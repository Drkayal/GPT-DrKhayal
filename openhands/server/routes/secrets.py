from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from openhands.core.logger import openhands_logger as logger
from openhands.integrations.provider import PROVIDER_TOKEN_TYPE, CustomSecret
from openhands.integrations.service_types import ProviderType
from openhands.integrations.utils import validate_provider_token
from openhands.server.dependencies import get_dependencies
from openhands.server.settings import (
    CustomSecretModel,
    CustomSecretWithoutValueModel,
    GETCustomSecrets,
    POSTProviderModel,
)
# from openhands.server.user_auth import (
#     get_provider_tokens,
#     get_secrets_store,
#     get_user_secrets,
# )
from openhands.storage.data_models.settings import Settings
from openhands.storage.data_models.user_secrets import UserSecrets
from openhands.storage.secrets.secrets_store import SecretsStore
from openhands.storage.settings.settings_store import SettingsStore
from openhands.server import shared

app = APIRouter(prefix='/api', dependencies=get_dependencies())


def _get_user_auth_deps():
    from openhands.server.user_auth import (  # local import to avoid circulars in tests
        get_provider_tokens,
        get_secrets_store,
        get_user_secrets,
    )

    return get_provider_tokens, get_secrets_store, get_user_secrets

# Bind locally-resolved dependencies for module scope usage
_get_provider_tokens, _get_secrets_store, _get_user_secrets = _get_user_auth_deps()

# Local dependencies that directly use FileSecretsStore for tests and OSS default
async def _dep_secrets_store() -> SecretsStore:
    from openhands.storage.secrets.file_secrets_store import FileSecretsStore
    return await FileSecretsStore.get_instance(shared.config, None)


async def _dep_user_secrets(
    secrets_store: SecretsStore = Depends(_dep_secrets_store),
) -> UserSecrets | None:
    return await secrets_store.load()


# =================================================
# SECTION: Handle git provider tokens
# =================================================


async def invalidate_legacy_secrets_store(
    settings: Settings, settings_store: SettingsStore, secrets_store: SecretsStore
) -> UserSecrets | None:
    """We are moving `secrets_store` (a field from `Settings` object) to its own dedicated store
    This function moves the values from Settings to UserSecrets, and deletes the values in Settings
    While this function in called multiple times, the migration only ever happens once
    """
    if len(settings.secrets_store.provider_tokens.items()) > 0:
        user_secrets = UserSecrets(
            provider_tokens=settings.secrets_store.provider_tokens
        )
        await secrets_store.store(user_secrets)

        # Invalidate old tokens via settings store serializer
        invalidated_secrets_settings = settings.model_copy(
            update={'secrets_store': UserSecrets()}
        )
        await settings_store.store(invalidated_secrets_settings)

        return user_secrets

    return None


def process_token_validation_result(
    confirmed_token_type: ProviderType | None, token_type: ProviderType
) -> str:
    if not confirmed_token_type or confirmed_token_type != token_type:
        return (
            f'Invalid token. Please make sure it is a valid {token_type.value} token.'
        )

    return ''


async def check_provider_tokens(
    incoming_provider_tokens: POSTProviderModel,
    existing_provider_tokens: PROVIDER_TOKEN_TYPE | None,
) -> str:
    msg = ''
    if incoming_provider_tokens.provider_tokens:
        # Determine whether tokens are valid
        for token_type, token_value in incoming_provider_tokens.provider_tokens.items():
            if token_value.token:
                confirmed_token_type = await validate_provider_token(
                    token_value.token, token_value.host
                )  # FE always sends latest host
                msg = process_token_validation_result(confirmed_token_type, token_type)

            existing_token = (
                existing_provider_tokens.get(token_type, None)
                if existing_provider_tokens
                else None
            )
            if (
                existing_token
                and (existing_token.host != token_value.host)
                and existing_token.token
            ):
                confirmed_token_type = await validate_provider_token(
                    existing_token.token, token_value.host
                )  # Host has changed, check it against existing token
                if not confirmed_token_type or confirmed_token_type != token_type:
                    msg = process_token_validation_result(
                        confirmed_token_type, token_type
                    )

    return msg


@app.post('/add-git-providers')
async def store_provider_tokens(
    provider_info: POSTProviderModel,
    secrets_store: SecretsStore = Depends(_dep_secrets_store),
    provider_tokens: PROVIDER_TOKEN_TYPE | None = Depends(_get_provider_tokens),
) -> JSONResponse:
    provider_err_msg = await check_provider_tokens(provider_info, provider_tokens)
    if provider_err_msg:
        logger.info(
            f'Returning 401 Unauthorized - Provider token error: {provider_err_msg}'
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={'error': provider_err_msg},
        )

    try:
        user_secrets = await secrets_store.load()
        if not user_secrets:
            user_secrets = UserSecrets()

        # Start from existing provider tokens
        merged_tokens: dict[ProviderType, CustomSecret | object] = dict(
            user_secrets.provider_tokens
        )

        # Merge incoming provider tokens
        if provider_info.provider_tokens:
            for provider, incoming in provider_info.provider_tokens.items():
                existing = merged_tokens.get(provider)
                if existing:
                    # If incoming token is empty, keep existing token; always update host if provided
                    token_to_use = existing.token if not incoming.token else incoming.token
                    merged_tokens[provider] = incoming.model_copy(
                        update={'token': token_to_use, 'host': incoming.host or existing.host}
                    )
                else:
                    merged_tokens[provider] = incoming

        updated_secrets = user_secrets.model_copy(
            update={'provider_tokens': merged_tokens}
        )
        await secrets_store.store(updated_secrets)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'message': 'Git providers stored'},
        )
    except Exception as e:
        logger.warning(f'Something went wrong storing git providers: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': 'Something went wrong storing git providers'},
        )


@app.post('/unset-provider-tokens', response_model=dict[str, str])
async def unset_provider_tokens(
    secrets_store: SecretsStore = Depends(_dep_secrets_store),
) -> JSONResponse:
    try:
        await secrets_store.store(UserSecrets())
        return JSONResponse(
            status_code=status.HTTP_200_OK, content={'message': 'Tokens unset'}
        )
    except Exception as e:
        logger.warning(f'Failed to unset tokens: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': 'Failed to unset tokens'},
        )


# =================================================
# SECTION: Handle custom secrets
# =================================================


@app.get('/secrets', response_model=GETCustomSecrets)
async def load_custom_secrets_names(
    user_secrets: UserSecrets | None = Depends(_dep_user_secrets),
) -> GETCustomSecrets | JSONResponse:
    try:
        if not user_secrets or not user_secrets.custom_secrets:
            return GETCustomSecrets(custom_secrets=[])

        custom_secrets: list[CustomSecretWithoutValueModel] = []
        for secret_name, secret_value in user_secrets.custom_secrets.items():
            custom_secret = CustomSecretWithoutValueModel(
                name=secret_name,
                description=secret_value.description,
            )
            custom_secrets.append(custom_secret)

        return GETCustomSecrets(custom_secrets=custom_secrets)

    except Exception as e:
        logger.warning(f'Failed to load secret names: {e}')
        logger.info('Returning 401 Unauthorized - Failed to get secret names')
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={'error': 'Failed to get secret names'},
        )


@app.post('/secrets', response_model=dict[str, str])
async def create_custom_secret(
    incoming_secret: CustomSecretModel,
    secrets_store: SecretsStore = Depends(_dep_secrets_store),
) -> JSONResponse:
    try:
        existing_secrets = await secrets_store.load()
        if not existing_secrets:
            existing_secrets = UserSecrets()
        custom_secrets = dict(existing_secrets.custom_secrets)

        secret_name = incoming_secret.name
        secret_value = incoming_secret.value
        secret_description = incoming_secret.description

        if secret_name in custom_secrets:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={'message': f'Secret {secret_name} already exists'},
            )

        custom_secrets[secret_name] = CustomSecret(
            secret=secret_value,
            description=secret_description or '',
        )

        # Preserve provider tokens
        updated_user_secrets = existing_secrets.model_copy(
            update={'custom_secrets': custom_secrets}
        )
        await secrets_store.store(updated_user_secrets)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={'message': f'Secret {secret_name} created successfully'},
        )
    except Exception as e:
        logger.warning(f'Failed to create secret: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': 'Failed to create secret'},
        )


@app.put('/secrets/{secret_id}', response_model=dict[str, str])
async def update_custom_secret(
    secret_id: str,
    incoming_secret: CustomSecretWithoutValueModel,
    secrets_store: SecretsStore = Depends(_dep_secrets_store),
) -> JSONResponse:
    try:
        existing_secrets = await secrets_store.load()
        if not existing_secrets:
            existing_secrets = UserSecrets()
        custom_secrets = dict(existing_secrets.custom_secrets)

        if secret_id not in custom_secrets:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'message': f'Secret {secret_id} not found'},
            )

        # Update description only, keep existing secret value
        current = custom_secrets[secret_id]
        custom_secrets[secret_id] = CustomSecret(
            secret=current.secret,
            description=incoming_secret.description or '',
        )

        updated_user_secrets = existing_secrets.model_copy(
            update={'custom_secrets': custom_secrets}
        )
        await secrets_store.store(updated_user_secrets)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'message': f'Secret {secret_id} updated successfully'},
        )
    except Exception as e:
        logger.warning(f'Failed to update secret: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': 'Failed to update secret'},
        )


@app.delete('/secrets/{secret_id}')
async def delete_custom_secret(
    secret_id: str,
    secrets_store: SecretsStore = Depends(_dep_secrets_store),
) -> JSONResponse:
    try:
        existing_secrets = await secrets_store.load()
        if not existing_secrets:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'message': f'Secret {secret_id} not found'},
            )

        custom_secrets = dict(existing_secrets.custom_secrets)
        if secret_id not in custom_secrets:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'message': f'Secret {secret_id} not found'},
            )

        custom_secrets.pop(secret_id)
        updated_user_secrets = existing_secrets.model_copy(
            update={'custom_secrets': custom_secrets}
        )
        await secrets_store.store(updated_user_secrets)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'message': f'Secret {secret_id} deleted successfully'},
        )
    except Exception as e:
        logger.warning(f'Failed to delete secret: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': 'Failed to delete secret'},
        )
