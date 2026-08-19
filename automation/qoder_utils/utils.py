"""
Qoder Creator - Utilities
Logging, random generators, save/load helpers.
"""

import json
import random
import string
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .config import LOG_FILE, DATA_DIR


# ================= LOGGING =================
def setup_logging():
    """Setup logging - create log file if not exists."""
    if not LOG_FILE.exists():
        LOG_FILE.write_text(
            f"# Qoder Creator Log - {datetime.now(timezone.utc).isoformat()}\n"
        )


def write_log(message: str, level: str = "INFO"):
    """Write a log entry."""
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    except Exception:
        pass


# ================= JSONL =================
def save_jsonl(filepath: Path, data: Dict[str, Any]):
    """Append a JSON line to a file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def load_jsonl(filepath: Path) -> list:
    """Load all lines from a JSONL file."""
    if not filepath.exists():
        return []
    results = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return results


# ================= GENERATORS =================
def generate_password(length: int = 14) -> str:
    """Generate a strong random password."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(random.choices(chars, k=length))


def generate_machine_id() -> str:
    """Generate a fake machine ID (32-char hex)."""
    return hashlib.md5(str(random.randint(1000000, 9999999)).encode()).hexdigest()[:32]


def generate_ms_deviceid() -> str:
    """Generate a fake Microsoft device ID."""
    return str(uuid.uuid4())


def generate_nonce(length: int = 16) -> str:
    """Generate a random nonce."""
    return uuid.uuid4().hex[:length]


# ================= TEXT HELPERS =================
def extract_otp(text: str, length: int = 6) -> Optional[str]:
    """Extract OTP/verification code from text."""
    import re

    if not text:
        return None

    # 1. Clean HTML tags and CSS style blocks (e.g. style="color: #232323;")
    clean_text = re.sub(r'<style[^>]*>[\s\S]*?</style>', ' ', text, flags=re.IGNORECASE)
    clean_text = re.sub(r'<script[^>]*>[\s\S]*?</script>', ' ', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'#[0-9a-fA-F]{6}', ' ', clean_text)  # Strip CSS hex color codes like #232323
    clean_text = re.sub(r'<[^>]+>', ' ', clean_text)          # Strip HTML tags

    # 2. Targeted regex patterns (highest priority)
    targeted_patterns = [
        r'verification\s*code[:\s]+(\d{4,8})',
        r'verify\s*code[:\s]+(\d{4,8})',
        r'code\s*is[:\s]+(\d{4,8})',
        r'your\s*code\s*is[:\s]+(\d{4,8})',
        r'OTP[:\s]+(\d{4,8})',
        r'passcode[:\s]+(\d{4,8})',
        r'confirm\s*code[:\s]+(\d{4,8})',
    ]

    for pattern in targeted_patterns:
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            return match.group(1)

    # 3. Standalone 6-digit number fallback (excluding common CSS hex values or timestamps)
    matches = re.findall(rf'\b(\d{{{length}}})\b', clean_text)
    for m in matches:
        if m not in ("232323", "000000", "ffffff", "123456"):
            return m

    return None
