# ☁️ CF Auto-Signup Manager

<p align="center">
  <img src="https://img.shields.io/badge/node.js-v18+-green?style=for-the-badge&logo=node.js" alt="Node version" />
  <img src="https://img.shields.io/badge/python-v3.8+-blue?style=for-the-badge&logo=python" alt="Python version" />
  <img src="https://img.shields.io/badge/cloudflare-workers-orange?style=for-the-badge&logo=cloudflare" alt="Cloudflare Workers" />
  <img src="https://img.shields.io/badge/license-MIT-red?style=for-the-badge" alt="License MIT" />
</p>

**CF Auto-Signup Manager** adalah aplikasi dashboard otomasi mandiri (standalone) yang dirancang untuk melakukan registrasi massal akun Cloudflare secara otomatis. Alat ini dilengkapi bypass Captcha Turnstile, integrasi domain email kustom via Cloudflare Worker/KV, serta sinkronisasi otomatis ke sistem **9Router**.

Didesain dengan antarmuka gelap minimalis yang premium dan dilengkapi penanganan proxy keluar (*outbound proxy*) untuk menjaga keamanan sidik jari (*fingerprint*) browser Anda.

---

## ✨ Fitur Utama

- 🤖 **Otomasi Camoufox**: Menggunakan Playwright dengan browser Camoufox (anti-fingerprinting tingkat lanjut) untuk bypass deteksi bot secara maksimal.
- ⚡ **Jalankan Secara Bersamaan (Concurrent Mode)**:
  - Mampu meluncurkan beberapa proses registrasi browser secara paralel di latar belakang untuk menghemat waktu.
  - Dilengkapi fitur pengenal tag email di logs terminal (`[email@domain]`) agar pembacaan proses multi-akun tetap rapi dan terorganisir.
  - Penanganan *error*, *retry*, dan rotasi proxy berjalan mandiri di setiap tugas paralel.
- 🔑 **Bypass Captcha Turnstile**: Terintegrasi langsung dengan API **2Captcha** untuk menyelesaikan tantangan Turnstile secara otomatis di latar belakang.
- 📧 **Pengelola Domain Email Dinamis**:
  - Konfigurasi domain kustom untuk menerima email verifikasi.
  - **Auto Setup Wrangler**: Cukup satu klik untuk membuat KV Namespace, menulis berkas `wrangler.toml`, dan men-deploy email routing Worker secara otomatis ke Cloudflare.
- 🔗 **Sinkronisasi Otomatis 9Router**:
  - Otomatis memasukkan kredensial akun sukses (Email, Password, Account ID, API Token) langsung ke panel VPS **9Router**.
  - **Robust Auto Re-login (Cookie Mode)**: Jika otentikasi session cookie kedaluwarsa atau menghasilkan status `401 Unauthorized`, server backend otomatis melakukan otentikasi login ulang ke VPS 9Router dan mencoba ulang sinkronisasi tanpa intervensi manual.
- 📋 **Pop-up Auto-Close**: Pop-up notifikasi setelah Anda menyalin Email, API Token (Copy Key), Account ID (Copy ID), atau Mailer Script akan otomatis menutup diri dalam 1 detik.
- 📥 **Export Data Mudah**: Unduh daftar akun sukses hasil otomatisasi kapan saja dalam format **JSON** sekali klik.
- 🌐 **Outbound Proxy List**: Mendukung daftar proxy (HTTP/SOCKS5) dalam format file `proxies.txt` dengan opsi rotasi otomatis per tugas registrasi.
- 📺 **Logs Streaming Real-time**: Logs visual dari browser otomatisasi dan Wrangler streaming secara langsung ke dashboard web melalui Server-Sent Events (SSE).

---

## 🛠️ Prasyarat (Prerequisites)

Sebelum menjalankan aplikasi, pastikan sistem Anda telah terpasang:
1. **Node.js** (versi >= 18)
2. **Python** (versi >= 3.8)

---

## 🚀 Panduan Instalasi & Mulai Cepat

### 1. Kloning Repositori
```bash
git clone https://github.com/Rzz13/Auto-CF.git
cd Auto-CF
```

### 2. Instalasi Dependensi Node.js
```bash
npm install
```

### 3. Instalasi Dependensi Python & Camoufox Browser
Aplikasi menggunakan Camoufox untuk meniru perilaku browser manusia sealami mungkin.
```bash
pip install camoufox
pip3 install --break-system-packages camoufox "camoufox[geoip]" "playwright==1.59.0"
python -m camoufox fetch
```

### 4. Jalankan Aplikasi
Jalankan server backend lokal:
```bash
npm start
```
Buka peramban browser Anda lalu akses dashboard di alamat:
👉 **[http://localhost:4000](http://localhost:4000)**

---

## ⚙️ Panduan Penggunaan & Konfigurasi

### A. Pengaturan Proxy (`proxies.txt`)
Masukkan daftar proxy Anda ke dalam berkas `proxies.txt` di root folder proyek (satu proxy per baris):
```text
# Contoh format proxy:
ip:port:user:password
username:password@ip:port
```
*Daftar proxy ini dapat diedit dan disimpan secara langsung melalui panel **Outbound Proxy Settings** di dashboard UI.*

### B. Auto Setup Cloudflare Worker Email
Jika belum memiliki Worker untuk menangkap email verifikasi Cloudflare, masuk ke tab **Email & Wrangler Setup** di UI:
1. Klik tombol **Mulailah Deploy & Setup** (Pastikan Anda telah melakukan login wrangler sebelumnya via terminal dengan perintah `npx wrangler login`).
2. Program akan secara otomatis membuatkan KV Namespace dan mempublikasikan email-routing worker khusus ke Cloudflare Anda.
3. Tambahkan domain terkait ke tabel **Pengelola Domain Email**.

### C. Menjalankan Pendaftaran Akun massal
1. Masuk ke tab **Dashboard**.
2. Pilih jumlah akun yang ingin dibuat pada kolom **Count to generate**.
3. Pilih domain email target (atau biarkan *Random* jika mendaftarkan lebih dari satu domain).
4. Klik **Generate & Run**. Aplikasi akan memulai antrian registrasi dan log aktivitas peramban akan streaming real-time di layar.

---

## 📂 Struktur Berkas Proyek

```text
├── automation/
│   └── cloudflare_signup.py    # Script python otomasi Playwright/Camoufox
├── mailer/
│   └── index.js                # Template email-routing worker Cloudflare
├── public/                     # Static files frontend dashboard (HTML, CSS, JS)
│   ├── css/
│   │   └── style.css           # Custom CSS premium minimalis style
│   ├── js/
│   │   └── app.js              # Logika frontend & handler API
│   └── index.html              # Antarmuka dashboard
├── accounts.json               # Database hasil akun terdaftar (Auto Generated)
├── config.json                 # Konfigurasi domain & settings server (Auto Generated)
├── config.example.json         # Contoh templat konfigurasi server
├── LICENSE                     # File lisensi MIT
├── proxies.txt                 # Daftar proxy outbound (Auto Generated jika kosong)
├── server.js                   # Node.js backend server
└── package.json                # Project manifest
```

---

## 🔒 Lisensi

Proyek ini dilisensikan di bawah lisensi MIT. Anda bebas menggunakannya untuk tujuan pribadi maupun komersial.
