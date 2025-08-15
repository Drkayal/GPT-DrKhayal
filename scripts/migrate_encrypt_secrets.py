#!/usr/bin/env python3
import os
import sys
import json
import glob
import shutil
from datetime import datetime

from openhands.core.config import load_openhands_config

# Reuse encryption helpers from the store to ensure compatibility
from openhands.storage.secrets import file_secrets_store as fss


def main() -> int:
    cfg = load_openhands_config()
    root = os.path.expanduser(cfg.file_store_path or '~/.openhands')

    if not os.environ.get('SECRETS_ENC_KEY'):
        print('[migrate] SECRETS_ENC_KEY is not set. Skipping encryption.')
        return 0

    if not getattr(fss, '_CRYPTO_AVAILABLE', False):
        print('[migrate] cryptography is not available. Please install it first.')
        return 1

    users_glob = os.path.join(root, 'users', '*', 'secrets.json')
    paths = sorted(glob.glob(users_glob))
    if not paths:
        print(f'[migrate] No secrets found under: {users_glob}')
        return 0

    migrated = 0
    skipped = 0
    for p in paths:
        try:
            with open(p, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception as e:
            print(f'[migrate] WARN: failed reading {p}: {e}')
            skipped += 1
            continue

        # Skip if already encrypted
        if data.get('provider_tokens_enc'):
            skipped += 1
            continue

        provider_tokens = data.get('provider_tokens') or {}
        # Keep only entries that have non-empty token values (mirror runtime behavior)
        provider_tokens = {k: v for k, v in provider_tokens.items() if v.get('token')}
        if not provider_tokens:
            skipped += 1
            continue

        try:
            enc = fss._encrypt_provider_tokens(provider_tokens)  # type: ignore[attr-defined]
        except Exception as e:
            print(f'[migrate] ERROR: encryption failed for {p}: {e}')
            return 2

        # Backup existing file
        ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        backup_path = p + f'.bak-{ts}'
        try:
            shutil.copy2(p, backup_path)
        except Exception as e:
            print(f'[migrate] WARN: failed to create backup for {p}: {e}')

        # Write encrypted form; remove plaintext provider_tokens
        data['provider_tokens_enc'] = enc
        if 'provider_tokens' in data:
            del data['provider_tokens']

        try:
            with open(p, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, separators=(',', ':'))
            migrated += 1
        except Exception as e:
            print(f'[migrate] ERROR: failed writing {p}: {e}')
            return 3

    print(f'[migrate] Done. migrated={migrated}, skipped={skipped}, root={root}')
    return 0


if __name__ == '__main__':
    sys.exit(main())