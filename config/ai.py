"""AI credentials shared by chat and moderation.

In local DEBUG mode, the .env file is authoritative and read on each call.
Django's autoreloader inherits old environment values from its parent, so a
one-time load_dotenv() cannot reliably pick up edited keys. Production keeps
normal process-environment precedence and requires a worker restart on changes.
"""
import os

from django.conf import settings
from dotenv import dotenv_values

DEFAULT_MODELS = {
    'DEEPSEEK': 'deepseek-chat',
    'GROQ': 'openai/gpt-oss-20b',
}


def get_provider_config(provider):
    provider = provider.upper()
    default_model = DEFAULT_MODELS[provider]
    local_values = dotenv_values(settings.BASE_DIR / '.env') if settings.DEBUG else {}

    def value(name):
        # An explicitly empty local key disables that provider, even if the
        # autoreloader parent still has a previous credential in its environment.
        raw = local_values[name] if name in local_values else os.getenv(name, '')
        return (raw or '').strip()

    return value(f'{provider}_API_KEY'), value(f'{provider}_MODEL') or default_model
