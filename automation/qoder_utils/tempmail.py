"""
Qoder Creator - Temp Mail & Worker API Client
Supports Tempik API & Custom Cloudflare Worker Email Handlers.
"""

import asyncio
import json
import random
import re
import time
import urllib.parse
import urllib.request
from typing import List, Optional, Dict, Any

from .config import TEMPIK_BASE
from .utils import write_log, extract_otp

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36"
)

WORKER_DOMAINS = {
    "erzet.site": "https://email-handler.rzz.workers.dev",
    "exploreabiansemal.site": "https://frosty-sunset-cc68.rzz.workers.dev",
}


class TempikClient:
    """Disposable email API client (supports Tempik & custom Cloudflare Workers)."""

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or TEMPIK_BASE).rstrip("/")
        self.session_id: Optional[str] = None
        self._email: Optional[str] = None
        self._domains: List[str] = []

    def _fetch_domains(self) -> List[str]:
        """Fetch available domains from /api/config or default worker domains."""
        if self._domains:
            return self._domains
        try:
            url = f"{self.base_url}/config"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", _BROWSER_UA)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            self._domains = data.get("mailDomains", [data.get("mailDomain")])
            self._domains = [d for d in self._domains if d]
        except Exception:
            self._domains = list(WORKER_DOMAINS.keys())

        if not self._domains:
            self._domains = list(WORKER_DOMAINS.keys())

        write_log(f"Available email domains: {self._domains}", "INFO")
        return self._domains

    def init_session(self) -> Optional[str]:
        """Create a new session (for standard Tempik API)."""
        if self.session_id:
            return self.session_id
        try:
            url = f"{self.base_url}/session"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", _BROWSER_UA)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            self.session_id = data.get("sessionId") or data.get("id") or data.get("session_id")
            write_log(f"Tempik session: {self.session_id[:8]}...", "INFO")
        except Exception:
            pass
        return self.session_id

    def create_inbox(self, local_part: str = None, domain: str = None) -> str:
        """Create a new inbox address."""
        if not domain:
            domains = self._fetch_domains()
            domain = random.choice(domains)

        if not local_part:
            names = ["bima", "dewi", "nangkalucu", "citra", "bleki", "rawah", "perkasa", "muda", "indah", "langit", "surya", "kirana", "bayu"]
            local_part = f"{random.choice(names)}{random.randint(10, 99)}"

        domain_lower = domain.lower()
        if domain_lower in WORKER_DOMAINS:
            self._email = f"{local_part}@{domain_lower}"
            write_log(f"Worker inbox created: {self._email}", "INFO")
            return self._email

        self.init_session()
        url = f"{self.base_url}/inboxes"
        body_data = {"domain": domain, "localPart": local_part}
        body = json.dumps(body_data).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Accept", "application/json")
        req.add_header("Content-Type", "application/json")
        if self.session_id:
            req.add_header("x-session-id", self.session_id)
        req.add_header("User-Agent", _BROWSER_UA)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            self._email = data.get("address")
            write_log(f"Tempik inbox: {self._email} (domain={domain})", "INFO")
            return self._email
        except Exception:
            self._email = f"{local_part}@{domain_lower}"
            return self._email

    def get_messages(self, address: str = None) -> List[Dict[str, Any]]:
        """Get all messages for an inbox address."""
        addr = address or self._email
        if not addr:
            raise ValueError("No email address provided")

        domain = addr.split("@")[-1].lower() if "@" in addr else ""
        if domain in WORKER_DOMAINS:
            worker_url = WORKER_DOMAINS[domain]
            url = f"{worker_url}/?email={urllib.parse.quote(addr)}"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", _BROWSER_UA)
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    for msg in data:
                        if "body" not in msg:
                            msg["body"] = msg.get("html") or msg.get("text") or ""
                    return data
            except Exception as e:
                write_log(f"Worker get_messages error ({addr}): {e}", "WARNING")
                return []

        url = f"{self.base_url}/inboxes/{addr}/messages"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        if self.session_id:
            req.add_header("x-session-id", self.session_id)
        req.add_header("User-Agent", _BROWSER_UA)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            write_log(f"get_messages error ({addr}): {e}", "WARNING")
            return []

    async def wait_for_messages(
        self,
        address: str = None,
        max_wait: int = 60,
        interval: int = 4,
    ) -> List[Dict[str, Any]]:
        """Poll for messages until at least one arrives or max_wait is reached."""
        addr = address or self._email
        start = time.time()
        attempt = 0

        while (time.time() - start) < max_wait:
            attempt += 1
            msgs = self.get_messages(addr)
            if msgs:
                write_log(f"Message received for {addr} after {attempt} attempts", "SUCCESS")
                return msgs

            await asyncio.sleep(interval)

        write_log(f"Timeout waiting for messages ({addr}) after {max_wait}s", "WARNING")
        return []

    def extract_otp(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extract OTP from message list."""
        for msg in messages:
            body = msg.get("body") or msg.get("html") or msg.get("text") or msg.get("snippet") or ""
            subject = msg.get("subject") or ""
            text = f"{subject}\n{body}"
            otp = extract_otp(text)
            if otp:
                return otp
        return None
