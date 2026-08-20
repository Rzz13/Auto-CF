#!/bin/bash
# =======================================================
# Start Script for Ubuntu VPS (Xvfb + VNC + Node.js App)
# =======================================================

echo "[1/4] Memulai Virtual Display Xvfb (:99)..."
Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
sleep 2

echo "[2/4] Memulai x11vnc Server (port 5900)..."
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 > /dev/null 2>&1 &
sleep 1

echo "[3/4] Memulai noVNC Web Service (port 6080)..."
websockify --web /usr/share/novnc/ 6080 localhost:5900 > /dev/null 2>&1 &
sleep 1

echo "[4/4] Memulai Aplikasi Node.js di Display :99..."
DISPLAY=:99 node server.js
