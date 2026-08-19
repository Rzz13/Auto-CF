#!/usr/bin/env python3
"""ChatGPT account auto-signup exported from verssache/chatgpt-creator Go repository.

Outputs JSON lines to stdout:
  {"step": "..."} — progress update
  {"status": "success", "email": "...", "password": "..."} — final result
  {"status": "error", "error": "..."} — failure
"""

import sys
import json
import argparse
import time
import random
import string
import re
import uuid
import base64
import os
import urllib.parse
from pathlib import Path

# External dependencies (installed via pip)
from bs4 import BeautifulSoup
from faker import Faker

try:
    from curl_cffi import requests
except ImportError:
    print(json.dumps({"status": "error", "error": "curl_cffi is not installed. Please run: pip install curl-cffi"}), flush=True)
    sys.exit(1)

# ── FNV1a32 Hash with Avalanche Finalizer ──────────────────────────────────────
def fnv1a32(text: str) -> str:
    h = 2166136261
    for c in text:
        h ^= ord(c)
        h = (h * 16777619) & 0xffffffff
    # Avalanche finalizer (murmur3-style)
    h ^= h >> 16
    h = (h * 2246822507) & 0xffffffff
    h ^= h >> 13
    h = (h * 3266489909) & 0xffffffff
    h ^= h >> 16
    return f"{h:08x}"

# ── Datadog Trace Headers Generator ───────────────────────────────────────────
def make_trace_headers() -> dict:
    trace_id = os.urandom(16)
    span_id = os.urandom(8)
    
    trace_id_hex = trace_id.hex()
    span_id_hex = span_id.hex()
    
    traceparent = f"00-{trace_id_hex}-{span_id_hex}-01"
    tracestate = f"dd=t.dm:-1;t.tid:{trace_id_hex[:16]};s:-1"
    
    # x-datadog-trace-id: decimal conversion of last 8 bytes of trace_id
    trace_id_int = int.from_bytes(trace_id[8:], byteorder='big')
    # x-datadog-parent-id: decimal conversion of spanID
    span_id_int = int.from_bytes(span_id, byteorder='big')
    
    return {
        "traceparent": traceparent,
        "tracestate": tracestate,
        "x-datadog-trace-id": str(trace_id_int),
        "x-datadog-parent-id": str(span_id_int),
        "x-datadog-sampling-priority": "-1",
    }

# ── Sentinel Token Generator (OpenAI Proof-of-Work) ──────────────────────────
class SentinelTokenGenerator:
    def __init__(self, device_id: str = None, ua: str = None):
        self.device_id = device_id or str(uuid.uuid4())
        self.ua = ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        self.requirements_seed = f"{random.random()}"
        self.sid = str(uuid.uuid4())

    def get_config(self) -> list:
        now = time.strftime("%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)", time.gmtime())
        perf_now = random.random() * 49000 + 1000
        time_origin = (time.time() * 1000) - perf_now

        nav_props = [
            "vendorSub", "productSub", "vendor", "maxTouchPoints",
            "scheduling", "userActivation", "doNotTrack", "geolocation",
            "connection", "plugins", "mimeTypes", "pdfViewerEnabled",
            "webkitTemporaryStorage", "webkitPersistentStorage",
            "hardwareConcurrency", "cookieEnabled", "credentials",
            "mediaDevices", "permissions", "locks", "ink",
        ]
        nav_prop = random.choice(nav_props)
        nav_val = f"{nav_prop}-undefined"

        screen_res = "1920x1080"
        sdk_js = "https://sentinel.openai.com/sentinel/20260124ceb8/sdk.js"

        return [
            screen_res,
            now,
            4294705152,
            0, # nonce placeholder
            self.ua,
            sdk_js,
            None,
            None,
            "en-US",
            "en-US,en",
            random.random(),
            nav_val,
            random.choice(["location", "implementation", "URL", "documentURI", "compatMode"]),
            random.choice(["Object", "Function", "Array", "Number", "parseFloat", "undefined"]),
            perf_now,
            self.sid,
            "",
            random.choice([4, 8, 12, 16]),
            time_origin
        ]

    def base64_encode(self, data) -> str:
        # Use separators=(',', ':') to match Go's compact json encoding without extra spaces
        raw = json.dumps(data, separators=(',', ':'))
        return base64.b64encode(raw.encode()).decode()

    def generate_token(self, seed: str = None, difficulty: str = None) -> str:
        seed = seed or self.requirements_seed
        difficulty = difficulty or "0"

        start_time = time.time()
        config = self.get_config()

        for i in range(500000):
            config[3] = i
            elapsed = int((time.time() - start_time) * 1000)
            config[9] = elapsed

            data = self.base64_encode(config)
            hash_hex = fnv1a32(seed + data)

            if hash_hex[:len(difficulty)] <= difficulty:
                return "gAAAAAB" + data + "~S"

        # Fallback error token
        return "gAAAAAB" + "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D" + self.base64_encode("None")

    def generate_requirements_token(self) -> str:
        config = self.get_config()
        config[3] = 1
        config[9] = random.randint(5, 49)
        data = self.base64_encode(config)
        return "gAAAAAC" + data

# ── Password & Birthday Helpers ────────────────────────────────────────────────
def generate_password(length: int = 14) -> str:
    if length <= 0:
        length = 14
    lower = "abcdefghijklmnopqrstuvwxyz"
    upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digit = "0123456789"
    special = "!@#$%&*"
    all_chars = lower + upper + digit + special

    pw = [
        random.choice(lower),
        random.choice(upper),
        random.choice(digit),
        random.choice(special)
    ]
    for _ in range(length - 4):
        pw.append(random.choice(all_chars))
    random.shuffle(pw)
    return "".join(pw)

def random_birthdate() -> str:
    year = random.randint(1985, 2002)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"

# ── Domain Blacklist Management ────────────────────────────────────────────────
BLACKLIST_FILE = "blacklist.json"

def load_blacklist() -> set:
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def add_blacklist_domain(domain: str):
    blacklist = load_blacklist()
    if domain not in blacklist:
        blacklist.add(domain)
        try:
            with open(BLACKLIST_FILE, "w") as f:
                json.dump(list(blacklist), f, indent=2)
        except Exception:
            pass

# ── Temp Email Generator & OTP Verification (generator.email) ────────────────
def create_temp_email(default_domain: str = None, proxies: dict = None) -> str:
    fake = Faker()
    if default_domain:
        first_name = fake.first_name().lower()
        last_name = fake.last_name().lower()
        rand_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
        return f"{first_name}{last_name}{rand_suffix}@{default_domain}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    
    session = requests.Session(impersonate="chrome120", proxies=proxies)
    try:
        resp = session.get("https://generator.email/", headers=headers, timeout=15)
        if resp.status_code != 200:
            raise Exception(f"generator.email returned status: {resp.status_code}")
        
        soup = BeautifulSoup(resp.text, "html.parser")
        domains = ["smartmail.de", "enayu.com", "crazymailing.com"]
        blacklist = load_blacklist()
        
        suggestions = soup.select(".e7m.tt-suggestions div > p")
        for sug in suggestions:
            dom = sug.get_text().strip()
            if dom and dom not in blacklist:
                domains.append(dom)
                
        random_domain = random.choice(domains)
        first_name = fake.first_name().lower()
        last_name = fake.last_name().lower()
        rand_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
        return f"{first_name}{last_name}{rand_suffix}@{random_domain}"
    except Exception as e:
        raise Exception(f"Failed to fetch temp email from generator.email: {e}")

# ── Ammail Helpers ─────────────────────────────────────────────────────────────
def load_config_domains():
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    config_paths = [
        os.path.join(root_dir, "config.json"),
        os.path.join(os.getcwd(), "config.json"),
        os.path.join(script_dir, "config.json")
    ]
    for p in config_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data.get("domains", [])
                    return data
            except Exception:
                pass
    return []

def custom_email_request(email, path):
    domain = email.split("@")[1].lower() if "@" in email else ""
    configs = load_config_domains()
    matched = None
    for cfg in configs:
        if cfg.get("domain", "").lower() == domain:
            matched = cfg
            break

    if not matched or not matched.get("domain_url"):
        return None

    base_url = matched.get("domain_url")
    if "?" in base_url:
        url = f"{base_url}&email={email}"
    else:
        url = f"{base_url}?email={email}"

    api_key = matched.get("x-api-key")

    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        req.add_header("Accept", "application/json")
        if api_key:
            req.add_header("x-api-key", api_key)
            
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            if "messages/" in path or path.startswith("/messages/"):
                msg_id = path.split("/")[-1]
                if isinstance(data, list):
                    for idx, msg in enumerate(data):
                        curr_id = str(msg.get("id") or msg.get("messageId") or f"custom_{idx}")
                        if curr_id == msg_id:
                            body_content = msg.get("body") or msg.get("text") or msg.get("html") or ""
                            return {
                                "message": {
                                    "id": curr_id,
                                    "subject": msg.get("subject", ""),
                                    "body": body_content,
                                    "html": msg.get("html", ""),
                                    "text": msg.get("text") or msg.get("body", ""),
                                    "from_address": msg.get("from") or msg.get("sender") or msg.get("from_address") or ""
                                }
                            }
                return {"message": {}}
            elif "messages" in path or "inboxes" in path:
                messages = []
                if isinstance(data, list):
                    for idx, msg in enumerate(data):
                        msg_id = msg.get("id") or msg.get("messageId") or f"custom_{idx}"
                        messages.append({
                            "id": msg_id,
                            "subject": msg.get("subject", "No Subject"),
                            "from": msg.get("from") or msg.get("sender") or msg.get("from_address") or "unknown",
                            "snippet": msg.get("snippet") or msg.get("body") or msg.get("text") or ""
                        })
                return {"messages": messages}
    except Exception:
        pass
    return None

def ammail_request(base_url, api_key, path, method="GET", data=None, host_header=None, email=None):
    email_ctx = email
    if email_ctx:
        email_ctx = email_ctx.lower()
        domain = email_ctx.split("@")[1] if "@" in email_ctx else ""
        configs = load_config_domains()
        configured_domains = [cfg.get("domain", "").lower() for cfg in configs]
        if domain in configured_domains:
            res = custom_email_request(email_ctx, path)
            if res is not None:
                return res

    if base_url == "custom" or not base_url:
        if "messages" in path or "inboxes" in path:
            return {"messages": []}
        return {}

    url = base_url.rstrip("/") + "/api" + path
    try:
        req = urllib.request.Request(url, method=method)
        req.add_header("X-API-Key", api_key)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        req.add_header("Accept", "application/json, */*")
        if host_header:
            req.add_header("Host", host_header)
        elif "localhost" in base_url or "127.0.0.1" in base_url:
            req.add_header("Host", "ammail.klipers.site")
        if data:
            req.data = json.dumps(data).encode()
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception:
        pass
    return None

# ── OTP Verification Code Poller ───────────────────────────────────────────────
def get_verification_code(email_addr: str, max_retries: int = 20, delay: float = 3.0, proxies: dict = None, ammail_base_url: str = None, ammail_api_key: str = None) -> str:
    domain = email_addr.split("@")[1].lower() if "@" in email_addr else ""
    configs = load_config_domains()
    configured_domains = [cfg.get("domain", "").lower() for cfg in configs]
    
    is_custom = domain in configured_domains or (ammail_base_url and ammail_base_url != "custom")
    
    if is_custom:
        username = email_addr.split("@")[0]
        otp_regex = re.compile(r"\b\d{6}\b")
        
        for poll_i in range(max_retries):
            time.sleep(delay)
            print(json.dumps({"step": f"Waiting for verification code OTP from custom email... (Try {poll_i+1}/{max_retries})"}), flush=True)
            
            try:
                msgs_resp = ammail_request(ammail_base_url, ammail_api_key, f"/inboxes/{urllib.parse.quote(username)}/messages", email=email_addr)
                msgs_list = msgs_resp.get("messages", []) if isinstance(msgs_resp, dict) else (msgs_resp if isinstance(msgs_resp, list) else [])
                for msg in msgs_list:
                    from_name = str(msg.get('from', '')).lower()
                    subject = str(msg.get('subject', '')).lower()
                    
                    if 'openai' in from_name or 'openai' in subject or 'chatgpt' in subject:
                        mid = str(msg.get('id', ''))
                        
                        try:
                            full = ammail_request(ammail_base_url, ammail_api_key, f"/messages/{urllib.parse.quote(mid)}", email=email_addr)
                            msg_body = full.get("message", full) if isinstance(full, dict) else {}
                            
                            html_content = msg_body.get('body','') or msg_body.get('html','') or msg_body.get('text','') or full.get('body','') or msg.get('snippet','')
                            if html_content:
                                soup_body = BeautifulSoup(html_content, "html.parser")
                                for script in soup_body(["script", "style"]):
                                    script.extract()
                                body_text = soup_body.get_text()
                                
                                matches = otp_regex.findall(body_text)
                                if matches:
                                    for m in matches:
                                        if m != "177010":
                                            return m
                        except Exception:
                            pass
            except Exception:
                pass
                
        raise Exception(f"Failed to get verification code from custom email after {max_retries} retries")

    else:
        username, domain = email_addr.split("@")[0], email_addr.split("@")[1]
        otp_regex = re.compile(r"\b\d{6}\b")
        session = requests.Session(impersonate="chrome110", proxies=proxies)
        url = f"https://generator.email/{domain}/{username}"
        
        for i in range(max_retries):
            try:
                headers = {
                    "Cookie": f"surl={domain}/{username}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
                }
                resp = session.get(url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    time.sleep(delay)
                    continue
                    
                soup = BeautifulSoup(resp.text, "html.parser")
                elements = soup.select("#email-table > div.e7m.list-group-item.list-group-item-info > div.e7m.subj_div_45g45gg")
                for el in elements:
                    text = el.get_text().strip()
                    matches = otp_regex.findall(text)
                    if matches:
                        code = matches[0]
                        if code != "177010":
                            return code
                            
                for script in soup(["script", "style"]):
                    script.extract()
                text = soup.get_text()
                matches = otp_regex.findall(text)
                if matches:
                    for code in matches:
                        if code != "177010":
                            return code
            except Exception:
                pass
            time.sleep(delay)
            
        raise Exception(f"Failed to get verification code after {max_retries} retries")

# ── ChatGPT Registration Client ────────────────────────────────────────────────
class ChatGPTRegisterClient:
    def __init__(self, proxy: str = None, tag: str = "", worker_id: int = 1, ammail_base_url: str = None, ammail_api_key: str = None):
        self.proxy = proxy
        self.tag = tag
        self.worker_id = worker_id
        self.device_id = str(uuid.uuid4())
        self.ammail_base_url = ammail_base_url
        self.ammail_api_key = ammail_api_key
        
        self.proxies = None
        if proxy:
            self.proxies = {"http": proxy, "https": proxy}
            
        self.session = requests.Session(impersonate="chrome110", proxies=self.proxies)
        self.session.cookies.set("oai-did", self.device_id, domain="chatgpt.com", path="/")
        
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        self.sec_ch_ua = '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"'
        self.impersonate = "chrome110"
        
    def log_step(self, step: str, status: int = 200):
        ts = time.strftime("%H:%M:%S")
        print(json.dumps({"step": f"[{ts}] [W{self.worker_id}] [{self.tag}] {step} | {status}"}), flush=True)

    def print_msg(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        print(json.dumps({"step": f"[{ts}] [W{self.worker_id}] [{self.tag}] {msg}"}), flush=True)

    def do_request(self, method: str, url: str, headers: dict = None, data = None, json_data = None):
        headers = headers or {}
        if "User-Agent" not in headers:
            headers["User-Agent"] = self.ua
        if "Accept" not in headers:
            headers["Accept"] = "*/*"
        if "Accept-Language" not in headers:
            headers["Accept-Language"] = "en-US,en;q=0.9"
        if "sec-ch-ua" not in headers:
            headers["sec-ch-ua"] = self.sec_ch_ua
        if "sec-ch-ua-mobile" not in headers:
            headers["sec-ch-ua-mobile"] = "?0"
        if "sec-ch-ua-platform" not in headers:
            headers["sec-ch-ua-platform"] = '"Windows"'
            
        return self.session.request(method, url, headers=headers, data=data, json=json_data, timeout=30)

    def visit_homepage(self) -> bool:
        for retry in range(3):
            try:
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1"
                }
                resp = self.do_request("GET", "https://chatgpt.com/", headers=headers)
                self.log_step(f"Visit Homepage (Try {retry+1})", resp.status_code)
                if resp.status_code in [200, 302, 307]:
                    return True
            except Exception as e:
                self.log_step(f"Visit Homepage Error (Try {retry+1}): {e}", 500)
            time.sleep(1.0)
        raise Exception("Failed to visit homepage after 3 retries")

    def get_csrf(self) -> str:
        headers = {
            "Accept": "application/json",
            "Referer": "https://chatgpt.com/"
        }
        resp = self.do_request("GET", "https://chatgpt.com/api/auth/csrf", headers=headers)
        self.log_step("Get CSRF", resp.status_code)
        if resp.status_code != 200:
            raise Exception(f"Failed to get CSRF (status: {resp.status_code})")
        data = resp.json()
        csrf = data.get("csrfToken")
        if not csrf:
            raise Exception("CSRF Token not found in response")
        return csrf

    def signin(self, email: str, csrf: str) -> str:
        signin_url = "https://chatgpt.com/api/auth/signin/openai"
        params = {
            "prompt": "login",
            "ext-oai-did": self.device_id,
            "auth_session_logging_id": str(uuid.uuid4()),
            "screen_hint": "login_or_signup",
            "login_hint": email
        }
        
        query_str = urllib.parse.urlencode(params)
        full_url = f"{signin_url}?{query_str}"
        
        form_data = {
            "callbackUrl": "https://chatgpt.com/",
            "csrfToken": csrf,
            "json": "true"
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Referer": "https://chatgpt.com/",
            "Origin": "https://chatgpt.com"
        }
        
        encoded_data = urllib.parse.urlencode(form_data)
        resp = self.do_request("POST", full_url, headers=headers, data=encoded_data)
        self.log_step("Signin", resp.status_code)
        if resp.status_code != 200:
            raise Exception(f"Signin post failed (status: {resp.status_code})")
        
        data = resp.json()
        auth_url = data.get("url")
        if not auth_url:
            raise Exception("Authorize URL not found in signin response")
        return auth_url

    def authorize(self, auth_url: str) -> str:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://chatgpt.com/",
            "Upgrade-Insecure-Requests": "1"
        }
        resp = self.do_request("GET", auth_url, headers=headers)
        self.log_step("Authorize", resp.status_code)
        return resp.url

    def register(self, email: str, password: str) -> tuple:
        reg_url = "https://auth.openai.com/api/accounts/user/register"
        payload = {
            "username": email,
            "password": password
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": "https://auth.openai.com/create-account/password",
            "Origin": "https://auth.openai.com"
        }
        
        for k, v in make_trace_headers().items():
            headers[k] = v
            
        resp = self.do_request("POST", reg_url, headers=headers, json_data=payload)
        self.log_step("Register", resp.status_code)
        
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
            
        return resp.status_code, data

    def send_otp(self) -> tuple:
        otp_url = "https://auth.openai.com/api/accounts/email-otp/send"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://auth.openai.com/create-account/password",
            "Upgrade-Insecure-Requests": "1"
        }
        resp = self.do_request("GET", otp_url, headers=headers)
        self.log_step("Send OTP", resp.status_code)
        
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
            
        return resp.status_code, data

    def validate_otp(self, code: str) -> tuple:
        val_url = "https://auth.openai.com/api/accounts/email-otp/validate"
        payload = {"code": code}
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": "https://auth.openai.com/email-verification",
            "Origin": "https://auth.openai.com"
        }
        
        for k, v in make_trace_headers().items():
            headers[k] = v
            
        resp = self.do_request("POST", val_url, headers=headers, json_data=payload)
        self.log_step(f"Validate OTP [{code}]", resp.status_code)
        
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
            
        return resp.status_code, data

    def create_account(self, name: str, birthdate: str) -> tuple:
        create_url = "https://auth.openai.com/api/accounts/create_account"
        payload = {
            "name": name,
            "birthdate": birthdate
        }
        
        generator = SentinelTokenGenerator(self.device_id, self.ua)
        self.print_msg("Building Sentinel Proof-of-Work Token...")
        
        try:
            challenge_payload = {
                "p": generator.generate_requirements_token(),
                "id": self.device_id,
                "flow": "create_account"
            }
            
            sentinel_req_headers = {
                "Content-Type": "text/plain;charset=UTF-8",
                "Referer": "https://sentinel.openai.com/sentinel/20260124ceb8/frame.html",
                "Origin": "https://sentinel.openai.com",
                "oai-device-id": self.device_id,
                "oai-language": "en-US"
            }
            
            resp_sentinel = self.do_request("POST", "https://sentinel.openai.com/backend-api/sentinel/req", headers=sentinel_req_headers, json_data=challenge_payload)
            if resp_sentinel.status_code != 200:
                raise Exception(f"Sentinel req failed: {resp_sentinel.status_code}")
                
            challenge = resp_sentinel.json()
            c_val = challenge.get("token")
            if not c_val:
                raise Exception("Invalid sentinel challenge token")
                
            pow_data = challenge.get("proofofwork", {})
            required = pow_data.get("required", False)
            seed = pow_data.get("seed", "")
            
            if required and seed:
                difficulty = pow_data.get("difficulty", "0")
                p_val = generator.generate_token(seed, difficulty)
            else:
                p_val = generator.generate_requirements_token()
                
            token_data = {
                "p": p_val,
                "t": "",
                "c": c_val,
                "id": self.device_id,
                "flow": "create_account"
            }
            sentinel_token = json.dumps(token_data, separators=(',', ':'))
        except Exception as e:
            raise Exception(f"failed to get sentinel auth token: {e}")
            
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": "https://auth.openai.com/about-you",
            "Origin": "https://auth.openai.com",
            "openai-sentinel-token": sentinel_token
        }
        
        for k, v in make_trace_headers().items():
            headers[k] = v
            
        resp = self.do_request("POST", create_url, headers=headers, json_data=payload)
        self.log_step("Create Account", resp.status_code)
        
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
            
        return resp.status_code, data

    def callback(self, cb_url: str) -> tuple:
        if not cb_url:
            raise Exception("empty callback url")
            
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1"
        }
        resp = self.do_request("GET", cb_url, headers=headers)
        self.log_step("Callback", resp.status_code)
        return resp.status_code, {"final_url": resp.url}

    def run_register(self, email_addr: str, password: str, name: str, birthdate: str) -> bool:
        self.print_msg("Starting registration flow...")
        self.visit_homepage()
        time.sleep(random.uniform(0.3, 0.8))
        
        csrf = self.get_csrf()
        time.sleep(random.uniform(0.2, 0.5))
        
        auth_url = self.signin(email_addr, csrf)
        time.sleep(random.uniform(0.3, 0.8))
        
        final_url = self.authorize(auth_url)
        time.sleep(random.uniform(0.3, 0.8))
        
        parsed_url = urllib.parse.urlparse(final_url)
        final_path = parsed_url.path
        
        need_otp = False
        
        if "create-account/password" in final_path:
            time.sleep(random.uniform(0.5, 1.0))
            status, data = self.register(email_addr, password)
            if status != 200:
                if status == 400 and "unsupported_email" in json.dumps(data):
                    raise Exception(f"unsupported_email: {email_addr}")
                raise Exception(f"register failed ({status}): {data}")
            time.sleep(random.uniform(0.3, 0.8))
            self.send_otp()
            need_otp = True
        elif "email-verification" in final_path or "email-otp" in final_path:
            self.print_msg("Jump to OTP verification stage")
            need_otp = True
        elif "about-you" in final_path:
            self.print_msg("Jump to fill information stage")
            time.sleep(random.uniform(0.5, 1.0))
            status, data = self.create_account(name, birthdate)
            if status != 200:
                raise Exception(f"create account failed ({status}): {data}")
            time.sleep(random.uniform(0.3, 0.5))
            
            cb_url = data.get("continue_url") or data.get("url") or data.get("redirect_url")
            self.callback(cb_url)
            return True
        elif "callback" in final_path or "chatgpt.com" in final_url:
            self.print_msg("Account registration completed")
            return True
        else:
            self.print_msg(f"Unknown jump: {final_url}")
            self.register(email_addr, password)
            self.send_otp()
            need_otp = True
            
        if need_otp:
            self.print_msg("Waiting for verification code OTP from email...")
            otp_code = get_verification_code(email_addr, 20, 3.0, self.proxies, self.ammail_base_url, self.ammail_api_key)
            time.sleep(random.uniform(0.3, 0.8))
            
            status, data = self.validate_otp(otp_code)
            if status != 200:
                self.print_msg("Verification code failed, retrying...")
                self.send_otp()
                time.sleep(random.uniform(1.0, 2.0))
                otp_code = get_verification_code(email_addr, 10, 3.0, self.proxies, self.ammail_base_url, self.ammail_api_key)
                time.sleep(random.uniform(0.3, 0.8))
                status, data = self.validate_otp(otp_code)
                if status != 200:
                    raise Exception(f"verification code failed after retry ({status}): {data}")
                    
        time.sleep(random.uniform(0.5, 1.5))
        status, data = self.create_account(name, birthdate)
        if status != 200:
            raise Exception(f"create account failed ({status}): {data}")
            
        time.sleep(random.uniform(0.2, 0.5))
        cb_url = data.get("continue_url") or data.get("url") or data.get("redirect_url")
        self.callback(cb_url)
        return True

# ── Main Entrypoint ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--default-domain", default="")
    parser.add_argument("--proxy-server", default="")
    parser.add_argument("--proxy-user", default="")
    parser.add_argument("--proxy-pass", default="")
    parser.add_argument("--output-file", default="results.txt")
    parser.add_argument("--worker-id", type=int, default=1)
    parser.add_argument("--tag", default="1/1")
    parser.add_argument("--ammail-base-url", default="custom")
    parser.add_argument("--ammail-api-key", default="custom")
    args = parser.parse_args()

    proxy = None
    if args.proxy_server:
        proxy_url = args.proxy_server
        if args.proxy_user and args.proxy_pass:
            parsed = urllib.parse.urlparse(args.proxy_server)
            netloc = f"{args.proxy_user}:{args.proxy_pass}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            proxy_url = urllib.parse.urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        proxy = proxy_url

    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        fake = Faker()
        
        email_addr = args.email
        if not email_addr:
            print(json.dumps({"step": f"Generating temp email using domain: {args.default_domain or '(generator.email)'}..."}), flush=True)
            email_addr = create_temp_email(args.default_domain, proxies={"http": proxy, "https": proxy} if proxy else None)
            
        password = args.password
        if not password:
            password = generate_password(14)
            
        name = f"{fake.first_name()} {fake.last_name()}"
        birthdate = random_birthdate()

        client = ChatGPTRegisterClient(proxy=proxy, tag=args.tag, worker_id=args.worker_id, ammail_base_url=args.ammail_base_url, ammail_api_key=args.ammail_api_key)
        client.print_msg(f"Targeting: {email_addr} | Password: {password}")
        
        success = client.run_register(email_addr, password, name, birthdate)
        if success:
            with open(args.output_file, "a") as f:
                f.write(f"{email_addr}|{password}\n")
                
            print(json.dumps({
                "status": "success",
                "email": email_addr,
                "password": password
            }), flush=True)
        else:
            print(json.dumps({
                "status": "error",
                "error": "Registration flow completed but success was not verified"
            }), flush=True)
            
    except Exception as e:
        err_str = str(e)
        # Check if email domain blacklist is needed
        if "unsupported_email" in err_str:
            parts = email_addr.split("@")
            if len(parts) == 2:
                add_blacklist_domain(parts[1])
                
        print(json.dumps({
            "status": "error",
            "error": err_str
        }), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
