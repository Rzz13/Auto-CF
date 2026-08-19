"""Qoder account auto-signup via Playwright + Temp Mail + Captcha Solver + PAT Generation.

Outputs JSON lines to stdout:
  {"step": "..."} — progress update
  {"status": "success", "api_key": "...", "email": "...", "password": "...", "account_id": ""} — final result
  {"status": "error", "error": "..."} — failure
"""

import sys
import json
import argparse
import time
import asyncio
import os
from pathlib import Path

# Add automation directory to sys.path for internal imports
AUTOMATION_DIR = Path(__file__).parent
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))

# Force UTF-8 encoding on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def emit(obj):
    print(json.dumps(obj), flush=True)


def log_step(msg):
    emit({"step": msg})


def die(msg, code=1):
    emit({"status": "error", "error": msg})
    sys.exit(code)


# ── Custom Console Wrapper to capture Rich logs and emit JSON steps ────────────
class StepLoggerConsole:
    """Wrapper console that redirects rich prints to emit({'step': ...})."""

    def print(self, *args, **kwargs):
        text_parts = []
        for arg in args:
            if hasattr(arg, "plain"):
                text_parts.append(arg.plain)
            else:
                s = str(arg)
                import re
                s = re.sub(r"\[/?(?:bold|cyan|yellow|green|red|dim|italic|bright_black|white|magenta)[^\]]*\]", "", s)
                text_parts.append(s)
        text = " ".join(text_parts).strip()
        if text:
            log_step(text)


def check_proxy_alive(proxy_dict, timeout=10):
    """Test if the proxy is working by sending a fast request to a public API."""
    import urllib.request
    import urllib.parse
    import urllib.error
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


async def run_qoder_signup(args):
    email_target = args.email
    password_target = args.password
    proxy_server = args.proxy_server
    proxy_user = getattr(args, "proxy_user", "")
    proxy_pass = getattr(args, "proxy_pass", "")
    headless = args.headless

    try:
        from qoder_utils.tempmail import TempikClient
        from qoder_utils.utils import generate_password
        from qoder_utils.stealth import launch_stealth_browser, create_stealth_context
        from qoder_utils.config import QODER_BASE
        from qoder_utils.captcha import solve_slider_local
        from qoder_utils.pat import PATManager
    except ImportError as e:
        die(f"Gagal mengimpor modul qoder_utils: {e}")

    # Build proxy dict if provided
    proxy_dict = None
    if proxy_server:
        import urllib.parse
        p_str = proxy_server if (proxy_server.startswith("http") or proxy_server.startswith("socks")) else f"http://{proxy_server}"
        parsed = urllib.parse.urlparse(p_str)
        clean_server = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            clean_server += f":{parsed.port}"
        user = parsed.username or proxy_user
        pwd = parsed.password or proxy_pass

        proxy_dict = {"server": clean_server}
        if user and pwd:
            proxy_dict["username"] = user
            proxy_dict["password"] = pwd

        log_step("Menguji koneksi proxy...")
        if not check_proxy_alive(proxy_dict):
            die("Proxy mati/Invalid IP - aborting untuk retry proxy baru", 3)

    # Custom console for progress logs
    step_console = StepLoggerConsole()
    log_step("Memulai alur pembuatan akun Qoder...")

    try:
        # Step 1: Prep temp email
        tempmail = TempikClient()
        domain = None
        if args.ammail_domain:
            domain = args.ammail_domain
        elif email_target and "@" in email_target and email_target != "__random__":
            domain = email_target.split("@")[1]

        if email_target and email_target != "__random__":
            local_part = email_target.split("@")[0]
            email = tempmail.create_inbox(local_part=local_part, domain=domain)
        else:
            email = tempmail.create_inbox(domain=domain)

        password = password_target if (password_target and password_target != "__random__") else generate_password()

        log_step(f"Email target: {email}")
        log_step(f"Password target: {password}")

        # Launch Playwright & Execute Qoder signup
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            log_step("Membuka browser...")
            browser = await launch_stealth_browser(p, proxy_dict, headless)
            context = await create_stealth_context(browser, proxy_dict)
            page = await context.new_page()

            log_step("Membuka halaman signup Qoder...")
            await page.goto(f"{QODER_BASE}/users/sign-up", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)

            # Fill form
            log_step("Mengisi form registrasi Qoder...")
            try:
                await page.fill("#basic_firstName", "User")
                await page.fill("#basic_lastName", "Dev")
                await page.fill("#basic_email", email)
            except Exception as fe:
                await context.close()
                await browser.close()
                die(f"Gagal mengisi input email/nama: {fe}")

            # Checkbox I agree
            cb = await page.query_selector("input[type=checkbox]")
            if cb:
                try:
                    await cb.check(force=True)
                except Exception:
                    pass

            # Click Continue
            # log_step("Klik Continue...")
            for sel in ['button:has-text("Continue")', 'button[type="submit"]']:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        break
                except Exception:
                    continue
            await page.wait_for_timeout(4000)

            # Fill password
            # log_step("Mengisi password...")
            pw = await page.query_selector("#basic_password")
            if pw:
                try:
                    await pw.click(force=True)
                    await page.keyboard.type(password, delay=20)
                except Exception:
                    pass
            for sel in ['button:has-text("Continue")', 'button[type="submit"]']:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        break
                except Exception:
                    continue
            await page.wait_for_timeout(4000)

            # Captcha
            log_step("Memeriksa Captcha Slider...")
            for sel in ["#aliyunCaptcha-captcha-body", 'button:has-text("Click to verify")']:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        break
                except Exception:
                    continue
            await page.wait_for_timeout(3000)

            # log_step("Menyelesaikan Captcha Slider lokal...")
            solved = await solve_slider_local(page, max_attempts=5, console=step_console)
            if not solved:
                await context.close()
                await browser.close()
                die("Gagal menyelesaikan Captcha Slider setelah 5 percobaan")

            log_step("Captcha berhasil diselesaikan!")
            await page.wait_for_timeout(2000)

            # OTP email polling (1 menit = timeout 60s)
            log_step("Menunggu email OTP verifikasi dari Qoder (timeout 60 detik)...")
            messages = await tempmail.wait_for_messages(email, max_wait=60, interval=4)

            if not messages:
                await context.close()
                await browser.close()
                die("OTP verifikasi email tidak diterima dalam 1 menit")

            otp = tempmail.extract_otp(messages)
            if not otp:
                await context.close()
                await browser.close()
                die("Gagal mengekstrak 6-digit OTP dari email")

            log_step(f"Kode OTP diterima: {otp}")

            # Fill OTP
            # log_step("Mengisi kode OTP...")
            otp_inputs = await page.query_selector_all('input.ant-otp-input')
            if len(otp_inputs) >= 6:
                await otp_inputs[0].click()
                await page.wait_for_timeout(200)
                await page.keyboard.type(otp, delay=80)
                await page.wait_for_timeout(1500)
            else:
                all_inputs = await page.query_selector_all('input:not([type="hidden"])')
                if all_inputs:
                    await all_inputs[0].click()
                    await page.keyboard.type(otp, delay=80)
                else:
                    await page.keyboard.type(otp, delay=80)

            for sel in ['button:has-text("Create account")', 'button:has-text("Verify")', 'button[type="submit"]']:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        break
                except Exception:
                    continue
            await page.wait_for_timeout(6000)

            current_url = page.url
            # log_step(f"URL setelah verifikasi: {current_url}")

            # Create PAT (Personal Access Token)
            log_step("Mengekstrak PAT (Personal Access Token)...")
            pat_response = await PATManager.create(page, "farm")
            pat_token = PATManager.extract_token(pat_response)

            # Jika percobaan pertama belum mendapat token, navigasi ke dashboard/settings dan retry
            if not pat_token:
                log_step(f"PAT percobaan 1 status={pat_response.get('status')}. Navigasi ke dashboard Qoder untuk retry...")
                try:
                    await page.goto(f"{QODER_BASE}/dashboard", wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(3000)
                    pat_response = await PATManager.create(page, "farm")
                    pat_token = PATManager.extract_token(pat_response)
                except Exception as ne:
                    log_step(f"Retry navigation error: {ne}")

            pat_valid = pat_token is not None

            # Try CLI device claim if PAT valid
            # claimed = False
            # if pat_valid:
            #     log_step("Klaim trial Pro via device authorization...")
            #     try:
            #         from qoder_utils.claim import ClaimManager
            #         claimed = await ClaimManager.auto_device_authorize(page)
            #         if not claimed:
            #             acc_obj = {"email": email, "pat_token": pat_token, "pat_valid": pat_valid}
            #             claimed = await ClaimManager.claim_account(acc_obj)
            #     except Exception as ce:
            #         log_step(f"Warning claim trial: {ce}")

            await context.close()
            await browser.close()

            if not pat_token:
                die(f"Gagal mengekstrak PAT Token (Status HTTP {pat_response.get('status')}: {pat_response.get('body', '')[:100]})")

            log_step(f"Sukses! PAT Token: {pat_token[:25]}...")
            emit({
                "status": "success",
                "email": email,
                "password": password,
                "api_key": pat_token,
                "account_id": "",
                "claimed": "false"
            })

    except SystemExit:
        raise
    except Exception as e:
        die(f"Error dalam alur signup Qoder: {e}")


def main():
    parser = argparse.ArgumentParser(description="Qoder auto-signup")
    parser.add_argument("--email", default="", help="Email target. Jika kosong, di-generate dari tempmail.")
    parser.add_argument("--password", default="", help="Password target. Jika kosong, di-generate random.")
    parser.add_argument("--domain", default="", help="Domain tempmail kustom.")
    parser.add_argument("--proxy-server", dest="proxy_server", default="")
    parser.add_argument("--proxy-user", dest="proxy_user", default="")
    parser.add_argument("--proxy-pass", dest="proxy_pass", default="")
    parser.add_argument("--ammail-base-url", dest="ammail_base_url", default="")
    parser.add_argument("--ammail-api-key", dest="ammail_api_key", default="")
    parser.add_argument("--ammail-domain", dest="ammail_domain", default="")
    parser.add_argument("--2captcha-key", dest="captcha_key", default="")
    parser.add_argument("--headless", action="store_true", default=False)
    parser.add_argument("--profiles-dir", dest="profiles_dir", default="")
    parser.add_argument("--output-file", dest="output_file", default="results.txt")
    parser.add_argument("--worker-id", dest="worker_id", type=int, default=1)
    parser.add_argument("--tag", default="1/1")

    args = parser.parse_args()
    asyncio.run(run_qoder_signup(args))


if __name__ == "__main__":
    main()
