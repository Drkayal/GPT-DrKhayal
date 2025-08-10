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
from openhands.runtime.base import Runtime
from openhands.server.dependencies import get_dependencies
from openhands.server.user_auth import get_provider_tokens
from openhands.server.utils import get_conversation
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