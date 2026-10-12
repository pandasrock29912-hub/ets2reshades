#!/usr/bin/env bash
# =============================================================================
#  Provisions an Ubuntu server (Oracle Cloud Always-Free) to run the ETS2 store.
#
#  Run it from INSIDE the uploaded store folder on the server:
#      sudo bash deploy/setup_server.sh yoursubdomain.duckdns.org
#
#  What it does (all automatic):
#    - installs Python + Caddy (free HTTPS)
#    - creates the virtualenv and installs the app
#    - builds the product zips
#    - points .env at https://<domain> and enables proxy trust
#    - installs + starts a systemd service (auto-restarts on reboot)
#    - configures Caddy so Let's Encrypt issues a free HTTPS certificate
# =============================================================================
set -euo pipefail

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  echo "Usage: sudo bash deploy/setup_server.sh <yourdomain.duckdns.org>"
  exit 1
fi

# Re-run as root if invoked as a normal user (Oracle's default login is 'ubuntu').
if [ "$(id -u)" -ne 0 ]; then
  exec sudo bash "$0" "$DOMAIN"
fi

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "==> App folder : $APP_DIR"
echo "==> Domain     : https://$DOMAIN"

export DEBIAN_FRONTEND=noninteractive

echo "==> [1/6] Installing system packages (python3, caddy)..."
apt-get update -y >/dev/null
apt-get install -y python3 python3-venv python3-pip caddy >/dev/null

echo "==> [2/6] Creating virtualenv + installing Python deps..."
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

echo "==> [3/6] Building product zips..."
.venv/bin/python build_products.py

echo "==> [4/6] Pointing .env at https://$DOMAIN and enabling TRUST_PROXY..."
set_env() {  # set_env KEY VALUE
  if grep -q "^$1=" .env; then sed -i "s#^$1=.*#$1=$2#" .env; else echo "$1=$2" >> .env; fi
}
set_env SITE_URL "https://$DOMAIN"
set_env TRUST_PROXY "true"
# Ensure the data dir exists and is writable
mkdir -p data

echo "==> [5/6] Installing systemd service (auto-start on boot)..."
cat > /etc/systemd/system/ets2store.service <<EOF
[Unit]
Description=ETS2 Photorealism store
After=network.target

[Service]
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 --timeout 60 server.app:app
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable ets2store >/dev/null 2>&1
systemctl restart ets2store

echo "==> [6/6] Configuring Caddy for free HTTPS on $DOMAIN..."
cat > /etc/caddy/Caddyfile <<EOF
$DOMAIN {
    encode gzip
    reverse_proxy 127.0.0.1:8000
}
EOF
systemctl enable caddy >/dev/null 2>&1
systemctl restart caddy

echo
echo "=================================================================="
echo "  DONE. It can take ~30-60s for the HTTPS certificate."
echo "  Visit:  https://$DOMAIN"
echo
echo "  Useful commands:"
echo "    systemctl status ets2store      # is the store running?"
echo "    journalctl -u ets2store -f      # live store logs"
echo "    journalctl -u caddy -f          # live HTTPS logs"
echo "    systemctl restart ets2store     # after editing .env"
echo
echo "  NEXT: edit $APP_DIR/.env"
echo "    - paste your LIVE PayPal Client ID + Secret"
echo "    - set PAYPAL_ENV=live"
echo "    then:  systemctl restart ets2store"
echo "=================================================================="
