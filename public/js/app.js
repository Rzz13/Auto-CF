// --- LocalStorage Keys ---
const STORAGE_KEYS = {
  AMMAIL_URL: "cf_auto_ammail_url",
  AMMAIL_KEY: "cf_auto_ammail_key",
  ROUTER_URL: "cf_auto_router_url",
  ROUTER_KEY: "cf_auto_router_key",
  CAPTCHA_KEY: "cf_auto_captcha_key",

  // New widget storage
  HEADLESS: "cf_auto_headless",
  AUTO_SYNC: "cf_auto_auto_sync",
  PROXY_ENABLED: "cf_auto_proxy_enabled",
  PROXY_LIST: "cf_auto_proxy_list",
  PROXY_TYPE: "cf_auto_proxy_type",
  EMAIL_AUTO: "cf_auto_email_auto",
  EMAIL_DOMAIN: "cf_auto_email_domain",
  CONCURRENT_RUN: "cf_auto_concurrent_run",
};

// --- DOM Elements ---
const elGenForm = document.getElementById("generator-form");
const elSettingsForm = document.getElementById("settings-form");
const elSubmit = document.getElementById("btn-generate");
const elStop = document.getElementById("btn-stop");

const elAutoEmail = document.getElementById("auto-generate-email");
const elManualEmailGroup = document.getElementById("manual-email-group");
const elManualEmail = document.getElementById("manual-email");

const elGenCount = document.getElementById("generate-count");
const elDomainSelect = document.getElementById("domain-select");

const elHeadless = document.getElementById("setting-headless");
const elAutoSync = document.getElementById("setting-auto-sync");
const elConcurrentRun = document.getElementById("setting-concurrent-run");

const elProxyEnabled = document.getElementById("setting-proxy-enabled");
const elProxyType = document.getElementById("proxy-type");
const elProxyCountLabel = document.getElementById("proxy-count-label");
const elProxyList = document.getElementById("proxy-list");
const elBtnProxyTest = document.getElementById("btn-proxy-test");
const elBtnProxyEdit = document.getElementById("btn-proxy-edit");

const elRouterUrl = document.getElementById("router-url");
const elRouterKey = document.getElementById("router-key");
const elCaptchaKey = document.getElementById("captcha-key");

const elClearLogs = document.getElementById("btn-clear-logs");
const elRefreshAccounts = document.getElementById("btn-refresh-accounts");
const elExportAccounts = document.getElementById("btn-export-accounts");

const elTerminal = document.getElementById("terminal-logs");
const elTableBody = document.getElementById("accounts-table-body");
const elSseStatus = document.getElementById("sse-status");

// --- Runner Queue State ---
let runQueue = {
  active: false,
  currentIndex: 0,
  totalCount: 0,
  emails: [],
  passwords: [],
  activeJobs: {},
};
let currentJobRetryCount = 0;

// --- Helper Functions ---
function generateRandomEmailPrefix() {
  const prefixes = [
    "rendi",
    "farah",
    "luna",
    "rifki",
    "sari",
    "yanto",
    "alif",
    "daniel",
    "chris",
    "oliver",
    "tom",
    "hadi",
  ];
  const randPrefix = prefixes[Math.floor(Math.random() * prefixes.length)];
  const randNum = Math.floor(1000 + Math.random() * 9000);
  return `${randPrefix}_${randNum}`;
}

function generateStrongPassword() {
  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
  const numbers = "0123456789";
  const specials = "!@#$%^&*";

  let pass = "";
  pass += letters[Math.floor(Math.random() * 26)]; // Uppercase
  pass += letters[26 + Math.floor(Math.random() * 26)]; // Lowercase
  pass += numbers[Math.floor(Math.random() * 10)];
  pass += specials[Math.floor(Math.random() * 8)];

  const allChars = letters + numbers + specials;
  for (let i = 0; i < 10; i++) {
    pass += allChars[Math.floor(Math.random() * allChars.length)];
  }

  return pass
    .split("")
    .sort(() => 0.5 - Math.random())
    .join("");
}

function writeToTerminal(text, type = "info") {
  const line = document.createElement("div");
  line.className = `line ${type}-line`;

  const timestamp = new Date().toLocaleTimeString();
  line.innerText = `[${timestamp}] ${text}`;

  elTerminal.appendChild(line);
  elTerminal.scrollTop = elTerminal.scrollHeight;
}

function copyToClipboard(text, label) {
  navigator.clipboard
    .writeText(text)
    .then(() => {
      alert(`${label} disalin ke clipboard!`);
    })
    .catch(() => {
      alert("Gagal menyalin.");
    });
}

function getProxiesArray() {
  return elProxyList.value
    .split("\n")
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
}

function updateProxyCountLabel() {
  const count = getProxiesArray().length;
  elProxyCountLabel.innerText = `${count} proxies configured`;
}

// --- Load and Save Settings ---
async function loadSettings() {
  elRouterUrl.value = localStorage.getItem(STORAGE_KEYS.ROUTER_URL) || "http://localhost:20128";
  elRouterKey.value = localStorage.getItem(STORAGE_KEYS.ROUTER_KEY) || "123456";
  elCaptchaKey.value = localStorage.getItem(STORAGE_KEYS.CAPTCHA_KEY) || "";

  elHeadless.checked = localStorage.getItem(STORAGE_KEYS.HEADLESS) !== "false";
  elAutoSync.checked = localStorage.getItem(STORAGE_KEYS.AUTO_SYNC) === "true";
  elProxyEnabled.checked =
    localStorage.getItem(STORAGE_KEYS.PROXY_ENABLED) === "true";
  elProxyType.value = localStorage.getItem(STORAGE_KEYS.PROXY_TYPE) || "http";

  elAutoEmail.checked =
    localStorage.getItem(STORAGE_KEYS.EMAIL_AUTO) !== "false";
  elDomainSelect.value =
    localStorage.getItem(STORAGE_KEYS.EMAIL_DOMAIN) || "random";
  elConcurrentRun.checked =
    localStorage.getItem(STORAGE_KEYS.CONCURRENT_RUN) === "true";

  try {
    const res = await fetch("/api/proxies");
    if (res.ok) {
      elProxyList.value = await res.text();
    }
  } catch (err) {
    console.error("Gagal memuat proxies dari server:", err);
  }

  updateProxyCountLabel();
  toggleEmailView();
}

async function saveSettings() {
  const routerUrl = elRouterUrl.value.trim();
  const routerKey = elRouterKey.value.trim();
  const captchaKey = elCaptchaKey.value.trim();

  localStorage.setItem(STORAGE_KEYS.ROUTER_URL, routerUrl);
  localStorage.setItem(STORAGE_KEYS.ROUTER_KEY, routerKey);
  localStorage.setItem(STORAGE_KEYS.CAPTCHA_KEY, captchaKey);

  localStorage.setItem(STORAGE_KEYS.HEADLESS, elHeadless.checked);
  localStorage.setItem(STORAGE_KEYS.AUTO_SYNC, elAutoSync.checked);
  localStorage.setItem(STORAGE_KEYS.PROXY_ENABLED, elProxyEnabled.checked);
  localStorage.setItem(STORAGE_KEYS.PROXY_TYPE, elProxyType.value);

  localStorage.setItem(STORAGE_KEYS.EMAIL_AUTO, elAutoEmail.checked);
  localStorage.setItem(STORAGE_KEYS.EMAIL_DOMAIN, elDomainSelect.value);
  localStorage.setItem(STORAGE_KEYS.CONCURRENT_RUN, elConcurrentRun.checked);

  const proxiesVal = elProxyList.value;
  try {
    await fetch("/api/proxies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proxies: proxiesVal })
    });
  } catch (err) {
    console.error("Gagal menyimpan proxies ke server:", err);
  }

  try {
    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        settings: {
          routerUrl,
          routerKey,
          captchaKey,
          concurrentRun: elConcurrentRun.checked
        }
      })
    });
  } catch (err) {
    console.error("Gagal menyimpan settings ke config.json:", err);
  }

  updateProxyCountLabel();
}

function toggleEmailView() {
  if (elAutoEmail.checked) {
    elManualEmailGroup.style.display = "none";
    elGenCount.closest(".form-row").style.display = "grid";
  } else {
    elManualEmailGroup.style.display = "flex";
    elGenCount.closest(".form-row").style.display = "none";
  }
}

// Bind settings form submit (Only save when "Save Settings" button is clicked)
elSettingsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  await saveSettings();
  alert("Pengaturan berhasil disimpan ke server!");
});

// Handle email view toggle
elAutoEmail.addEventListener("change", toggleEmailView);

// --- Accordions logic ---
document.querySelectorAll(".accordion-header").forEach((header) => {
  header.addEventListener("click", () => {
    const item = header.closest(".accordion-item");
    item.classList.toggle("open");
  });
});

// --- Proxy List Edit Toggle ---
elBtnProxyEdit.addEventListener("click", () => {
  if (elProxyList.hasAttribute("readonly")) {
    elProxyList.removeAttribute("readonly");
    elBtnProxyEdit.innerText = "💾 Save";
    elBtnProxyEdit.style.borderColor = "var(--accent-orange)";
    elBtnProxyEdit.style.color = "var(--accent-orange)";
  } else {
    elProxyList.setAttribute("readonly", "true");
    elBtnProxyEdit.innerText = "📝 Edit";
    elBtnProxyEdit.style.borderColor = "";
    elBtnProxyEdit.style.color = "";
    saveSettings();
  }
});

// --- Local Proxy Test Handler ---
elBtnProxyTest.addEventListener("click", () => {
  const proxies = getProxiesArray();
  if (proxies.length === 0) {
    alert("Masukkan setidaknya 1 proxy untuk dites!");
    return;
  }
  writeToTerminal(`Memulai pengujian lokal untuk ${proxies.length} proxy...`);
  proxies.forEach((p, index) => {
    writeToTerminal(`Proxy #${index + 1}: ${p} - Terdaftar`);
  });
  alert(`Seluruh ${proxies.length} proxy tersimpan dan siap digunakan!`);
});

// --- Server-Sent Events (SSE) logs streaming ---
function initEventSource() {
  const eventSource = new EventSource("/api/stream");

  eventSource.onopen = () => {
    elSseStatus.innerHTML = `<span class="status-dot green"></span> Connected`;
  };

  eventSource.onerror = () => {
    elSseStatus.innerHTML = `<span class="status-dot red"></span> Disconnected`;
  };

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.step) {
        // Intercept Wrangler logs
        if (
          data.step.includes("[Wrangler]") ||
          data.step.includes("[Wrangler stderr]") ||
          data.step.includes("[Wrangler Warning]") ||
          data.step.includes("=== MEMULAI SETUP")
        ) {
          let type = "info";
          if (
            data.step.includes("[Wrangler stderr]") ||
            data.step.includes("[Wrangler Error]")
          )
            type = "error";
          if (data.step.includes("[Wrangler Success]")) type = "success";

          const cleanText = data.step
            .replace("[Wrangler stderr] ", "")
            .replace("[Wrangler] ", "")
            .replace("[Wrangler Error] ", "")
            .replace("[Wrangler Success] ", "");

          if (typeof writeToWranglerConsole === "function") {
            writeToWranglerConsole(cleanText, type);
          }
          return;
        }

        let logType = "info";
        if (
          data.step.includes("[stderr]") ||
          data.step.includes("Warning") ||
          data.step.includes("Gagal") ||
          data.step.includes("Timeout")
        ) {
          logType = "stderr";
        }
        writeToTerminal(data.step, logType);
      }

      if (data.status === "success") {
        if (elConcurrentRun.checked) {
          writeToTerminal(
            `[Sukses] Akun berhasil dibuat: ${data.account.email}`,
            "success",
          );
          const emailKey = data.email || data.account.email;
          delete runQueue.activeJobs[emailKey];
          fetchAccounts();
          checkConcurrentQueueFinished();
        } else {
          writeToTerminal(
            `[Queue ${runQueue.currentIndex + 1}/${runQueue.totalCount}] Sukses: ${data.account.email}`,
            "success",
          );
          currentJobRetryCount = 0;
          fetchAccounts();
          advanceQueue();
        }
      } else if (data.status === "error") {
        if (elConcurrentRun.checked) {
          writeToTerminal(
            `[Gagal] ${data.error}`,
            "error",
          );
          const emailKey = data.email;
          if (emailKey) {
            handleConcurrentJobFailure(emailKey);
          } else {
            checkConcurrentQueueFinished();
          }
        } else {
          writeToTerminal(
            `[Queue ${runQueue.currentIndex + 1}/${runQueue.totalCount}] Gagal: ${data.error}`,
            "error",
          );
          handleJobFailure();
        }
      } else if (data.status === "wrangler-success") {
        if (typeof writeToWranglerConsole === "function") {
          writeToWranglerConsole(
            `Setup sukses! Worker di-deploy untuk domain: ${data.domain}`,
            "success",
          );
        }
        alert(
          `Wrangler Auto Setup & Deploy sukses!\nDomain ${data.domain} siap digunakan.`,
        );
        const btn = document.getElementById("btn-run-wrangler-setup");
        if (btn) {
          btn.removeAttribute("disabled");
          btn.innerText = "🚀 Mulai Deploy & Setup";
        }
        fetchConfigDomains();
      } else if (data.status === "wrangler-error") {
        if (typeof writeToWranglerConsole === "function") {
          writeToWranglerConsole(`Deployment Gagal: ${data.error}`, "error");
        }
        alert(`Setup Wrangler Gagal: ${data.error}`);
        const btn = document.getElementById("btn-run-wrangler-setup");
        if (btn) {
          btn.removeAttribute("disabled");
          btn.innerText = "🚀 Mulai Deploy & Setup";
        }
      }
    } catch (e) {
      writeToTerminal(event.data);
    }
  };
}

// --- Queue Execution Controller ---
async function runQueueStep() {
  if (!runQueue.active) return;

  if (elConcurrentRun.checked) {
    runQueue.activeJobs = {};
    for (let i = 0; i < runQueue.totalCount; i++) {
      const email = runQueue.emails[i];
      const password = runQueue.passwords[i];
      runQueue.activeJobs[email] = { retryCount: 0, password };
    }
    for (let i = 0; i < runQueue.totalCount; i++) {
      const email = runQueue.emails[i];
      const password = runQueue.passwords[i];
      triggerSingleRun(email, password);
    }
    return;
  }

  const email = runQueue.emails[runQueue.currentIndex];
  const password = runQueue.passwords[runQueue.currentIndex];

  writeToTerminal(`-------------------------------------------`);
  writeToTerminal(
    `Memulai Job ${runQueue.currentIndex + 1} dari ${runQueue.totalCount}`,
  );
  writeToTerminal(`Target Akun: ${email}`);
  writeToTerminal(`-------------------------------------------`);

  // Pick a random proxy if proxy is enabled
  let selectedProxy = "";
  if (elProxyEnabled.checked) {
    const proxies = getProxiesArray();
    if (proxies.length > 0) {
      selectedProxy = proxies[Math.floor(Math.random() * proxies.length)];
      writeToTerminal(`Menggunakan proxy acak: ${selectedProxy}`);
    } else {
      writeToTerminal(
        `Peringatan: Proxy aktif tetapi daftar proxy kosong! Menjalankan tanpa proxy...`,
        "stderr",
      );
    }
  }

  const ammailBaseUrl = "custom";
  const ammailApiKey = "custom";
  const routerUrl = elAutoSync.checked ? elRouterUrl.value.trim() : "";
  const routerApiKey = elAutoSync.checked ? elRouterKey.value.trim() : "";
  const captchaKey = elCaptchaKey.value.trim();
  const proxyType = elProxyType.value;

  // Custom domain parsing helper
  const emailDomain = email.split("@")[1];

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        proxy: selectedProxy,
        proxyType,
        ammailBaseUrl,
        ammailApiKey,
        ammailDomain: emailDomain,
        routerUrl,
        routerApiKey,
        captchaKey,
        headless: elHeadless.checked,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Gagal memicu run pada server");
    }
  } catch (err) {
    writeToTerminal(
      `Gagal memicu Job ${runQueue.currentIndex + 1}: ${err.message}`,
      "error",
    );
    handleJobFailure();
  }
}

function handleJobFailure() {
  if (!runQueue.active) return;

  const proxies = getProxiesArray();
  if (
    elProxyEnabled.checked &&
    proxies.length > 0 &&
    currentJobRetryCount < 5
  ) {
    currentJobRetryCount++;
    writeToTerminal(
      `[Retry ${currentJobRetryCount}/5] Mencoba ulang Job ini dengan proxy acak baru...`,
      "stderr",
    );

    // Generate new email/password for this job if using Auto Generate Email
    if (elAutoEmail.checked && cachedDomains.length > 0) {
      const prefix = generateRandomEmailPrefix();
      const domainSelection = elDomainSelect.value;
      let domain = "";
      if (domainSelection === "random") {
        domain = cachedDomains[Math.floor(Math.random() * cachedDomains.length)].domain;
      } else {
        domain = domainSelection;
      }
      const newEmail = `${prefix}@${domain}`;
      const newPassword = generateStrongPassword();

      runQueue.emails[runQueue.currentIndex] = newEmail;
      runQueue.passwords[runQueue.currentIndex] = newPassword;
      writeToTerminal(`Mengganti target email untuk retry: ${newEmail}`);
    }

    setTimeout(runQueueStep, 2000);
  } else {
    currentJobRetryCount = 0;
    writeToTerminal(
      `Job ${runQueue.currentIndex + 1} gagal permanen setelah percobaan maksimal. Melanjutkan ke Job berikutnya...`,
      "error",
    );
    advanceQueue();
  }
}

function advanceQueue() {
  runQueue.currentIndex++;
  if (runQueue.currentIndex < runQueue.totalCount) {
    runQueueStep();
  } else {
    // Queue finished
    runQueue.active = false;
    writeToTerminal(`===========================================`, "success");
    writeToTerminal(
      `Semua tugas otomatisasi selesai! (${runQueue.totalCount} Job)`,
      "success",
    );
    writeToTerminal(`===========================================`, "success");

    elSubmit.removeAttribute("disabled");
    elSubmit.innerText = "Generate & Run";
    elStop.style.display = "none";
  }
}

async function triggerSingleRun(email, password) {
  if (!runQueue.active) return;

  writeToTerminal(`[Parallel] Memulai otomatisasi untuk: ${email}`);

  let selectedProxy = "";
  if (elProxyEnabled.checked) {
    const proxies = getProxiesArray();
    if (proxies.length > 0) {
      selectedProxy = proxies[Math.floor(Math.random() * proxies.length)];
    }
  }

  const ammailBaseUrl = "custom";
  const ammailApiKey = "custom";
  const routerUrl = elAutoSync.checked ? elRouterUrl.value.trim() : "";
  const routerApiKey = elAutoSync.checked ? elRouterKey.value.trim() : "";
  const captchaKey = elCaptchaKey.value.trim();
  const proxyType = elProxyType.value;
  const emailDomain = email.split("@")[1];

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        proxy: selectedProxy,
        proxyType,
        ammailBaseUrl,
        ammailApiKey,
        ammailDomain: emailDomain,
        routerUrl,
        routerApiKey,
        captchaKey,
        headless: elHeadless.checked,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Gagal memicu run pada server");
    }
  } catch (err) {
    writeToTerminal(`[${email}] Gagal memicu Job: ${err.message}`, "error");
    handleConcurrentJobFailure(email);
  }
}

function handleConcurrentJobFailure(email) {
  if (!runQueue.active) return;
  const job = runQueue.activeJobs[email];
  if (!job) return;

  const proxies = getProxiesArray();
  if (elProxyEnabled.checked && proxies.length > 0 && job.retryCount < 5) {
    job.retryCount++;
    writeToTerminal(`[${email}][Retry ${job.retryCount}/5] Mencoba ulang dengan proxy acak baru...`, "stderr");

    let targetEmail = email;
    let targetPassword = job.password;
    if (elAutoEmail.checked && cachedDomains.length > 0) {
      const prefix = generateRandomEmailPrefix();
      const domainSelection = elDomainSelect.value;
      let domain = "";
      if (domainSelection === "random") {
        domain = cachedDomains[Math.floor(Math.random() * cachedDomains.length)].domain;
      } else {
        domain = domainSelection;
      }
      targetEmail = `${prefix}@${domain}`;
      targetPassword = generateStrongPassword();

      delete runQueue.activeJobs[email];
      runQueue.activeJobs[targetEmail] = { retryCount: job.retryCount, password: targetPassword };
      writeToTerminal(`[${email}] Target email diganti menjadi: ${targetEmail}`);
    }

    setTimeout(() => triggerSingleRun(targetEmail, targetPassword), 2000);
  } else {
    writeToTerminal(`[${email}] Job gagal permanen setelah percobaan maksimal.`, "error");
    delete runQueue.activeJobs[email];
    checkConcurrentQueueFinished();
  }
}

function checkConcurrentQueueFinished() {
  if (!runQueue.active) return;
  if (Object.keys(runQueue.activeJobs).length === 0) {
    runQueue.active = false;
    writeToTerminal(`===========================================`, "success");
    writeToTerminal(
      `Semua tugas otomatisasi selesai! (Concurrent Mode)`,
      "success",
    );
    writeToTerminal(`===========================================`, "success");

    elSubmit.removeAttribute("disabled");
    elSubmit.innerText = "Generate & Run";
    elStop.style.display = "none";
  }
}

// --- Fetch accounts list ---
async function fetchAccounts() {
  try {
    const res = await fetch("/api/accounts");
    if (!res.ok) throw new Error("Failed to read accounts from server");

    const accounts = await res.json();

    if (accounts.length === 0) {
      elTableBody.innerHTML = `<tr><td colspan="7" class="loading-td">Belum ada akun terdaftar di database lokal.</td></tr>`;
      return;
    }

    elTableBody.innerHTML = accounts
      .map((acc) => {
        const formattedDate = new Date(acc.createdAt).toLocaleString();
        const apiKeyTruncated = acc.apiKey
          ? `${acc.apiKey.substring(0, 15)}...`
          : "None";
        const accountIdTruncated = acc.accountId
          ? `${acc.accountId.substring(0, 12)}...`
          : "None";

        return `
        <tr>
          <td>${formattedDate}</td>
          <td>
            <span class="copyable" title="Klik untuk Copy" onclick="navigator.clipboard.writeText('${acc.email}'); alert('Email disalin!');" style="cursor: pointer; text-decoration: underline;">
              ${acc.email}
            </span>
          </td>
          <td><code>${acc.password}</code></td>
          <td title="${acc.accountId || ""}"><code>${accountIdTruncated}</code></td>
          <td title="${acc.apiKey || ""}"><code>${apiKeyTruncated}</code></td>
          <td><span class="badge ${acc.apiKeyStatus}">${acc.apiKeyStatus}</span></td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn-action" onclick="copyToClipboard('${acc.apiKey || ""}', 'API Key')">Copy Key</button>
              <button class="btn-action" onclick="copyToClipboard('${acc.accountId || ""}', 'Account ID')">Copy ID</button>
            </div>
          </td>
        </tr>
      `;
      })
      .join("");
  } catch (err) {
    elTableBody.innerHTML = `<tr><td colspan="7" class="loading-td" style="color: var(--accent-red)">Error memuat akun: ${err.message}</td></tr>`;
  }
}

// --- Action Bindings ---
elClearLogs.addEventListener("click", () => {
  elTerminal.innerHTML = `<div class="line system-line">[Sistem] Logs dibersihkan.</div>`;
});

elRefreshAccounts.addEventListener("click", fetchAccounts);

elGenForm.addEventListener("submit", (e) => {
  e.preventDefault();
  if (runQueue.active) return;

  // Validate SOCKS5 Proxy Authentication Limitation
  if (elProxyEnabled.checked && elProxyType.value === "socks5") {
    const proxies = getProxiesArray();
    const hasAuth = proxies.some((p) => {
      if (p.includes("@")) return true;
      const parts = p.split(":");
      if (parts.length === 4) return true;
      return false;
    });
    if (hasAuth) {
      alert(
        "Error: Playwright (Firefox/Camoufox) tidak mendukung autentikasi username & password untuk proxy tipe SOCKS5.\n\nSolusi:\n1. Gunakan IP Whitelisting pada dashboard penyedia proxy Anda, lalu hapus bagian 'user:pass@' dari list proxy.\n2. Atau, gunakan port HTTP/HTTPS dari penyedia proxy Anda dan ubah tipe proxy di pengaturan menjadi HTTP.",
      );
      return;
    }
  }

  const autoMail = elAutoEmail.checked;
  if (autoMail && cachedDomains.length === 0) {
    alert("Error: Belum ada domain email kustom yang dikonfigurasi!\n\nHarap masuk ke tab \"Email & Wrangler Setup\" untuk melakukan konfigurasi terlebih dahulu.");
    elTerminal.innerHTML = `<div class="line error-line">[Sistem Error] Gagal memulai otomatisasi: Belum ada domain email kustom yang dikonfigurasi! Harap buka tab "Email & Wrangler Setup" untuk menambahkan domain kustom atau deploy Worker terlebih dahulu.</div>`;
    return;
  }

  const count = autoMail ? parseInt(elGenCount.value) || 1 : 1;
  const domainSelection = elDomainSelect.value;
  const manualEmailVal = elManualEmail.value.trim();

  if (!autoMail && !manualEmailVal) {
    alert("Masukkan email address manual terlebih dahulu!");
    return;
  }

  // Populate queue
  runQueue.active = true;
  runQueue.currentIndex = 0;
  runQueue.totalCount = count;
  runQueue.emails = [];
  runQueue.passwords = [];

  for (let i = 0; i < count; i++) {
    let email = "";
    if (autoMail) {
      const prefix = generateRandomEmailPrefix();
      let domain = "";
      if (domainSelection === "random") {
        domain = cachedDomains[Math.floor(Math.random() * cachedDomains.length)].domain;
      } else {
        domain = domainSelection;
      }
      email = `${prefix}@${domain}`;
    } else {
      email = manualEmailVal;
    }

    runQueue.emails.push(email);
    runQueue.passwords.push(generateStrongPassword());
  }

  // Update UI State
  elSubmit.setAttribute("disabled", "true");
  elSubmit.innerText = "Running Automation Queue...";
  elStop.style.display = "block";
  elTerminal.innerHTML = `<div class="line system-line">[Sistem] Memulai antrian otomatisasi (${count} Job)...</div>`;

  runQueueStep();
});

elStop.addEventListener("click", async () => {
  if (!runQueue.active) return;

  elStop.setAttribute("disabled", "true");
  elStop.innerText = "Stopping...";
  writeToTerminal("Menghentikan antrian otomatisasi secara paksa...", "error");

  try {
    const res = await fetch("/api/stop", { method: "POST" });
    if (res.ok) {
      writeToTerminal("Backend proses dihentikan.", "success");
    }
  } catch (err) {
    writeToTerminal(
      `Gagal mengirim sinyal stop ke backend: ${err.message}`,
      "error",
    );
  }

  // Reset states
  runQueue.active = false;
  elSubmit.removeAttribute("disabled");
  elSubmit.innerText = "Generate & Run";

  elStop.removeAttribute("disabled");
  elStop.innerText = "Stop Process 🛑";
  elStop.style.display = "none";
});

// --- Initialization ---
window.addEventListener("DOMContentLoaded", () => {
  loadSettings();
  fetchAccounts();
  initEventSource();
  fetchConfigDomains(); // Muat domain kustom saat startup
});

// --- Tabs switching logic ---
const elTabBtnDashboard = document.getElementById("tab-btn-dashboard");
const elTabBtnSetup = document.getElementById("tab-btn-setup");
const elDashboardView = document.getElementById("dashboard-view");
const elSetupView = document.getElementById("setup-view");

elTabBtnDashboard.addEventListener("click", () => {
  elTabBtnDashboard.classList.add("active");
  elTabBtnSetup.classList.remove("active");
  elDashboardView.style.display = "block";
  elSetupView.style.display = "none";
});

elTabBtnSetup.addEventListener("click", () => {
  elTabBtnSetup.classList.add("active");
  elTabBtnDashboard.classList.remove("active");
  elDashboardView.style.display = "none";
  elSetupView.style.display = "block";
  fetchConfigDomains();
  fetchMailerScript();
});

// --- Domain Config Management ---
let cachedDomains = [];

async function fetchConfigDomains() {
  try {
    const res = await fetch("/api/config");
    if (!res.ok) throw new Error("Gagal mengambil konfigurasi domain");
    const data = await res.json();

    if (Array.isArray(data)) {
      cachedDomains = data;
    } else {
      cachedDomains = data.domains || [];
      // Muat data settings ke kolom input di UI jika ada
      if (data.settings) {
        if (data.settings.routerUrl !== undefined) {
          elRouterUrl.value = data.settings.routerUrl || "http://localhost:20128";
          localStorage.setItem(STORAGE_KEYS.ROUTER_URL, elRouterUrl.value);
        }
        if (data.settings.routerKey !== undefined) {
          elRouterKey.value = data.settings.routerKey || "123456";
          localStorage.setItem(STORAGE_KEYS.ROUTER_KEY, elRouterKey.value);
        }
        if (data.settings.captchaKey !== undefined) {
          elCaptchaKey.value = data.settings.captchaKey;
          localStorage.setItem(STORAGE_KEYS.CAPTCHA_KEY, data.settings.captchaKey);
        }
        if (data.settings.concurrentRun !== undefined) {
          elConcurrentRun.checked = data.settings.concurrentRun;
          localStorage.setItem(STORAGE_KEYS.CONCURRENT_RUN, data.settings.concurrentRun);
        }
      }
    }

    renderDomainsTable();
    updateEmailDomainDropdown();
  } catch (err) {
    console.error(err);
    document.getElementById("domains-table-body").innerHTML = `
      <tr>
        <td colspan="4" class="loading-td" style="color: var(--accent-red)">
          Error memuat domain: ${err.message}
        </td>
      </tr>`;
  }
}

function renderDomainsTable() {
  const tbody = document.getElementById("domains-table-body");
  if (cachedDomains.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="loading-td">Belum ada domain kustom yang terdaftar. Gunakan form di bawah atau auto-setup.</td></tr>`;
    return;
  }

  tbody.innerHTML = cachedDomains
    .map((d, index) => {
      const keyDisplay = d["x-api-key"] ? `••••••••` : "(Tidak ada)";
      return `
      <tr>
        <td><strong>${d.domain}</strong></td>
        <td><code style="font-size:12.5px;">${d.domain_url}</code></td>
        <td><code>${keyDisplay}</code></td>
        <td>
          <button class="btn-delete" onclick="deleteDomain(${index})">🗑️ Hapus</button>
        </td>
      </tr>
    `;
    })
    .join("");
}

function updateEmailDomainDropdown() {
  const select = document.getElementById("domain-select");
  let html = "";

  if (cachedDomains.length === 0) {
    html = `<option value="no-domain">No domain</option>`;
  } else if (cachedDomains.length === 1) {
    html = `<option value="${cachedDomains[0].domain}">${cachedDomains[0].domain}</option>`;
  } else {
    html = `<option value="random">Random (all domains)</option>`;
    cachedDomains.forEach((d) => {
      html += `<option value="${d.domain}">${d.domain}</option>`;
    });
  }
  select.innerHTML = html;

  // Select default value if exists in localStorage
  const savedDomain = localStorage.getItem(STORAGE_KEYS.EMAIL_DOMAIN);
  if (savedDomain && select.querySelector(`option[value="${savedDomain}"]`)) {
    select.value = savedDomain;
  }
}

async function deleteDomain(index) {
  if (
    !confirm(
      `Apakah Anda yakin ingin menghapus domain ${cachedDomains[index].domain}?`,
    )
  )
    return;

  const targetName = cachedDomains[index].domain;
  const updated = [...cachedDomains];
  updated.splice(index, 1);

  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    });
    if (!res.ok) throw new Error("Gagal menyimpan perubahan");

    writeToTerminal(`Domain ${targetName} dihapus dari konfigurasi.`, "info");
    await fetchConfigDomains();
  } catch (err) {
    alert(`Gagal menghapus domain: ${err.message}`);
  }
}

// Bind to window context
window.deleteDomain = deleteDomain;

// --- Add Domain Form ---
const elAddDomainForm = document.getElementById("add-domain-form");
elAddDomainForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const domain = document
    .getElementById("new-domain-name")
    .value.trim()
    .toLowerCase();
  const url = document.getElementById("new-domain-url").value.trim();
  const key = document.getElementById("new-domain-key").value.trim();

  if (!domain || !url) return;

  // Check duplicate
  if (cachedDomains.some((d) => d.domain === domain)) {
    alert("Domain ini sudah terdaftar!");
    return;
  }

  const newEntry = { domain, domain_url: url, "x-api-key": key };
  const updated = [...cachedDomains, newEntry];

  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    });
    if (!res.ok) throw new Error("Gagal menyimpan domain baru");

    document.getElementById("new-domain-name").value = "";
    document.getElementById("new-domain-url").value = "";
    document.getElementById("new-domain-key").value = "";

    writeToTerminal(`Domain baru ${domain} berhasil ditambahkan!`, "success");
    await fetchConfigDomains();
  } catch (err) {
    alert(`Gagal menambahkan domain: ${err.message}`);
  }
});

// --- Wrangler Auto-Setup ---
const elWranglerForm = document.getElementById("wrangler-setup-form");
const elWranglerBtn = document.getElementById("btn-run-wrangler-setup");
const elWranglerConsole = document.getElementById("wrangler-console-logs");

function writeToWranglerConsole(text, type = "info") {
  const line = document.createElement("div");
  line.className = `log-line log-${type}`;
  const timestamp = new Date().toLocaleTimeString();
  line.innerText = `[${timestamp}] ${text}`;
  elWranglerConsole.appendChild(line);
  elWranglerConsole.scrollTop = elWranglerConsole.scrollHeight;
}

// Bind to window context
window.writeToWranglerConsole = writeToWranglerConsole;

elWranglerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const apiToken = document.getElementById("setup-api-token").value.trim();
  const domain = document
    .getElementById("setup-domain-name")
    .value.trim()
    .toLowerCase();
  const apiKey = document.getElementById("setup-api-key").value.trim();

  if (!domain) {
    alert("Target domain wajib diisi!");
    return;
  }

  elWranglerBtn.setAttribute("disabled", "true");
  elWranglerBtn.innerText = "Deploying worker via Wrangler...";
  elWranglerConsole.innerHTML = `<div class="log-line">[Sistem] Memulai setup deployment Wrangler untuk domain: ${domain}...</div>`;

  try {
    const res = await fetch("/api/wrangler/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain, apiToken, apiKey }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Gagal memicu setup wrangler");
    }
    writeToWranglerConsole(
      "Sinyal deploy dikirim ke backend. Memantau output log...",
    );
  } catch (err) {
    writeToWranglerConsole(`Gagal memulai: ${err.message}`, "error");
    elWranglerBtn.removeAttribute("disabled");
    elWranglerBtn.innerText = "🚀 Mulai Deploy & Setup";
  }
});

// --- Fetch Mailer Script ---
async function fetchMailerScript() {
  const display = document.getElementById("code-snippet-display");
  try {
    const res = await fetch("/api/mailer-script");
    if (!res.ok) throw new Error("Gagal mengambil kode script worker");
    const code = await res.text();
    const highlighted = highlightJS(code);
    display.innerHTML = `<pre style="margin:0;"><code>${highlighted}</code></pre>`;
  } catch (err) {
    display.innerText = `Gagal memuat script mailer/index.js: ${err.message}`;
  }
}

// --- Syntax Highlighter Helper (Discord/Monokai style) ---
function highlightJS(code) {
  const pattern =
    /("(\\.|[^"\\])*"|'(\\.|[^'\\])*'|`(\\.|[^`\\])*`|\/\/[^\n]*|\/\*[\s\S]*?\*\/|\b(?:export|default|async|const|let|await|new|return|for|of|if|else|try|catch|import|from)\b|\b(?:Response|Request|Date|Math|Buffer|JSON|Promise|URL|Error|PostalMime|env|ctx)\b|\b\d+\b|\b[a-zA-Z0-9_]+(?=\())/g;

  let lastIndex = 0;
  let html = "";
  let match;

  while ((match = pattern.exec(code)) !== null) {
    const before = code.substring(lastIndex, match.index);
    html += before
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    const matchedText = match[0];
    let tokenType = "text";
    if (matchedText.startsWith("//") || matchedText.startsWith("/*")) {
      tokenType = "comment";
    } else if (
      matchedText.startsWith('"') ||
      matchedText.startsWith("'") ||
      matchedText.startsWith("`")
    ) {
      tokenType = "string";
    } else if (/^\d+$/.test(matchedText)) {
      tokenType = "number";
    } else if (
      /\b(export|default|async|const|let|await|new|return|for|of|if|else|try|catch|import|from)\b/.test(
        matchedText,
      )
    ) {
      tokenType = "keyword";
    } else if (
      /\b(Response|Request|Date|Math|Buffer|JSON|Promise|URL|Error|PostalMime|env|ctx)\b/.test(
        matchedText,
      )
    ) {
      tokenType = "builtin";
    } else {
      tokenType = "function";
    }

    const escapedMatch = matchedText
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    html += `<span class="token-${tokenType}">${escapedMatch}</span>`;

    lastIndex = pattern.lastIndex;
  }

  const remaining = code.substring(lastIndex);
  html += remaining
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return html;
}

// --- Copy Script Action ---
document.getElementById("btn-copy-script").addEventListener("click", () => {
  const codeContainer = document.getElementById("code-snippet-display");
  const code = codeContainer.innerText;
  navigator.clipboard
    .writeText(code)
    .then(() => {
      alert("Script mailer/index.js berhasil disalin ke clipboard!");
    })
    .catch(() => {
      alert("Gagal menyalin script.");
    });
});

// --- Global Window Alert Override to Custom Premium Modal ---
window.alert = function(message) {
  let title = "Pemberitahuan";
  let icon = "⚠️";
  
  const msgLower = message.toLowerCase();
  if (msgLower.includes("sukses") || msgLower.includes("berhasil") || msgLower.includes("disalin") || msgLower.includes("siap digunakan")) {
    title = "Sukses";
    icon = "✅";
  } else if (msgLower.includes("gagal") || msgLower.includes("error") || msgLower.includes("tidak ditemukan") || msgLower.includes("wajib diisi") || msgLower.includes("kesalahan")) {
    title = "Kesalahan";
    icon = "❌";
  }
  
  const modal = document.getElementById("custom-modal");
  const elTitle = document.getElementById("modal-title");
  const elMessage = document.getElementById("modal-message");
  const elIcon = modal.querySelector(".modal-title-icon");
  
  if (elTitle && elMessage && elIcon) {
    elTitle.innerText = title;
    elMessage.innerText = message;
    elIcon.innerText = icon;
    modal.style.display = "flex";

    if (window.alertAutoCloseTimeout) {
      clearTimeout(window.alertAutoCloseTimeout);
    }
    if (msgLower.includes("disalin")) {
      window.alertAutoCloseTimeout = setTimeout(() => {
        modal.style.display = "none";
      }, 1000);
    }
  } else {
    console.log(`[Alert] ${title}: ${message}`);
  }
};

// Bind modal closing listeners
document.getElementById("modal-close-btn").addEventListener("click", () => {
  document.getElementById("custom-modal").style.display = "none";
});

document.getElementById("custom-modal").addEventListener("click", (e) => {
  if (e.target === document.getElementById("custom-modal")) {
    document.getElementById("custom-modal").style.display = "none";
  }
});

// --- Export Accounts List to JSON Action ---
elExportAccounts.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/accounts");
    if (!res.ok) throw new Error("Gagal mengambil daftar akun dari server");
    const data = await res.json();

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cloudflare_accounts_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    alert("Daftar akun Cloudflare berhasil diekspor sebagai JSON!");
  } catch (err) {
    alert(`Gagal melakukan export: ${err.message}`);
  }
});
