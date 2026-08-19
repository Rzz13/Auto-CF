"""
Qoder Creator - Browser Stealth
Anti-detection untuk Playwright: fingerprint evasion, navigator spoofing.
"""

import random
import asyncio
from typing import Optional, Dict

# ================= STEALTH JS =================
STEALTH_JS = """() => {
    // Overwrite navigator properties
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
    });

    // Overwrite chrome property
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };

    // Overwrite permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );

    // Hapus jejak automation
    delete window.__playwright;
    delete window.__pw_manual;
    delete window.__PW_inspect;

    // Override navigator.hardwareConcurrency
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8
    });

    // Override navigator.deviceMemory
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8
    });
}"""

# Redirect interception JS (capture qoder:// URLs)
QODER_REDIRECT_JS = """() => {
    (function() {
        const _origAssign = window.location.assign.bind(window.location);
        const _origReplace = window.location.replace.bind(window.location);
        window.location.assign = function(url) {
            if (url && url.startsWith('qoder://')) {
                window.__qoder_redirect_url = url;
                console.log('[STEALTH] Captured qoder:// assign:', url);
                return;
            }
            return _origAssign(url);
        };
        window.location.replace = function(url) {
            if (url && url.startsWith('qoder://')) {
                window.__qoder_redirect_url = url;
                console.log('[STEALTH] Captured qoder:// replace:', url);
                return;
            }
            return _origReplace(url);
        };
    })();
}"""

# Random user agents list
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-site-isolation-trials",
    "--disable-web-security",
    "--allow-running-insecure-content",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-accelerated-2d-canvas",
    "--no-first-run",
    "--no-zygote",
    "--use-gl=swiftshader",
    "--disable-gl-drawing-for-tests",
    "--disable-infobars",
    "--window-position=0,0",
    "--ignore-certificate-errors",
    "--ignore-certificate-errors-skip-list",
    "--disable-canvas-aa",
    "--disable-2d-canvas-clip-aa",
    "--disable-gl-error-limit",
    "--no-default-browser-check",
    "--disable-bell",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-breakpad",
    "--disable-client-side-phishing-detection",
    "--disable-component-extensions-with-background-pages",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-hang-monitor",
    "--disable-domain-reliability",
    "--disable-component-update",
]


# ================= CONTEXT HELPERS =================
async def create_stealth_context(browser, proxy: Dict[str, str] = None):
    """Create a browser context with stealth fingerprint."""
    context_kwargs = {
        "viewport": {
            "width": random.randint(1200, 1400),
            "height": random.randint(750, 850),
        },
        "user_agent": random_user_agent(),
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "device_scale_factor": 2,
        "has_touch": False,
        "is_mobile": False,
        "color_scheme": "light",
        "extra_http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        },
    }

    if proxy:
        context_kwargs["proxy"] = proxy

    context = await browser.new_context(**context_kwargs)

    # Inject stealth scripts
    await context.add_init_script(STEALTH_JS)
    await context.add_init_script(QODER_REDIRECT_JS)

    return context


async def launch_stealth_browser(playwright, proxy: Dict[str, str] = None, headless: bool = True):
    """Launch a Chromium browser with stealth args + optional proxy."""
    launch_options = {
        "headless": headless,
        "args": CHROMIUM_ARGS.copy(),
    }

    if proxy and proxy.get("server"):
        launch_options["proxy"] = proxy

    try:
        browser = await playwright.chromium.launch(**launch_options)
    except Exception:
        launch_options.pop("channel", None)
        browser = await playwright.chromium.launch(**launch_options)
    return browser
