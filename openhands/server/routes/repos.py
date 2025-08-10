from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from openhands.core.logger import openhands_logger as logger
from openhands.events.action import FileReadAction
from openhands.events.action.files import FileWriteAction
from openhands.events.observation import ErrorObservation, FileReadObservation
from openhands.integrations.provider import PROVIDER_TOKEN_TYPE
from openhands.integrations.service_types import ProviderType
from openhands.integrations.github.github_service import GithubServiceImpl
from openhands.runtime.base import Runtime
from openhands.server.dependencies import get_dependencies
from openhands.server.user_auth import get_provider_tokens
from openhands.server.utils import get_conversation, get_conversation_metadata
from openhands.server.session.conversation import ServerConversation
from openhands.utils.async_utils import call_sync_from_async

app = APIRouter(
    prefix='/api/conversations/{conversation_id}/repos', dependencies=get_dependencies()
)


class OpenRepoRequest(BaseModel):
    repository: str | None = None  # format: owner/repo
    branch: str | None = None


@app.post('/open')
async def open_repository(
    payload: OpenRepoRequest,
    provider_tokens: PROVIDER_TOKEN_TYPE | None = Depends(get_provider_tokens),
    conversation: ServerConversation = Depends(get_conversation),
) -> JSONResponse:
    try:
        runtime: Runtime = conversation.runtime
        repo = payload.repository
        branch = payload.branch
        logger.info(f'Opening repository: repo={repo}, branch={branch}')
        cloned_dir = await runtime.clone_or_init_repo(provider_tokens, repo, branch)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'workspace_dir': cloned_dir or ''},
        )
    except Exception as e:
        logger.error(f'Error opening repository: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': f'Error opening repository: {e}'},
        )


@app.get('/tree', response_model=list[str])
async def get_tree(
    conversation: ServerConversation = Depends(get_conversation),
    path: str | None = None,
) -> list[str] | JSONResponse:
    try:
        runtime: Runtime = conversation.runtime
        file_list = await call_sync_from_async(runtime.list_files, path)
        # prefix path if provided to return full relative paths
        if path:
            file_list = [os.path.join(path, f) for f in file_list]
        return file_list
    except Exception as e:
        logger.error(f'Error getting file tree: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': f'Error getting file tree: {e}'},
        )


@app.get('/file')
async def read_file(
    conversation: ServerConversation = Depends(get_conversation),
    path: str | None = None,
) -> JSONResponse:
    if not path:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={'error': 'Missing path'}
        )
    runtime: Runtime = conversation.runtime
    absolute = os.path.join(runtime.config.workspace_mount_path_in_sandbox, path)
    read_action = FileReadAction(absolute)
    try:
        observation = await call_sync_from_async(runtime.run_action, read_action)
        if isinstance(observation, FileReadObservation):
            return JSONResponse(content={'path': path, 'content': observation.content})
        elif isinstance(observation, ErrorObservation):
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={'error': f'Error opening file: {observation}'},
            )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': f'Unexpected observation type: {type(observation)}'},
        )
    except Exception as e:
        logger.error(f'Error reading file {path}: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': f'Error reading file: {e}'},
        )


class WriteFileRequest(BaseModel):
    path: str
    content: str


@app.put('/file')
async def write_file(
    payload: WriteFileRequest,
    conversation: ServerConversation = Depends(get_conversation),
) -> JSONResponse:
    runtime: Runtime = conversation.runtime
    absolute = os.path.join(runtime.config.workspace_mount_path_in_sandbox, payload.path)
    write_action = FileWriteAction(path=absolute, content=payload.content)
    try:
        await call_sync_from_async(runtime.run_action, write_action)
        return JSONResponse(status_code=status.HTTP_200_OK, content={'ok': True})
    except Exception as e:
        logger.error(f'Error writing file {payload.path}: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': f'Error writing file: {e}'},
        )


class CreateBranchRequest(BaseModel):
    name: str
    from_ref: str | None = None


@app.post('/branch')
async def create_branch(
    payload: CreateBranchRequest,
    conversation: ServerConversation = Depends(get_conversation),
    metadata=Depends(get_conversation_metadata),
) -> JSONResponse:
    try:
        runtime: Runtime = conversation.runtime
        repo_dir = (metadata.selected_repository or '').split('/')[-1]
        if not repo_dir:
            return JSONResponse(status_code=400, content={'error': 'No repository opened'})
        base = payload.from_ref or 'HEAD'
        cmd = f'cd {repo_dir} && git fetch origin && git checkout -b {payload.name} {base}'
        await call_sync_from_async(runtime.run_action, FileReadAction(''))
        from openhands.events.action.commands import CmdRunAction  # lazy import to avoid cycles
        await call_sync_from_async(runtime.run_action, CmdRunAction(command=cmd))
        return JSONResponse(status_code=200, content={'branch': payload.name})
    except Exception as e:
        logger.error(f'Error creating branch: {e}')
        return JSONResponse(status_code=500, content={'error': f'{e}'})


class CommitRequest(BaseModel):
    message: str


@app.post('/commit')
async def commit_changes(
    payload: CommitRequest,
    conversation: ServerConversation = Depends(get_conversation),
    metadata=Depends(get_conversation_metadata),
) -> JSONResponse:
    try:
        runtime: Runtime = conversation.runtime
        repo_dir = (metadata.selected_repository or '').split('/')[-1]
        if not repo_dir:
            return JSONResponse(status_code=400, content={'error': 'No repository opened'})
        safe_msg = payload.message.replace('"', '\\"')
        cmd = f'cd {repo_dir} && git add -A && git commit -m "{safe_msg}" || true && git rev-parse HEAD'
        from openhands.events.action.commands import CmdRunAction
        obs = await call_sync_from_async(runtime.run_action, CmdRunAction(command=cmd))
        sha = None
        try:
            # observation content likely contains output; best-effort parse last 40-hex
            import re
            m = re.findall(r'[0-9a-f]{40}', str(getattr(obs, 'content', '')))
            sha = m[-1] if m else None
        except Exception:
            pass
        return JSONResponse(status_code=200, content={'ok': True, 'commit': sha})
    except Exception as e:
        logger.error(f'Error committing changes: {e}')
        return JSONResponse(status_code=500, content={'error': f'{e}'})


class PRRequest(BaseModel):
    title: str
    body: str | None = None
    target_branch: str | None = None
    draft: bool = True
    labels: list[str] | None = None


@app.post('/pr')
async def create_pr_endpoint(
    payload: PRRequest,
    provider_tokens: PROVIDER_TOKEN_TYPE | None = Depends(get_provider_tokens),
    conversation: ServerConversation = Depends(get_conversation),
    metadata=Depends(get_conversation_metadata),
) -> JSONResponse:
    try:
        runtime: Runtime = conversation.runtime
        repo_full = metadata.selected_repository
        if not repo_full:
            return JSONResponse(status_code=400, content={'error': 'No repository selected'})
        repo_dir = repo_full.split('/')[-1]

        # Determine current branch
        from openhands.events.action.commands import CmdRunAction
        get_branch_cmd = f'cd {repo_dir} && git branch --show-current'
        obs = await call_sync_from_async(runtime.run_action, CmdRunAction(command=get_branch_cmd))
        curr_branch = getattr(obs, 'content', '').strip() if obs else ''
        if not curr_branch:
            return JSONResponse(status_code=500, content={'error': 'Failed to detect current branch'})

        # Ensure branch is pushed
        push_cmd = f'cd {repo_dir} && git push -u origin {curr_branch}'
        await call_sync_from_async(runtime.run_action, CmdRunAction(command=push_cmd))

        # Determine target branch if not provided (default remote HEAD)
        target_branch = payload.target_branch
        if not target_branch:
            detect_cmd = (
                f"cd {repo_dir} && git remote show origin | grep 'HEAD branch' | awk -F': ' '{{print $2}}'"
            )
            obs2 = await call_sync_from_async(runtime.run_action, CmdRunAction(command=detect_cmd))
            target_branch = getattr(obs2, 'content', '').strip() or 'main'

        # Call GitHub service
        if not provider_tokens or ProviderType.GITHUB not in provider_tokens:
            return JSONResponse(status_code=400, content={'error': 'Missing GitHub token'})
        gh_token = provider_tokens[ProviderType.GITHUB]
        github_service = GithubServiceImpl(
            user_id=gh_token.user_id,
            token=gh_token.token,
            base_domain=gh_token.host,
        )
        pr_url = await github_service.create_pr(
            repo_name=repo_full,
            source_branch=curr_branch,
            target_branch=target_branch,
            title=payload.title,
            body=payload.body,
            draft=payload.draft,
            labels=payload.labels,
        )
        return JSONResponse(status_code=200, content={'url': pr_url})
    except Exception as e:
        logger.error(f'Error creating PR: {e}')
        return JSONResponse(status_code=500, content={'error': f'{e}'})