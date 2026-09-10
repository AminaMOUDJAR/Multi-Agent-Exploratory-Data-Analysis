import os

from dotenv import load_dotenv

# Always load backend/.env regardless of the current working directory.
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_ENV_PATH)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_BASE_URL = _env("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = _env("LLM_MODEL", "openai/gpt-oss-20b")
MAX_ROWS = int(_env("MAX_ROWS", "100000"))

LLM_ENABLED = bool(OPENAI_API_KEY)


def llm_client():
    """Return an OpenAI-compatible client, or None when no key is configured.

    Works with OpenAI, Groq, Together, Ollama (+ /v1), LM Studio, etc.
    """
    if not LLM_ENABLED:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=60.0, max_retries=1)
    except Exception:
        return None
