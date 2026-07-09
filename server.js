import express from "express";
import cors from "cors";
import fs from "fs";
import path from "path";
import { spawn } from "child_process";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ACCOUNTS_FILE = path.join(__dirname, "accounts.json");

const app = express();
const PORT = process.env.PORT || 4000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// Initialize accounts.json if not exists
if (!fs.existsSync(ACCOUNTS_FILE)) {
  fs.writeFileSync(ACCOUNTS_FILE, JSON.stringify([], null, 2));
}

// In-memory active SSE clients
let sseClients = [];

// Helper to broadcast step logs to all connected dashboard clients
function broadcastLog(data) {
  sseClients.forEach((client) => {
    client.write(`data: ${JSON.stringify(data)}\n\n`);
  });
}

// Endpoint to read accounts.json
app.get("/api/accounts", (req, res) => {
  try {
    const raw = fs.readFileSync(ACCOUNTS_FILE, "utf-8");
    const accounts = JSON.parse(raw);
    res.json(accounts);
  } catch (err) {
    res.status(500).json({ error: "Failed to read accounts file" });
  }
});

// SSE endpoint for live terminal log streaming
app.get("/api/stream", (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  sseClients.push(res);

  req.on("close", () => {
    sseClients = sseClients.filter((client) => client !== res);
  });
});

function parseProxyString(raw, type = "http") {
  if (!raw) return null;
  raw = raw.trim();
  const proto = type === "socks5" ? "socks5" : "http";

  // Malformed: http://host:port:user:pass
  const badUrl = raw.match(
    /^(https?|socks[45]?):\/\/([^:]+):(\d+):([^:]+):(.+)$/,
  );
  if (badUrl) {
    const [, , host, port, user, pass] = badUrl;
    return {
      server: `${proto}://${host}:${port}`,
      username: user,
      password: pass,
    };
  }

  // Correct URL: http://user:pass@host:port
  const goodUrl = raw.match(
    /^(socks[45]?|https?|http):\/\/(?:([^:@]+):([^@]+)@)?([^:]+):(\d+)$/,
  );
  if (goodUrl) {
    const [, , user, pass, host, port] = goodUrl;
    const r = { server: `${proto}://${host}:${port}` };
    if (user) r.username = user;
    if (pass) r.password = pass;
    return r;
  }

  // Plain: host:port:user:pass
  const parts = raw.split(":");
  if (parts.length === 4 && /^\d+$/.test(parts[1])) {
    return {
      server: `${proto}://${parts[0]}:${parts[1]}`,
      username: parts[2],
      password: parts[3],
    };
  }

  // Plain: host:port
  if (parts.length === 2 && /^\d+$/.test(parts[1])) {
    return { server: `${proto}://${parts[0]}:${parts[1]}` };
  }

  return null;
}

let activeChild = null;
let cachedAuthToken = null;

// Trigger CF signup automation process
app.post("/api/run", async (req, res) => {
  const {
    email,
    password,
    proxy,
    proxyType,
    ammailBaseUrl,
    ammailApiKey,
    ammailDomain,
    captchaKey,
    routerUrl,
    routerApiKey,
    headless,
  } = req.body;

  if (!email || !password) {
    return res.status(400).json({ error: "Email and password are required" });
  }

  // Construct python script arguments
  const pythonBinary = process.platform === "win32" ? "python" : "python3";
  const scriptPath = path.join(__dirname, "automation", "cloudflare_signup.py");
  const args = [
    scriptPath,
    `--email=${email}`,
    `--password=${password}`,
    `--profiles-dir=${path.join(__dirname, "profiles")}`,
  ];

  if (headless !== false) {
    args.push("--headless");
  }

  if (ammailBaseUrl && ammailApiKey && ammailDomain) {
    args.push(`--ammail-base-url=${ammailBaseUrl}`);
    args.push(`--ammail-api-key=${ammailApiKey}`);
    args.push(`--ammail-domain=${ammailDomain}`);
  } else {
    const domain = email.split("@")[1];
    args.push(`--ammail-base-url=custom`);
    args.push(`--ammail-api-key=custom`);
    args.push(`--ammail-domain=${domain}`);
  }

  if (captchaKey) {
    args.push(`--2captcha-key=${captchaKey}`);
  }

  if (proxy) {
    const parsedProxy = parseProxyString(proxy, proxyType || "http");
    if (parsedProxy) {
      args.push(`--proxy-server=${parsedProxy.server}`);
      if (parsedProxy.username)
        args.push(`--proxy-user=${parsedProxy.username}`);
      if (parsedProxy.password)
        args.push(`--proxy-pass=${parsedProxy.password}`);
    } else {
      args.push(`--proxy-server=${proxy}`);
    }
  }

  console.log("Running python script with args:", args);
  broadcastLog({ step: `Memulai otomatisasi Camoufox untuk: ${email}...` });

  const child = spawn(pythonBinary, args);
  activeChild = child;

  child.stdout.on("data", async (data) => {
    const lines = data.toString().split("\n");
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const parsed = JSON.parse(line);
        if (parsed.step) {
          broadcastLog({ step: parsed.step });
        } else if (parsed.status === "success") {
          broadcastLog({
            step: "Akun sukses terverifikasi! Menyimpan hasil...",
          });

          // Save to local accounts.json
          const newAccount = {
            email: parsed.email,
            password: password,
            accountId: parsed.account_id,
            apiKey: parsed.api_key,
            apiKeyStatus: "ready",
            createdAt: new Date().toISOString(),
            profileDir: `profiles/cloudflare/${parsed.email.replace("@", "_")}`,
            provider: "cloudflare-ai",
          };

          try {
            const raw = fs.readFileSync(ACCOUNTS_FILE, "utf-8");
            const accounts = JSON.parse(raw);
            // Dedup
            const filtered = accounts.filter(
              (a) => a.email !== newAccount.email,
            );
            filtered.unshift(newAccount);
            fs.writeFileSync(ACCOUNTS_FILE, JSON.stringify(filtered, null, 2));
            broadcastLog({ step: "Tersimpan lokal di accounts.json!" });
          } catch (writeErr) {
            console.error("Local save error:", writeErr);
          }

          // Push to 9Router VPS connection manager if settings provided
          if (routerUrl && routerApiKey) {
            try {
              broadcastLog({ step: "Mengirim koneksi baru ke VPS 9Router..." });
              const urlClean = routerUrl.endsWith("/")
                ? routerUrl.slice(0, -1)
                : routerUrl;
              const connData = {
                provider: "cloudflare-ai",
                authType: "apikey",
                name: `${newAccount.email}|${password}`,
                apiKey: newAccount.apiKey,
                email: newAccount.email,
                priority: 1,
                isActive: true,
                testStatus: "active",
                providerSpecificData: {
                  accountId: newAccount.accountId,
                },
              };

              let headers = {
                "Content-Type": "application/json",
              };

              const isApiKey = routerApiKey.startsWith("sk-");
              if (isApiKey) {
                headers["Authorization"] = `Bearer ${routerApiKey}`;
              } else {
                headers["Cookie"] = `auth_token=${cachedAuthToken || routerApiKey}`;
              }

              let response = await fetch(`${urlClean}/api/providers`, {
                method: "POST",
                headers: headers,
                body: JSON.stringify(connData),
              });

              // Fallback jika menggunakan original monolith 9router (mengembalikan 404 di endpoint /api/providers)
              if (response.status === 404) {
                broadcastLog({
                  step: "Endpoint /api/providers 404 — Mencoba sinkronisasi ke monolith /api/providers/client...",
                });
                response = await fetch(`${urlClean}/api/providers/client`, {
                  method: "POST",
                  headers: headers,
                  body: JSON.stringify(connData),
                });
              }

              // Jika 401 Unauthorized dan input key bukan API Key (sk-), coba login menggunakan password
              if (response.status === 401 && !isApiKey) {
                broadcastLog({
                  step: "Status 401 Unauthorized — Mencoba melakukan login via password ke VPS...",
                });
                try {
                  const loginRes = await fetch(`${urlClean}/api/auth/login`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ password: routerApiKey }),
                  });

                  if (loginRes.status === 200 || loginRes.status === 201) {
                    const setCookieHeaders = loginRes.headers.getSetCookie
                      ? loginRes.headers.getSetCookie()
                      : [loginRes.headers.get("set-cookie")].filter(Boolean);

                    let authToken = null;
                    for (const header of setCookieHeaders) {
                      const match = header.match(/auth_token=([^;]+)/);
                      if (match) {
                        authToken = match[1];
                        break;
                      }
                    }

                    if (authToken) {
                      cachedAuthToken = authToken; // Simpan di cache global
                      broadcastLog({
                        step: "Login sukses! Mencoba ulang sinkronisasi dengan cookie auth_token baru...",
                      });
                      const authHeaders = {
                        "Content-Type": "application/json",
                        Cookie: `auth_token=${authToken}`,
                      };

                      // Coba ulang ke /api/providers dengan auth_token baru
                      response = await fetch(`${urlClean}/api/providers`, {
                        method: "POST",
                        headers: authHeaders,
                        body: JSON.stringify(connData),
                      });

                      // Jika masih 404, coba ulang ke monolith /api/providers/client
                      if (response.status === 404) {
                        response = await fetch(
                          `${urlClean}/api/providers/client`,
                          {
                            method: "POST",
                            headers: authHeaders,
                            body: JSON.stringify(connData),
                          },
                        );
                      }
                    } else {
                      broadcastLog({
                        step: "Login berhasil tetapi gagal mengekstrak cookie auth_token.",
                      });
                    }
                  } else {
                    broadcastLog({
                      step: `Gagal login ke VPS 9Router (Status ${loginRes.status})`,
                    });
                  }
                } catch (loginErr) {
                  broadcastLog({
                    step: `Gagal melakukan percobaan login otomatis: ${loginErr.message}`,
                  });
                }
              }

              if (response.status === 200 || response.status === 201) {
                broadcastLog({
                  step: "Sukses tersinkronisasi ke VPS 9Router!",
                });
              } else {
                const errText = await response.text();
                broadcastLog({
                  step: `Gagal sinkronisasi 9Router (Status ${response.status}): ${errText}`,
                });
              }
            } catch (syncErr) {
              broadcastLog({
                step: `Gagal sinkronisasi 9Router (Koneksi error): ${syncErr.message}`,
              });
            }
          }

          broadcastLog({ status: "success", account: newAccount });
        } else if (parsed.status === "error") {
          broadcastLog({ status: "error", error: parsed.error });
        }
      } catch (e) {
        // Raw print non-JSON logs as progress lines
        broadcastLog({ step: line });
      }
    }
  });

  child.stderr.on("data", (data) => {
    const rawLines = data.toString().split("\n");
    for (const rawLine of rawLines) {
      if (rawLine.trim()) {
        broadcastLog({ step: `[stderr] ${rawLine}` });
      }
    }
  });

  child.on("close", (code) => {
    if (activeChild === child) activeChild = null;
    broadcastLog({
      step: `Proses otomatisasi selesai dengan exit code: ${code}`,
    });
  });

  res.json({ status: "started" });
});

// Endpoint to stop the running automation process
app.post("/api/stop", (req, res) => {
  if (activeChild) {
    try {
      activeChild.kill("SIGTERM");
      broadcastLog({ step: "Otomatisasi dihentikan paksa oleh pengguna." });
    } catch (e) {
      console.error("Failed to kill active process:", e);
    }
    activeChild = null;
    res.json({ status: "stopped" });
  } else {
    res.json({ status: "idle" });
  }
});

const CONFIG_FILE = path.join(__dirname, "config.json");
const PROXIES_FILE = path.join(__dirname, "proxies.txt");

// Initialize config.json if not exists
if (!fs.existsSync(CONFIG_FILE)) {
  fs.writeFileSync(CONFIG_FILE, JSON.stringify({ domains: [], settings: {} }, null, 2));
}

// Initialize proxies.txt if not exists
if (!fs.existsSync(PROXIES_FILE)) {
  fs.writeFileSync(PROXIES_FILE, "# Masukkan daftar proxy Anda di sini (satu per baris, contoh: ip:port atau username:password@ip:port)\n");
}

app.get("/api/proxies", (req, res) => {
  try {
    const content = fs.existsSync(PROXIES_FILE) ? fs.readFileSync(PROXIES_FILE, "utf-8") : "";
    res.send(content);
  } catch (err) {
    res.status(500).send("Failed to read proxies file");
  }
});

app.post("/api/proxies", (req, res) => {
  try {
    const { proxies } = req.body;
    fs.writeFileSync(PROXIES_FILE, proxies || "");
    res.json({ status: "success" });
  } catch (err) {
    res.status(500).json({ error: "Failed to write proxies file" });
  }
});

app.get("/api/config", (req, res) => {
  try {
    const raw = fs.readFileSync(CONFIG_FILE, "utf-8");
    const config = JSON.parse(raw);
    res.json(config);
  } catch (err) {
    res.status(500).json({ error: "Failed to read config file" });
  }
});

app.get("/api/mailer-script", (req, res) => {
  try {
    const mailerPath = path.join(__dirname, "mailer", "index.js");
    if (fs.existsSync(mailerPath)) {
      res.type("text/plain").send(fs.readFileSync(mailerPath, "utf-8"));
    } else {
      res.status(404).send("Mailer script not found");
    }
  } catch (err) {
    res.status(500).send("Failed to read mailer script");
  }
});

app.post("/api/config", (req, res) => {
  try {
    const body = req.body;
    let current = { domains: [], settings: {} };
    if (fs.existsSync(CONFIG_FILE)) {
      try {
        const raw = fs.readFileSync(CONFIG_FILE, "utf-8");
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          current.domains = parsed;
        } else {
          current = parsed;
        }
      } catch (e) {}
    }

    if (Array.isArray(body)) {
      current.domains = body;
    } else {
      if (body.domains) current.domains = body.domains;
      if (body.settings) current.settings = body.settings;
    }

    fs.writeFileSync(CONFIG_FILE, JSON.stringify(current, null, 2));
    res.json({ status: "success" });
  } catch (err) {
    res.status(500).json({ error: "Failed to write config file" });
  }
});

// POST wrangler setup
app.post("/api/wrangler/setup", async (req, res) => {
  const { domain, apiToken, apiKey } = req.body;
  if (!domain) {
    return res.status(400).json({ error: "Domain is required" });
  }

  res.json({ status: "started" });

  const mailerDir = path.join(__dirname, "mailer");
  const customEnv = {};
  if (apiToken) {
    customEnv.CLOUDFLARE_API_TOKEN = apiToken.trim();
  }

  const runCmd = (cmd, args) => {
    return new Promise((resolve, reject) => {
      broadcastLog({ step: `[Wrangler] Menjalankan: ${cmd} ${args.join(" ")}` });
      const p = spawn(cmd, args, {
        shell: true,
        cwd: mailerDir,
        env: { ...process.env, ...customEnv }
      });

      let stdout = "";
      let stderr = "";

      p.stdout.on("data", (data) => {
        const text = data.toString();
        stdout += text;
        text.split("\n").forEach(line => {
          if (line.trim()) broadcastLog({ step: `[Wrangler] ${line.trim()}` });
        });
      });

      p.stderr.on("data", (data) => {
        const text = data.toString();
        stderr += text;
        text.split("\n").forEach(line => {
          if (line.trim()) broadcastLog({ step: `[Wrangler stderr] ${line.trim()}` });
        });
      });

      p.on("close", (code) => {
        if (code === 0) {
          resolve(stdout);
        } else {
          reject(new Error(`Exit code ${code}. Stderr: ${stderr}`));
        }
      });
    });
  };

  // Run the setup flow asynchronously
  (async () => {
    try {
      broadcastLog({ step: "=== MEMULAI SETUP OTOMATIS WRANGLER ===" });
      try {
        await runCmd("npx", ["wrangler", "whoami"]);
      } catch (err) {
        if (!apiToken) {
          broadcastLog({ step: "[Wrangler Error] Anda belum login ke Wrangler. Harap jalankan 'npx wrangler login' di terminal Anda, atau masukkan Cloudflare API Token." });
          throw err;
        }
      }

      broadcastLog({ step: "[Wrangler] Memeriksa KV Namespace..." });
      let kvId = "";
      try {
        const kvListOutput = await runCmd("npx", ["wrangler", "kv:namespace", "list"]);
        const namespaces = JSON.parse(kvListOutput);
        const matchedKv = namespaces.find(ns => ns.title.includes("EMAIL_KV") || ns.title.includes("cloudflare-email-handler-EMAIL_KV"));
        if (matchedKv) {
          kvId = matchedKv.id;
          broadcastLog({ step: `[Wrangler] KV Namespace EMAIL_KV ditemukan dengan ID: ${kvId}` });
        }
      } catch (err) {
        broadcastLog({ step: `[Wrangler Warning] Gagal membaca list KV namespace: ${err.message}. Mencoba membuat baru...` });
      }

      if (!kvId) {
        broadcastLog({ step: "[Wrangler] Membuat KV Namespace baru 'EMAIL_KV'..." });
        const kvCreateOutput = await runCmd("npx", ["wrangler", "kv:namespace", "create", "EMAIL_KV"]);
        const match = kvCreateOutput.match(/"id":\s*"([a-f0-9]{32})"/i) || kvCreateOutput.match(/with ID\s+([a-f0-9]{32})/i);
        if (match) {
          kvId = match[1];
          broadcastLog({ step: `[Wrangler] Sukses membuat KV namespace dengan ID: ${kvId}` });
        } else {
          throw new Error("Gagal mengambil ID KV dari output pembuatan KV");
        }
      }

      broadcastLog({ step: "[Wrangler] Menulis mailer/wrangler.toml..." });
      const tomlPath = path.join(mailerDir, "wrangler.toml");
      let tomlContent = `name = "cloudflare-email-handler"
main = "index.js"
compatibility_date = "2024-01-01"

[[kv_namespaces]]
binding = "EMAIL_KV"
id = "${kvId}"
`;
      if (apiKey) {
        tomlContent += `
[vars]
API_KEY = "${apiKey.trim()}"
`;
      }
      fs.writeFileSync(tomlPath, tomlContent, "utf-8");
      broadcastLog({ step: "[Wrangler] Sukses menulis mailer/wrangler.toml!" });

      broadcastLog({ step: "[Wrangler] Men-deploy Worker ke Cloudflare..." });
      const deployOutput = await runCmd("npx", ["wrangler", "deploy"]);
      const urlMatch = deployOutput.match(/(https:\/\/[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-]+\.workers\.dev)/);
      let workerUrl = "";
      if (urlMatch) {
        workerUrl = urlMatch[1];
        broadcastLog({ step: `[Wrangler] Worker berhasil di-deploy ke: ${workerUrl}` });
      } else {
        const urlMatch2 = deployOutput.match(/https:\/\/[^\s]+/);
        if (urlMatch2) {
          workerUrl = urlMatch2[0];
          broadcastLog({ step: `[Wrangler Fallback] Worker di-deploy ke: ${workerUrl}` });
        } else {
          throw new Error("Gagal mengekstrak URL Worker dari output deployment");
        }
      }

      broadcastLog({ step: "[Wrangler] Menyimpan konfigurasi baru ke config.json..." });
      const raw = fs.readFileSync(CONFIG_FILE, "utf-8");
      const parsed = JSON.parse(raw);
      
      let domains = [];
      let settings = {};
      if (Array.isArray(parsed)) {
        domains = parsed;
      } else {
        domains = parsed.domains || [];
        settings = parsed.settings || {};
      }

      const cleanDomain = domain.trim().toLowerCase();
      const idx = domains.findIndex(c => c.domain.toLowerCase() === cleanDomain);
      const newConfig = {
        domain: cleanDomain,
        domain_url: workerUrl,
        "x-api-key": apiKey || ""
      };

      if (idx !== -1) {
        domains[idx] = newConfig;
      } else {
        domains.push(newConfig);
      }
      
      const toWrite = Array.isArray(parsed) ? domains : { domains, settings };
      fs.writeFileSync(CONFIG_FILE, JSON.stringify(toWrite, null, 2));
      broadcastLog({ step: `[Wrangler Success] Domain ${cleanDomain} berhasil dikonfigurasi dan disimpan!` });
      broadcastLog({ status: "wrangler-success", domain: cleanDomain, url: workerUrl });

    } catch (err) {
      broadcastLog({ step: `[Wrangler Error] Setup gagal: ${err.message}` });
      broadcastLog({ status: "wrangler-error", error: err.message });
    }
  })();
});

app.listen(PORT, () => {
  console.log(
    `Standalone CF Auto-Signup backend running at http://localhost:${PORT}`,
  );
});
