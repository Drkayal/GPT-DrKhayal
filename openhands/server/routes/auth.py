from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from openhands.server.dependencies import get_dependencies
from openhands.server.user_auth import get_user_id
from openhands.server.user_auth.github_cookie_auth import SESSION_COOKIE_NAME


app = APIRouter(prefix='/api', dependencies=get_dependencies())


@app.post('/authenticate')
async def authenticate(user_id: str | None = Depends(get_user_id)) -> JSONResponse:
    if user_id:
        return JSONResponse({'message': 'Authenticated'})
    return JSONResponse({'error': 'Unauthorized'}, status_code=401)


@app.post('/logout')
async def logout() -> JSONResponse:
    resp = JSONResponse({'message': 'logged out'})
    resp.delete_cookie(SESSION_COOKIE_NAME, path='/')
    return resp