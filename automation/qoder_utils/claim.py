"""
Qoder Creator - Claim Manager
Automate Qoder trial claim via Qoder CLI / device authentication.
"""

import os
import sys
import subprocess
import shutil
import platform
import json
import asyncio
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from .utils import write_log
from .config import ACCOUNTS_FILE


class ClaimManager:
    """Handle device trial claim via Qoder CLI (qodercli-wake) & In-Browser PKCE Auth."""

    @staticmethod
    def is_linux() -> bool:
        return platform.system() == "Linux"

    @staticmethod
    def get_cli_path() -> Optional[str]:
        """Check if qodercli or qodercli-wake is installed in PATH or local dir."""
        for binary in ["qodercli-wake", "qodercli", "qoder"]:
            path = shutil.which(binary)
            if path:
                return path
            
            candidates = [
                Path.home() / ".local" / "bin" / binary,
                Path.home() / ".qoder" / "bin" / binary,
                Path("/root/.local/bin") / binary,
                Path("/root/.qoder/bin") / binary,
                Path("/usr/local/bin") / binary,
            ]
            for c in candidates:
                if c.exists() and c.is_file():
                    return str(c)

            qoder_dir = Path.home() / ".qoder" / "bin" / binary
            if qoder_dir.exists() and qoder_dir.is_dir():
                for p in qoder_dir.glob(f"{binary}*"):
                    if p.is_file():
                        return str(p)

            root_qoder_dir = Path("/root/.qoder/bin") / binary
            if root_qoder_dir.exists() and root_qoder_dir.is_dir():
                for p in root_qoder_dir.glob(f"{binary}*"):
                    if p.is_file():
                        return str(p)

        return None

    @classmethod
    async def auto_device_authorize(cls, page) -> bool:
        """
        Run qodercli login in background to obtain device auth URL,
        then navigate and authorize automatically in the active logged-in browser session.
        """
        cli = cls.get_cli_path()
        if not cli:
            return False

        auth_url = None
        proc = None

        try:
            write_log("Starting background qodercli login for device authorization...", "INFO")
            proc = subprocess.Popen(
                [cli, "login"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            start_time = time.time()
            while time.time() - start_time < 10:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if "https://qoder.com/device/selectAccounts" in line:
                    match = re.search(r"https://qoder\.com/device/selectAccounts\?[^\s]+", line)
                    if match:
                        auth_url = match.group(0)
                        break
                await asyncio.sleep(0.2)

            if auth_url:
                write_log(f"Captured device auth URL: {auth_url}", "INFO")
                await page.goto(auth_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(3000)

                btns = await page.query_selector_all("button, a")
                for b in btns:
                    try:
                        text = (await b.inner_text()).strip()
                        if any(w in text.lower() for w in ["authorize", "confirm", "allow", "continue", "select"]):
                            await b.click()
                            write_log(f"Clicked device authorization button: '{text}'", "SUCCESS")
                            await page.wait_for_timeout(3000)
                            return True
                    except Exception:
                        pass
        except Exception as e:
            write_log(f"Auto device authorization error: {e}", "WARNING")
        finally:
            if proc and proc.poll() is None:
                proc.terminate()

        return False

    @classmethod
    def claim_via_cli(cls, pat: str, email: str) -> bool:
        """Run qodercli-wake binary on native Linux / Ubuntu."""
        cli = cls.get_cli_path()
        if not cli:
            return False

        try:
            for cmd in [
                [cli, "login", pat],
                [cli, "login", "-t", pat],
                [cli, "login", "--token", pat],
            ]:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if res.returncode == 0 and "unknown option" not in res.stderr.lower():
                    write_log(f"qodercli claim success for {email}", "SUCCESS")
                    return True
        except Exception as e:
            write_log(f"CLI claim error for {email}: {e}", "WARNING")

        return False

    @classmethod
    async def claim_account(cls, account: Dict[str, Any]) -> bool:
        """Claim trial for a given account dict."""
        email = account.get("email", "?")
        pat = account.get("pat_token")

        if not pat:
            write_log(f"Cannot claim for {email}: missing PAT token", "ERROR")
            return False

        if cls.is_linux():
            return cls.claim_via_cli(pat, email)

        return False
