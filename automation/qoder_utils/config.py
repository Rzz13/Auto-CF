"""
Qoder Creator - Configuration
"""

import os
import platform
from pathlib import Path
from typing import Any

# ================= ANSI COLORS =================
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    MAGENTA = '\033[95m'


def print_color(text, color=Colors.RESET):
    print(f"{color}{text}{Colors.RESET}")


# ================= PLATFORM =================
SYSTEM = platform.system()
IS_MAC = SYSTEM == "Darwin"
IS_WINDOWS = SYSTEM == "Windows"
IS_LINUX = SYSTEM == "Linux"

# ================= API URLs =================
TEMPIK_BASE = os.getenv("TEMPIK_BASE", "https://tempik.example.com/api")
QODER_BASE = "https://qoder.com"
QODER_OPENAPI = "https://openapi.qoder.sh"

# ================= SIGNUP =================
HEADLESS = True
SIGNUP_DELAY = 5
SIGNUP_RETRY = 2
CONCURRENCY = 1

# ================= PROXY =================
PROXY_MODE = "none"

# ================= FILE PATHS =================
BASE_DIR = Path(__file__).parent.parent.parent
PROXY_FILE = BASE_DIR / "proxies.txt"
DATA_DIR = BASE_DIR / "data"
ACCOUNTS_FILE = DATA_DIR / "qoder_accounts.jsonl"
LOG_FILE = DATA_DIR / "qoder.log"

# ================= DEFAULTS =================
DEFAULT_PASSWORD_LENGTH = 14
DEFAULT_TIMEOUT = 120000
DEFAULT_OTP_TIMEOUT = 150

# Ensure data dir exists
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
