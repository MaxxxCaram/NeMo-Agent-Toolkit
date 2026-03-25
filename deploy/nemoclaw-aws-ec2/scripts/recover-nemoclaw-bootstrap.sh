#!/bin/bash
# Run ON THE EC2 instance (as ubuntu with sudo) if the first boot failed before nemoclaw was installed.
# Adjust SANDBOX_NAME if yours is not my-assistant.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

SANDBOX_NAME="${SANDBOX_NAME:-my-assistant}"

sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release apt-transport-https software-properties-common

sudo apt-get remove -y docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc 2>/dev/null || true

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME:-$VERSION}") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu

curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt-get install -y nodejs
sudo npm install -g "github:NVIDIA/NemoClaw"

NEMOCLAW_BIN="$(command -v nemoclaw)"
test -x "$NEMOCLAW_BIN"

sudo install -d -m 0755 /etc/nemoclaw
if [[ ! -f /etc/nemoclaw/nemoclaw.env ]]; then
  sudo sh -c 'umask 077; printf "%s\n" "# Add TELEGRAM_BOT_TOKEN / NVIDIA_API_KEY as needed" > /etc/nemoclaw/nemoclaw.env'
  sudo chmod 600 /etc/nemoclaw/nemoclaw.env
  sudo chown root:root /etc/nemoclaw/nemoclaw.env
fi

sudo tee /etc/systemd/system/nemoclaw-aux.service >/dev/null <<UNIT
[Unit]
Description=NemoClaw auxiliary (Telegram bridge)
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu
Environment=HOME=/home/ubuntu
Environment=NEMOCLAW_SANDBOX=${SANDBOX_NAME}
Environment=SANDBOX_NAME=${SANDBOX_NAME}
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EnvironmentFile=-/etc/nemoclaw/nemoclaw.env
ExecStartPre=/bin/sh -c 'until docker info >/dev/null 2>&1; do sleep 2; done'
ExecStart=${NEMOCLAW_BIN} start
ExecStop=${NEMOCLAW_BIN} stop

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable nemoclaw-aux.service
sudo systemctl restart nemoclaw-aux.service || true

echo "Recover complete. Run: nemoclaw list (you may need a new login shell for docker group)."
