"""Read explicit subscription validity fields; never use token/window expiry."""
import base64
import json
import os
from datetime import datetime
from pathlib import Path


def subscription_date(value):
    try:
        if isinstance(value, (float, int)) and not isinstance(value, bool):
            date = datetime.fromtimestamp(value / 1000 if value > 100_000_000_000 else value)
        elif isinstance(value, str) and value.strip():
            date = datetime.fromisoformat(value.strip().replace('Z', '+00:00')).astimezone()
        else:
            return ''
        if not 2000 <= date.year <= 2100:
            return ''
        return date.strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError, OverflowError, OSError):
        return ''


def read_codex_subscription_expiry(path=None):
    """Display-only metadata from the same local auth file used by Codex.

    This is a login-time snapshot, not a live billing request. JWT exp is the
    access credential lifetime and must never be treated as membership expiry.
    """
    try:
        path = Path(path) if path is not None else Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'auth.json'
        if path.stat().st_size > 2_000_000:
            return ''
        auth = json.loads(path.read_text(encoding='utf8'))
        token = auth.get('tokens', {}).get('id_token', '')
        encoded = token.split('.')[1]
        claims = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        metadata = claims.get('https://api.openai.com/auth') or {}
        return subscription_date(metadata.get('chatgpt_subscription_active_until'))
    except (OSError, ValueError, TypeError, AttributeError, IndexError):
        return ''
