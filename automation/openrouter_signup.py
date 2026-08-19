"""OpenRouter account auto-signup via Camoufox (anti-fingerprint) + Ammail email verification.

Flow:
  1. Buka https://openrouter.ai/
  2. Klik "Get API Key" -> diarahkan ke /sign-in atau /sign-up
  3. Klik "Sign up" jika di halaman sign-in, atau langsung di sign-up
  4. Fill email + password
  5. Centang checkbox "I agree"
  6. Klik Continue
  7. Solve Cloudflare Turnstile (via 2Captcha atau click)
  8. Tunggu email verifikasi dari openrouter (clerk), ambil link
  9. Buka link verifikasi di browser yang sama
  10. Di halaman onboarding -> klik Next
  11. Ambil API Key (sk-or-v1-...)
  12. Output JSON success

Outputs JSON lines to stdout:
  {"step": "..."} — progress update
  {"status": "success", "api_key": "...", "email": "...", "password": "..."} — final result
  {"status": "error", "error": "..."} — failure
"""

import sys
import json
import argparse
import time
import random
import string
import re
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
import os


# ── Random email & password generator ──────────────────────────────────────────
ADJECTIVES = ["swift", "cool", "dark", "bright", "lucky", "silent", "bold", "quick", "sharp", "clean", "sleek", "smart"]
NOUNS      = ["fox", "wolf", "hawk", "bear", "lion", "byte", "node", "core", "link", "star", "wave", "gear"]

def random_username():
    adj  = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    num  = random.randint(10, 9999)
    return f"{adj}{noun}{num}"

def random_password(length=12):
    """Generate password min 8 char, mengandung huruf besar, kecil, angka, simbol."""
    length = max(length, 8)
    chars_lower  = string.ascii_lowercase
    chars_upper  = string.ascii_uppercase
    chars_digits = string.digits
    chars_symbol = "!@#$%^&*"
    # Pastikan minimal 1 dari setiap kategori
    pwd = [
        random.choice(chars_lower),
        random.choice(chars_upper),
        random.choice(chars_digits),
        random.choice(chars_symbol),
    ]
    all_chars = chars_lower + chars_upper + chars_digits + chars_symbol
    pwd += [random.choice(all_chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return "".join(pwd)

def pick_random_domain():
    """Ambil domain random dari config.json, fallback ke generator.email domains."""
    configs = load_config_domains()
    if configs:
        cfg = random.choice(configs)
        domain = cfg.get("domain", "")
        if domain:
            return domain
    # Fallback domains
    fallback = ["guerrillamail.com", "sharklasers.com", "guerrillamailblock.com"]
    return random.choice(fallback)

def generate_random_email(domain=None):
    """Generate email random. Jika domain tidak diisi, pakai config.json atau fallback."""
    if not domain:
        domain = pick_random_domain()
    username = random_username()
    return f"{username}@{domain}", username


def emit(obj):
    print(json.dumps(obj), flush=True)


def log_step(msg):
    emit({"step": msg})


def die(msg, code=1):
    emit({"status": "error", "error": msg})
    sys.exit(code)


# ── Ammail helpers (diambil dari cloudflare_signup.py) ─────────────────────────
def load_config_domains():
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
            except Exception as e:
                log_step(f"Error loading config.json from {p}: {e}")
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
    except Exception as e:
        log_step(f"Custom email request error: {e}")
    return None


def ammail_request(base_url, api_key, path, method="GET", data=None, host_header=None, email=None):
    email_ctx = email
    if not email_ctx:
        for arg in sys.argv:
            if arg.startswith("--email="):
                email_ctx = arg.split("=", 1)[1]
                break

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


def create_ammail_inbox(base_url, api_key, email):
    try:
        alias, domain = email.split("@", 1)
        ammail_request(base_url, api_key, "/inboxes", method="POST",
                       data={"alias": alias, "domain": domain})
    except Exception:
        pass


# ── 2Captcha Turnstile solver ───────────────────────────────────────────────────
OPENROUTER_SIGNUP_URL = "https://openrouter.ai/sign-up"

def get_turnstile_sitekey(page, fallback=None):
    """Scrape the actual Turnstile sitekey from page."""
    try:
        sitekey = page.evaluate(
            r"""
            () => {
                // Method 1: data-sitekey attribute
                const el = document.querySelector('[data-sitekey]');
                if (el) return el.getAttribute('data-sitekey');
                // Method 2: inside Turnstile iframe src
                for (const iframe of document.querySelectorAll('iframe')) {
                    const src = iframe.src || '';
                    const m = src.match(/[?&]sitekey=([^&]+)/);
                    if (m) return decodeURIComponent(m[1]);
                }
                // Method 3: window.__CF$cv$params
                try {
                    const raw = JSON.stringify(window.__CF$cv$params || {});
                    const m2 = raw.match(/sitekey["']?\s*:\s*["']([^"']+)["']/);
                    if (m2) return m2[1];
                } catch(e) {}
                return null;
            }
        """
        )
        if sitekey and len(sitekey.strip()) > 10:
            log_step(f"Sitekey ditemukan dari halaman: {sitekey}")
            return sitekey.strip()
    except Exception as e:
        log_step(f"get_turnstile_sitekey error: {e}")
    return fallback


def solve_turnstile_2captcha(api_key_2captcha, page_url, sitekey, timeout=120):
    """Submit Turnstile ke 2Captcha dan tunggu token solusi."""
    log_step("Mengirim Turnstile ke 2Captcha...")
    try:
        submit_data = {
            "key": api_key_2captcha,
            "method": "turnstile",
            "sitekey": sitekey,
            "pageurl": page_url,
            "json": 1,
        }
        encoded = urllib.parse.urlencode(submit_data).encode()
        req = urllib.request.Request("https://2captcha.com/in.php", data=encoded)
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        if not resp.get("status") == 1:
            log_step(f"2Captcha submit error: {resp}")
            return None
        task_id = resp.get("request")
        log_step(f"2Captcha task submitted: {task_id}")

        deadline = time.time() + timeout
        time.sleep(15)
        while time.time() < deadline:
            res_url = f"https://2captcha.com/res.php?key={api_key_2captcha}&action=get&id={task_id}&json=1"
            req2 = urllib.request.Request(res_url)
            with urllib.request.urlopen(req2, timeout=15) as r2:
                res = json.loads(r2.read())
            if res.get("status") == 1:
                token = res.get("request")
                log_step("2Captcha Turnstile solved!")
                return token
            if res.get("request") == "ERROR_CAPTCHA_UNSOLVABLE":
                log_step("2Captcha: captcha unsolvable")
                return None
            time.sleep(5)
        log_step("2Captcha Turnstile timeout")
        return None
    except Exception as e:
        log_step(f"2Captcha error: {e}")
        return None


def is_turnstile_iframe_present(page) -> bool:
    """Cek apakah ada iframe Cloudflare Turnstile di halaman (embedded di form)."""
    try:
        for f in page.frames:
            url = f.url or ""
            if "challenges.cloudflare.com" in url or "turnstile" in url:
                return True
    except Exception:
        pass
    # Fallback: cek via selector
    for sel in [
        "iframe[src*='challenges.cloudflare.com']",
        "iframe[src*='turnstile']",
        ".cf-turnstile",
        "[data-sitekey]",
        "iframe[title*='challenge' i]",
        "iframe[title*='turnstile' i]",
    ]:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            continue
    # Cek via text content (widget yang sudah render tapi src belum load)
    try:
        content = page.content()
        if "challenges.cloudflare.com" in content or "cf-turnstile" in content or "turnstile" in content.lower():
            return True
    except Exception:
        pass
    # Cek via teks yang terlihat user ("Verify you are human")
    for txt_sel in [
        "text=Verify you are human",
        "text=verify you are human",
        "*:has-text('Verify you are human')",
    ]:
        try:
            loc = page.locator(txt_sel).first
            if loc.count() > 0:
                return True
        except Exception:
            continue
    return False


def wait_for_turnstile_appear(page, timeout=6.0) -> bool:
    """Tunggu hingga Turnstile iframe/widget muncul di halaman (max timeout detik)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_turnstile_iframe_present(page):
            return True
        time.sleep(0.5)
    return False


def is_on_turnstile_page(page) -> bool:
    """Cek apakah kita di halaman Cloudflare challenge penuh (bukan embedded)."""
    try:
        title = page.title() or ""
        if "just a moment" in title.lower() or "security verification" in title.lower():
            return True
    except Exception:
        pass
    for sel in ["text=Just a moment", "text=Verifying you are human", "#challenge-form", "#cf-challenge-running"]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible(timeout=300):
                return True
        except Exception:
            continue
    return False


def is_turnstile_solved(page) -> bool:
    """Cek apakah Turnstile sudah solved (ada token non-kosong)."""
    try:
        result = page.evaluate(r"""
            () => {
                // Cek input hidden cf-turnstile-response
                const el = document.querySelector(
                    'input[name="cf-turnstile-response"], input[name="g-recaptcha-response"]'
                );
                if (el && el.value && el.value.length > 20) return true;
                // Cek via window.turnstile
                if (window.turnstile) {
                    try {
                        const resp = window.turnstile.getResponse();
                        if (resp && resp.length > 20) return true;
                    } catch(e) {}
                }
                return false;
            }
        """)
        return bool(result)
    except Exception:
        return False


def try_click_turnstile_checkbox(page) -> bool:
    """Klik checkbox Turnstile di dalam iframe. Berbagai metode."""
    # Metode 1: Lewat frame object
    target_frame = None
    try:
        for f in page.frames:
            url = f.url or ""
            if "challenges.cloudflare.com" in url or "turnstile" in url:
                target_frame = f
                break
    except Exception:
        pass

    if target_frame:
        # Coba selector checkbox
        for cb_sel in ["input[type='checkbox']", "[role='checkbox']", "div.ctp-checkbox-label", "label"]:
            try:
                box = target_frame.locator(cb_sel).first
                if box.count() > 0 and box.is_visible(timeout=2000):
                    box.click(timeout=3000, force=True)
                    time.sleep(0.5)
                    log_step(f"Turnstile klik via frame selector: {cb_sel}")
                    return True
            except Exception:
                continue

        # Coba klik koordinat bounding box iframe
        try:
            handle = target_frame.frame_element()
            bbox = handle.bounding_box() if handle else None
            if bbox and bbox["width"] > 0:
                # Posisi checkbox ada di kiri, vertikal tengah
                x = bbox["x"] + 24
                y = bbox["y"] + (bbox["height"] / 2)
                page.mouse.move(x, y, steps=15)
                time.sleep(random.uniform(0.2, 0.5))
                page.mouse.click(x, y)
                return True
        except Exception as e:
            log_step(f"Bounding box click error: {e}")

    # Metode 2: frame_locator
    for iframe_sel in [
        "iframe[src*='challenges.cloudflare.com']",
        "iframe[src*='turnstile']",
        "iframe[title*='turnstile' i]",
        "iframe[title*='challenge' i]",
    ]:
        for cb_sel in ["input[type='checkbox']", "[role='checkbox']", "div.ctp-checkbox-label"]:
            try:
                box = page.frame_locator(iframe_sel).locator(cb_sel).first
                if box.count() > 0:
                    box.click(timeout=3000, force=True)
                    log_step(f"Turnstile klik via frame_locator ({iframe_sel} > {cb_sel})")
                    return True
            except Exception:
                continue

    log_step("Warning: Turnstile iframe/checkbox tidak ditemukan")
    return False


def wait_for_turnstile_solved(page, timeout=90.0, captcha_key=None) -> bool:
    """
    Tunggu Turnstile selesai (token muncul).
    - Jika captcha_key ada: coba 2Captcha dulu
    - Fallback: klik checkbox berkali-kali
    Bekerja untuk embedded Turnstile (di dalam form Clerk), bukan hanya full-page challenge.
    """
    if not is_turnstile_iframe_present(page) and not is_on_turnstile_page(page):
        return True  # Tidak ada Turnstile, lanjut

    log_step("Turnstile terdeteksi, menyelesaikan...")

    # Coba 2Captcha
    if captcha_key:
        sitekey = get_turnstile_sitekey(page)
        if sitekey:
            token = solve_turnstile_2captcha(captcha_key, page.url, sitekey, timeout=120)
            if token:
                try:
                    page.evaluate(f"""
                    (function() {{
                        // Inject ke semua input
                        var inputs = document.querySelectorAll(
                            'input[name="cf-turnstile-response"], input[name="g-recaptcha-response"]'
                        );
                        inputs.forEach(function(el) {{ el.value = '{token}'; }});
                        // Trigger via window.turnstile callback
                        if (window.turnstile) {{
                            try {{
                                var cb = window.turnstile._callbacks || [];
                                if (typeof cb === 'function') cb('{token}');
                            }} catch(e) {{}}
                        }}
                        // Coba dispatch event
                        document.dispatchEvent(new Event('cf-turnstile-success'));
                    }})();
                    """)
                    log_step("Turnstile token injected via 2Captcha!")
                    time.sleep(2)
                    if is_turnstile_solved(page):
                        return True
                except Exception as e:
                    log_step(f"Token injection error: {e}")

    # Fallback: klik checkbox berkali-kali
    deadline = time.time() + timeout
    click_attempts = 0
    next_click_at = time.time() + 1.0

    while time.time() < deadline:
        if is_turnstile_solved(page):
            log_step("Turnstile solved!")
            return True
        if not is_on_turnstile_page(page) and not is_turnstile_iframe_present(page):
            log_step("Turnstile hilang dari halaman (solved/skip)")
            return True

        now = time.time()
        if click_attempts < 10 and now >= next_click_at:
            click_attempts += 1
            clicked = try_click_turnstile_checkbox(page)
            log_step(f"Turnstile click attempt {click_attempts}/10: {'berhasil' if clicked else 'gagal'}")
            next_click_at = now + 8.0

        time.sleep(1.0)

    log_step("Turnstile timeout!")
    return False


def wait_for_cf_clearance(page, timeout=45.0):
    if not is_on_turnstile_page(page):
        return True
    deadline = time.time() + timeout
    click_attempts = 0
    next_click_at = time.time() + 4.0
    while time.time() < deadline:
        time.sleep(2.0)
        if not is_on_turnstile_page(page):
            log_step("Turnstile selesai!")
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            return True
        now = time.time()
        if click_attempts < 5 and now >= next_click_at:
            click_attempts += 1
            try_click_turnstile_checkbox(page)
            next_click_at = now + 8.0
            time.sleep(2.0)
    return False


# ── Tunggu email verifikasi OpenRouter dari Ammail ─────────────────────────────
def wait_for_openrouter_verify_email(base_url, api_key, email, timeout=60):
    """Poll Ammail sampai dapat link verifikasi dari clerk.openrouter.ai"""
    alias = email.split("@")[0]
    deadline = time.time() + timeout
    seen_ids = set()

    while time.time() < deadline:
        try:
            data = ammail_request(base_url, api_key, f"/inboxes/{urllib.parse.quote(alias)}/messages", email=email)
            messages = data.get("messages", []) if isinstance(data, dict) else []
            for msg in messages:
                msg_id = str(msg.get("id", ""))
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)
                from_addr = str(msg.get("from", "")).lower()
                subject = str(msg.get("subject", "")).lower()

                is_or_email = (
                    "openrouter" in from_addr or
                    "openrouter" in subject or
                    "sign up" in subject or
                    "signup" in subject or
                    "verify" in subject or
                    "clerk" in from_addr
                )
                if is_or_email:
                    try:
                        full = ammail_request(base_url, api_key, f"/messages/{urllib.parse.quote(msg_id)}", email=email)
                        msg_body = full.get("message", full) if isinstance(full, dict) else {}
                        body = (msg_body.get("html", "") or
                                msg_body.get("body", "") or
                                msg_body.get("text", "") or
                                msg.get("snippet", ""))
                    except Exception:
                        body = msg.get("snippet", "")

                    # Cari link clerk.openrouter.ai/v1/verify
                    patterns = [
                        r'https://clerk\.openrouter\.ai/v1/verify[^\s\'"<>]+',
                        r'https://[^\s\'"<>]*openrouter[^\s\'"<>]*verify[^\s\'"<>]*',
                        r'https://[^\s\'"<>]*clerk[^\s\'"<>]*verify[^\s\'"<>]*',
                    ]
                    for pat in patterns:
                        links = re.findall(pat, body)
                        if links:
                            # Clean HTML entities
                            link = links[0].rstrip(".").replace("&amp;", "&")
                            log_step(f"Link verifikasi ditemukan!")
                            return link
        except Exception as e:
            log_step(f"Ammail poll error: {e}")
        time.sleep(5)

    return None


# ── Extract API Key dari halaman workspace/keys ────────────────────────────────
# Pattern API key OpenRouter: sk-or-v1-<hex chars + dashes>
OR_KEY_PATTERN = re.compile(r'sk-or-v1-[a-zA-Z0-9\-_]+')

def extract_api_key_from_page(page, captured_keys=None):
    """Ekstrak API key (sk-or-v1-...) dari halaman workspace/keys OpenRouter."""
    log_step("Mengekstrak API Key dari halaman...")

    # Prioritas 1: dari network request yang sudah dicapture
    if captured_keys:
        for k in captured_keys:
            if k.startswith("sk-or-v1-") and len(k) > 20:
                # log_step(f"API Key dari network capture: {k}")
                return k

    try:
        # Tunggu halaman workspace/keys dimuat
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(3)

        # Prioritas 2: cari di JS variables (OpenRouter sering simpan di window/store)
        api_key = page.evaluate(r"""
            () => {
                // Cari di semua text content dengan pattern sk-or-v1-
                const allText = document.body.innerText || '';
                const m = allText.match(/sk-or-v1-[a-zA-Z0-9\-_]+/);
                if (m) return m[0];

                // Cari di value semua input (termasuk hidden)
                for (const inp of document.querySelectorAll('input')) {
                    const v = inp.value || '';
                    const km = v.match(/sk-or-v1-[a-zA-Z0-9\-_]+/);
                    if (km) return km[0];
                }

                // Cari di data attributes
                for (const el of document.querySelectorAll('[data-key],[data-value],[data-api-key],[data-token]')) {
                    for (const attr of ['data-key','data-value','data-api-key','data-token']) {
                        const v = el.getAttribute(attr) || '';
                        const km = v.match(/sk-or-v1-[a-zA-Z0-9\-_]+/);
                        if (km) return km[0];
                    }
                }

                // Cari di code/pre/span dengan class key/token
                for (const el of document.querySelectorAll('code,pre,span,p,div')) {
                    const t = el.innerText || el.textContent || '';
                    const km = t.match(/sk-or-v1-[a-zA-Z0-9\-_]+/);
                    if (km) return km[0];
                }

                // Cari di seluruh innerHTML (termasuk hidden)
                const html = document.documentElement.innerHTML;
                const hm = html.match(/sk-or-v1-[a-zA-Z0-9\-_]+/);
                if (hm) return hm[0];

                return null;
            }
        """)

        if api_key:
            m = OR_KEY_PATTERN.search(api_key)
            if m:
                key = m.group(0)
                log_step(f"API Key ditemukan dari DOM: {key}")
                return key

        # Prioritas 3: cari di page.content() HTML source
        content = page.content()
        m = OR_KEY_PATTERN.search(content)
        if m:
            key = m.group(0)
            log_step(f"API Key ditemukan di HTML source: {key}")
            return key

    except Exception as e:
        log_step(f"extract_api_key_from_page error: {e}")
    return None


def check_proxy_alive(proxy_dict, timeout=10):
    """Test if the proxy is working by sending a fast request to a public API."""
    try:
        server = proxy_dict.get("server", "")
        if not server.startswith("http"):
            server = f"http://{server}"

        user = proxy_dict.get("username", "")
        pwd = proxy_dict.get("password", "")

        if user and pwd:
            parsed = urllib.parse.urlparse(server)
            proxy_url = f"{parsed.scheme}://{user}:{pwd}@{parsed.netloc}"
        else:
            proxy_url = server

        proxy_support = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
        opener = urllib.request.build_opener(proxy_support)
        req = urllib.request.Request("https://google.com", headers={'User-Agent': 'Mozilla/5.0'})
        with opener.open(req, timeout=timeout) as response:
            if response.status in (200, 301, 302, 403, 404):
                log_step(f"Proxy aktif: {parsed.netloc if 'parsed' in locals() else server}")
                return True
    except urllib.error.HTTPError:
        return True
    except Exception as e:
        log_step(f"Proxy check error: {e}")
    return False


# ── Main Signup Flow ────────────────────────────────────────────────────────────
def run_signup(args):
    email = args.email
    password = args.password
    proxy_server = args.proxy_server
    proxy_user = getattr(args, "proxy_user", "")
    proxy_pass = getattr(args, "proxy_pass", "")
    ammail_base_url = args.ammail_base_url
    ammail_api_key = args.ammail_api_key
    captcha_key = args.captcha_key
    headless = args.headless
    profiles_dir = getattr(args, "profiles_dir", None)

    # Import camoufox
    try:
        from camoufox.sync_api import Camoufox
    except ImportError:
        die("camoufox tidak terinstall. Jalankan: pip install camoufox && python -m camoufox fetch")

    # Build proxy config cleanly (prevent user:pass duplicate formatting)
    proxy_config = None
    if proxy_server:
        p_str = proxy_server if (proxy_server.startswith("http") or proxy_server.startswith("socks")) else f"http://{proxy_server}"
        parsed = urllib.parse.urlparse(p_str)
        clean_server = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            clean_server += f":{parsed.port}"

        user = parsed.username or proxy_user
        pwd = parsed.password or proxy_pass

        proxy_config = {"server": clean_server}
        if user and pwd:
            proxy_config["username"] = user
            proxy_config["password"] = pwd

        log_step("Menguji koneksi proxy...")
        if not check_proxy_alive(proxy_config):
            die("Proxy mati/Invalid IP - aborting untuk retry proxy baru", 3)

    # Profile dir
    profile_dir_path = None
    if profiles_dir:
        profile_dir_path = os.path.join(profiles_dir, "openrouter", email.replace("@", "_"))
        os.makedirs(profile_dir_path, exist_ok=True)

    # Create ammail inbox
    create_ammail_inbox(ammail_base_url, ammail_api_key, email)

    log_step("Memulai browser")

    camoufox_kwargs = {
        "headless": headless,
        "geoip": True,
    }
    if proxy_config:
        camoufox_kwargs["proxy"] = proxy_config

    with Camoufox(**camoufox_kwargs) as browser:
        context_kwargs = {}
        if profile_dir_path:
            context_kwargs["storage_state"] = None

        page = browser.new_page()

        # ── Setup network listener untuk capture API key dari Authorization header
        captured_keys = []

        def on_request(request):
            try:
                auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
                if auth.startswith("Bearer sk-or-v1-"):
                    key = auth.split(" ", 1)[1].strip()
                    if key not in captured_keys:
                        captured_keys.append(key)
                        log_step(f"API Key dicapture dari network")
            except Exception:
                pass

        def on_response(response):
            try:
                # Juga cek response body untuk key
                url = response.url
                if "openrouter.ai" in url and response.status == 200:
                    try:
                        body = response.body()
                        if body:
                            text = body.decode("utf-8", errors="ignore")
                            matches = OR_KEY_PATTERN.findall(text)
                            for k in matches:
                                if k not in captured_keys:
                                    captured_keys.append(k)
                                    # log_step(f"API Key dicapture dari response")
                    except Exception:
                        pass
            except Exception:
                pass

        page.on("request", on_request)
        page.on("response", on_response)

        try:
            # Step 1: Buka homepage OpenRouter
            log_step("Membuka https://openrouter.ai/...")
            page.goto("https://openrouter.ai/", wait_until="domcontentloaded", timeout=30000)
            wait_for_cf_clearance(page, timeout=30)
            time.sleep(random.uniform(1.5, 2.5))

            # Step 2: Klik "Get API Key"
            try:
                btn_get_api_key = page.locator("a:has-text('Get API Key'), button:has-text('Get API Key')").first
                if btn_get_api_key.is_visible(timeout=5000):
                    btn_get_api_key.click()
                    time.sleep(random.uniform(1.0, 2.0))
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception as e:
                log_step(f"Get API Key button not found, navigating directly: {e}")
                page.goto("https://openrouter.ai/sign-in?redirect_url=https%3A%2F%2Fopenrouter.ai%2Fworkspaces%2Fdefault%2Fkeys",
                         wait_until="domcontentloaded", timeout=30000)

            wait_for_cf_clearance(page, timeout=30)
            time.sleep(random.uniform(1.0, 2.0))

            current_url = page.url

            # Step 3: Jika di halaman sign-in, klik "Sign up"
            if "sign-in" in current_url or "sign-up" not in current_url:
                for signup_sel in [
                    "a:has-text('Sign up')",
                    "a:has-text('Sign Up')",
                    "a[href*='sign-up']",
                    "button:has-text('Sign up')",
                ]:
                    try:
                        signup_link = page.locator(signup_sel).first
                        if signup_link.is_visible(timeout=3000):
                            signup_link.click()
                            time.sleep(random.uniform(1.0, 2.0))
                            page.wait_for_load_state("domcontentloaded", timeout=15000)
                            break
                    except Exception:
                        continue

            current_url = page.url

            # Validasi URL sign-up
            if "sign-up" not in current_url:
                log_step(f"Warning: URL bukan halaman sign-up, current: {current_url}")

            wait_for_cf_clearance(page, timeout=20)
            time.sleep(random.uniform(0.5, 1.0))

            # Step 4: Fill email
            log_step("Mengisi email...")
            email_input_selectors = [
                "input[name='emailAddress']",
                "input[type='email']",
                "input[placeholder*='email' i]",
                "input[id*='email' i]",
                "input[autocomplete='email']",
            ]
            email_filled = False
            for sel in email_input_selectors:
                try:
                    inp = page.locator(sel).first
                    if inp.is_visible(timeout=3000):
                        inp.click()
                        time.sleep(0.2)
                        inp.fill(email)
                        email_filled = True
                        break
                except Exception:
                    continue

            if not email_filled:
                die("Tidak dapat menemukan input field email")

            time.sleep(random.uniform(0.3, 0.7))

            # Step 5: Fill password
            log_step("Mengisi password...")
            password_filled = False
            for sel in [
                "input[name='password']",
                "input[type='password']",
                "input[placeholder*='password' i]",
                "input[id*='password' i]",
            ]:
                try:
                    inp = page.locator(sel).first
                    if inp.is_visible(timeout=3000):
                        inp.click()
                        time.sleep(0.2)
                        inp.fill(password)
                        password_filled = True
                        break
                except Exception:
                    continue

            if not password_filled:
                die("Tidak dapat menemukan input field password")

            time.sleep(random.uniform(0.3, 0.7))

            # Step 6: Centang checkbox "I agree" jika ada
            for checkbox_sel in [
                "input[type='checkbox']",
                "input[name*='agree' i]",
                "input[id*='agree' i]",
                "label:has-text('agree') input",
                "[role='checkbox']",
            ]:
                try:
                    checkbox = page.locator(checkbox_sel).first
                    if checkbox.is_visible(timeout=2000):
                        is_checked = checkbox.is_checked()
                        if not is_checked:
                            checkbox.click()
                            log_step("Checkbox dicentang!")
                        else:
                            log_step("Checkbox sudah tercentang!")
                        time.sleep(random.uniform(0.3, 0.6))
                        break
                except Exception:
                    continue

            # # Step 6b: Handle Turnstile yang muncul di form SEBELUM Continue (Clerk pattern)
            # # Tunggu dulu 3 detik agar iframe sempat load setelah interaksi form
            # log_step("Menunggu Turnstile muncul...")
            # turnstile_found = wait_for_turnstile_appear(page, timeout=6.0)
            # if turnstile_found:
            #     log_step("Turnstile ditemukan sebelum Continue, menyelesaikan...")
            #     wait_for_turnstile_solved(page, timeout=90, captcha_key=captcha_key)
            #     time.sleep(random.uniform(1.0, 2.0))
            # else:
            #     log_step("Turnstile tidak terdeteksi sebelum Continue, lanjut...")
            #     time.sleep(1.0)

            # Step 7: Klik Continue
            continue_clicked = False
            for cont_sel in [
                "button:has-text('Continue')",
                "button[type='submit']:has-text('Continue')",
                "button:has-text('Sign up')",
                "button[type='submit']",
            ]:
                try:
                    btn = page.locator(cont_sel).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        continue_clicked = True
                        time.sleep(random.uniform(1.5, 2.5))
                        break
                except Exception:
                    continue

            if not continue_clicked:
                log_step("Warning: Tombol Continue tidak ditemukan, mencoba Enter...")
                try:
                    page.keyboard.press("Enter")
                    time.sleep(2)
                except Exception:
                    pass

            # Step 8: Handle Turnstile yang muncul SETELAH Continue
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            current_url = page.url

            # Beri waktu agar Turnstile muncul jika ada
            time.sleep(2.0)
            if is_turnstile_iframe_present(page) or is_on_turnstile_page(page):
                wait_for_turnstile_solved(page, timeout=90, captcha_key=captcha_key)

            # Tunggu redirect setelah captcha
            time.sleep(random.uniform(2.0, 3.0))
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            current_url = page.url

            # Step 9: Tunggu dan buka link verifikasi email
            log_step("Menunggu email verifikasi dari OpenRouter...")
            verify_link = wait_for_openrouter_verify_email(ammail_base_url, ammail_api_key, email, timeout=60)

            if not verify_link:
                die("Link verifikasi email tidak diterima dalam 1 menit")

            log_step(f"Membuka link verifikasi di browser...")
            page.goto(verify_link, wait_until="domcontentloaded", timeout=30000)
            wait_for_cf_clearance(page, timeout=30)
            time.sleep(random.uniform(2.0, 3.0))

            # Tunggu redirect ke workspace/keys atau onboarding
            try:
                page.wait_for_url(re.compile(r"openrouter\.ai/(workspaces|sign-up/verify|onboarding)"), timeout=20000)
            except Exception:
                pass

            current_url = page.url

            # Step 10: Handle onboarding - klik Next jika muncul
            if "workspaces" in current_url or "sign-up" in current_url or "onboarding" in current_url:
                # Handle "How will you be using OpenRouter?" onboarding
                for next_btn_sel in [
                    "button:has-text('Next')",
                    "button:has-text('Continue')",
                    "button:has-text('Get Started')",
                ]:
                    try:
                        btn = page.locator(next_btn_sel).first
                        if btn.is_visible(timeout=5000):
                            btn.click()
                            time.sleep(random.uniform(1.5, 2.5))

                            # Tunggu halaman API key muncul
                            try:
                                page.wait_for_load_state("networkidle", timeout=10000)
                            except Exception:
                                pass
                            break
                    except Exception:
                        continue

                current_url = page.url

            # Lanjutkan klik Next sampai API key muncul (max 5 kali)
            api_key_result = None
            for step in range(6):
                # Coba ekstrak API key
                api_key_result = extract_api_key_from_page(page, captured_keys)
                if api_key_result:
                    break

                # Cek apakah ada tombol Next/Continue
                next_clicked = False
                for next_sel in [
                    "button:has-text('Next')",
                    "button:has-text('Continue')",
                ]:
                    try:
                        btn = page.locator(next_sel).first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            log_step(f"Klik Next/Continue (step {step+1})...")
                            time.sleep(random.uniform(1.5, 2.5))
                            try:
                                page.wait_for_load_state("networkidle", timeout=8000)
                            except Exception:
                                pass
                            next_clicked = True
                            break
                    except Exception:
                        continue

                if not next_clicked:
                    time.sleep(2)

            if not api_key_result:
                # Navigasi langsung ke workspace/keys jika belum dapat
                log_step("Navigasi langsung ke workspace/keys...")
                page.goto("https://openrouter.ai/workspaces/default/keys",
                         wait_until="domcontentloaded", timeout=20000)
                time.sleep(3)
                api_key_result = extract_api_key_from_page(page, captured_keys)

            if not api_key_result:
                die("Gagal mengekstrak API Key dari halaman OpenRouter")

            log_step(f"Sukses! API Key: {api_key_result[:20]}...")
            emit({
                "status": "success",
                "email": email,
                "password": password,
                "api_key": api_key_result,
                "account_id": "",
            })

        except SystemExit:
            raise
        except Exception as e:
            die(f"Error dalam proses signup: {e}")


# ── Entry Point ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="OpenRouter auto-signup")
    parser.add_argument("--email", default="",
                        help="Email untuk signup. Jika kosong, di-generate random dari config.json domain.")
    parser.add_argument("--password", default="",
                        help="Password untuk signup. Jika kosong, di-generate random (min 8 char).")
    parser.add_argument("--domain", default="",
                        help="Domain email untuk generate random (overrides config.json pick).")
    parser.add_argument("--proxy-server", dest="proxy_server", default="")
    parser.add_argument("--proxy-user", dest="proxy_user", default="")
    parser.add_argument("--proxy-pass", dest="proxy_pass", default="")
    parser.add_argument("--ammail-base-url", dest="ammail_base_url", default="custom")
    parser.add_argument("--ammail-api-key", dest="ammail_api_key", default="custom")
    parser.add_argument("--ammail-domain", dest="ammail_domain", default="")
    parser.add_argument("--2captcha-key", dest="captcha_key", default="")
    parser.add_argument("--headless", action="store_true", default=False)
    parser.add_argument("--profiles-dir", dest="profiles_dir", default="")
    parser.add_argument("--output-file", dest="output_file", default="results.txt")
    parser.add_argument("--worker-id", dest="worker_id", type=int, default=1)
    parser.add_argument("--tag", default="1/1")

    args = parser.parse_args()

    # ── Generate random email jika tidak diisi ──────────────────────────────
    if not args.email:
        domain = args.domain or args.ammail_domain or ""
        args.email, _ = generate_random_email(domain if domain else None)
        log_step(f"Email random: {args.email}")

    # ── Generate random password jika tidak diisi ───────────────────────────
    if not args.password:
        args.password = random_password(12)
        log_step(f"Password random: {args.password}")

    run_signup(args)


if __name__ == "__main__":
    main()
