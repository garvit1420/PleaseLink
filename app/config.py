"""
Application configuration — loaded from environment variables.

Every setting has a sensible default so the app can start locally
with just PSEUDOGRAM_API_KEY set.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── PseudoGram API ──────────────────────────────────────────────
API_KEY: str = os.environ.get("PSEUDOGRAM_API_KEY", "")
BASE_URL: str = os.environ.get("PSEUDOGRAM_BASE_URL", "https://pseudogram-api.onrender.com")

# ── Database ────────────────────────────────────────────────────
DB_PATH: str = os.environ.get("DB_PATH", "data/linkplease.db")

# ── DM Sender ──────────────────────────────────────────────────
MAX_RETRIES: int = int(os.environ.get("MAX_RETRIES", "5"))
RATE_LIMIT_MAX: int = int(os.environ.get("RATE_LIMIT_MAX", "9"))  # safety margin below 10
RATE_LIMIT_WINDOW: int = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))  # seconds
SENDER_POLL_INTERVAL: float = float(os.environ.get("SENDER_POLL_INTERVAL", "0.5"))

# ── Reconciler ──────────────────────────────────────────────────
RECONCILE_INTERVAL: int = int(os.environ.get("RECONCILE_INTERVAL", "10"))  # seconds

# ── Webhook ─────────────────────────────────────────────────────
VERIFY_SIGNATURES: bool = os.environ.get(
    "SIGNATURE_VERIFICATION_ENABLED",
    os.environ.get("VERIFY_SIGNATURES", "true")
).lower() == "true"
