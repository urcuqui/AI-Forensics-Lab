import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT_SECONDS = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "60"))
OLLAMA_TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.1"))

DATABASE_PATH = os.path.join(BASE_DIR, "data", "forensics_lab.sqlite3")

MAX_CONTENT_LENGTH = 256 * 1024  # 256 KB request body cap

MAX_EVIDENCE_SELECTION = 6
MAX_NOTE_LENGTH = 4000
