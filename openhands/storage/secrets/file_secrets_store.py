from __future__ import annotations

import json
import os
import base64
import hashlib
from dataclasses import dataclass

from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.core.logger import openhands_logger as logger
from openhands.storage import get_file_store
from openhands.storage.data_models.user_secrets import UserSecrets
from openhands.storage.files import FileStore
from openhands.storage.secrets.secrets_store import SecretsStore
from openhands.utils.async_utils import call_sync_from_async

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover
    _CRYPTO_AVAILABLE = False


def _derive_key() -> bytes | None:
    secret = os.environ.get('SECRETS_ENC_KEY')
    if not secret:
        return None
    # Derive a 32-byte key from the passphrase using SHA-256
    return hashlib.sha256(secret.encode('utf-8')).digest()


def _encrypt_provider_tokens(tokens_dict: dict) -> str:
    key = _derive_key()
    if not key or not _CRYPTO_AVAILABLE:
        # Should not be called without key; safeguard
        raise ValueError('Encryption key unavailable')
    data = json.dumps(tokens_dict, separators=(',', ':')).encode('utf-8')
    aesgcm = AESGCM(key)
    # 12-byte nonce for AES-GCM
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, data, associated_data=None)
    payload = nonce + ct
    return base64.b64encode(payload).decode('ascii')


def _decrypt_provider_tokens(enc_b64: str) -> dict:
    key = _derive_key()
    if not key or not _CRYPTO_AVAILABLE:
        raise ValueError('Decryption key unavailable')
    try:
        payload = base64.b64decode(enc_b64)
        nonce, ct = payload[:12], payload[12:]
        aesgcm = AESGCM(key)
        pt = aesgcm.decrypt(nonce, ct, associated_data=None)
        return json.loads(pt.decode('utf-8'))
    except Exception as e:  # pragma: no cover
        logger.warning(f'Failed to decrypt provider tokens: {e}')
        raise


@dataclass
class FileSecretsStore(SecretsStore):
    file_store: FileStore
    path: str = 'secrets.json'

    async def load(self) -> UserSecrets | None:
        try:
            json_str = await call_sync_from_async(self.file_store.read, self.path)
            kwargs = json.loads(json_str)

            # Handle encrypted provider tokens if present
            enc = kwargs.get('provider_tokens_enc')
            if enc:
                try:
                    tokens = _decrypt_provider_tokens(enc)
                    kwargs['provider_tokens'] = tokens
                except Exception:
                    # If decryption fails, keep provider_tokens empty for safety
                    kwargs['provider_tokens'] = {}
            
            # Backward compatibility: if plaintext provider_tokens exists, prefer it
            # (Only keep entries that have non-empty token values)
            provider_tokens = {
                k: v
                for k, v in (kwargs.get('provider_tokens') or {}).items()
                if v.get('token')
            }
            kwargs['provider_tokens'] = provider_tokens
            secrets = UserSecrets(**kwargs)
            return secrets
        except FileNotFoundError:
            return None

    async def store(self, secrets: UserSecrets) -> None:
        # Dump as dict so we can modify fields
        data = secrets.model_dump(context={'expose_secrets': True})

        # Encrypt provider_tokens when key is available
        key = _derive_key()
        if key and _CRYPTO_AVAILABLE:
            try:
                provider_tokens = data.get('provider_tokens') or {}
                if provider_tokens:
                    data['provider_tokens_enc'] = _encrypt_provider_tokens(provider_tokens)
                # Remove plaintext provider tokens
                data.pop('provider_tokens', None)
            except Exception as e:  # pragma: no cover
                logger.warning(f'Failed to encrypt provider tokens, storing as plaintext: {e}')
        else:
            if os.environ.get('SECRETS_ENC_KEY') and not _CRYPTO_AVAILABLE:
                logger.warning('SECRETS_ENC_KEY is set but cryptography is unavailable; storing tokens as plaintext')

        json_str = json.dumps(data, separators=(',', ':'))
        await call_sync_from_async(self.file_store.write, self.path, json_str)

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> FileSecretsStore:
        file_store = get_file_store(
            config.file_store,
            config.file_store_path,
            config.file_store_web_hook_url,
            config.file_store_web_hook_headers,
        )
        return FileSecretsStore(file_store)
