import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LINKEDIN_API_KEY = os.getenv("LINKEDIN_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
ZOOMINFO_API_KEY = os.getenv("ZOOMINFO_API_KEY", "")

CLAUDE_MODEL = "claude-sonnet-4-6"

MIN_NEWS_COUNT = int(os.getenv("MIN_NEWS_COUNT", "4"))

ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")


def save_api_keys(keys: dict):
    env_path = os.path.abspath(ENV_FILE)
    existing = {}

    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

    existing.update({k: v for k, v in keys.items() if v})

    with open(env_path, "w") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    load_dotenv(env_path, override=True)
