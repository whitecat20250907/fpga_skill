"""Keep the existing localhost console pairing across runtime-directory cleanup."""
from pathlib import Path
import os
import secrets


def console_token(run, persistent=Path('/var/lib/hmi/console.token')):
    runtime = run / 'console.token'
    if persistent.exists():
        token = persistent.read_text().strip()
        if len(token) < 32:raise ValueError('Invalid persisted console token')
    else:
        token = runtime.read_text().strip() if runtime.exists() else secrets.token_urlsafe(32)
        if len(token) < 32:raise ValueError('Invalid console token')
        persistent.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        try:
            fd = os.open(persistent, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return console_token(run, persistent)
        with os.fdopen(fd, 'w') as output:output.write(token)
    persistent.chmod(0o600)
    # Legacy launchers read the runtime path; preserve that interface.
    fd = os.open(runtime, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:output.write(token)
    runtime.chmod(0o600)
    return token
