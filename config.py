"""Load backend configuration from the repository root, preserving process settings."""
from pathlib import Path

from dotenv import load_dotenv


def load_backend_env():
    return load_dotenv(Path(__file__).resolve().parent / '.env', override=False)
