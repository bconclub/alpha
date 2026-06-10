#!/usr/bin/env bash
# Runs ON the VPS after git reset --hard origin/main (called by deploy-engine.yml).
set -e
cd /root/alpha/engine

echo ">>> Version on VPS: $(cat VERSION)"

echo ">>> Installing dependencies..."
pip3 install -r requirements.txt --break-system-packages --quiet

if [ ! -f /etc/systemd/system/alpha-bot.service ]; then
  echo ">>> Installing systemd service..."
  cp alpha-bot.service /etc/systemd/system/alpha-bot.service
  systemctl daemon-reload
  systemctl enable alpha-bot
fi

echo ">>> Restarting alpha-bot service..."
systemctl restart alpha-bot

sleep 5
systemctl is-active alpha-bot
echo ">>> Deploy complete."
