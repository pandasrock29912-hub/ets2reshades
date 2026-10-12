# Deploy to a free server (Oracle Cloud Always-Free) — $0/month

This walks you through putting the store on a **free, always-on server** so buyers
can reach it 24/7 — no hosting fee, no domain purchase. It's the longest setup
you'll ever do; after this it runs by itself.

You'll need about 25–40 minutes and a credit/debit card (for Oracle's identity
check — **you will not be charged**; the "Always Free" tier is genuinely free).

---

## PART A — Get the free server (Oracle Cloud)

### A1. Sign up
1. Go to **cloud.oracle.com** → **Start for Free** / **Sign up**.
2. Create an account with your email. Oracle asks for a card + phone to verify
   you're a person. **This is normal and you are not charged** — pick the
   **Always Free** tier, not a paid trial.

### A2. Create a VM (the free computer)
1. In the Oracle dashboard: **Menu → Compute → Instances → Create Instance**.
2. **Name** it `ets2store`.
3. **Image** → **Change image** → pick **Canonical Ubuntu** (22.04 or 24.04).
4. **Shape** → **Change shape** → select **VM.Standard.A1.Flex** (ARM). Set
   **1 OCPU** and **6 GB RAM** (both within Always Free).  
   *(If A1 isn't available, use **VM.Standard.E2.1.Micro** — 1 GB RAM, also free.)*
5. **SSH keys** → **Generate** (or paste your own). **Download the private key
   file** (ends in `.key` or `.pem`) — **save it somewhere safe**, you need it to
   log in. Keep the tab open.
6. **Networking** → accept the default VCN/subnet.
7. **Create** and wait ~2 min until it says **Running**.
8. Copy the **Public IP address** shown on the instance page.  
   *(Your VM must be **Running**, not Stopped — a stopped VM = store offline.)*

### A3. Open the web ports (IMPORTANT — store is unreachable without this)
1. On the instance page, click the **Subnet** link (or go to **Networking →
   Virtual Cloud Networks → your VCN → Default Security List**).
2. **Add Ingress Rules** and add **two** rules:
   | Source | Protocol | Dest port |
   |--------|----------|-----------|
   | `0.0.0.0/0` | TCP | `80` |
   | `0.0.0.0/0` | TCP | `443` |
3. (Port **22** for SSH is usually already open.)

---

## PART B — Get a free web address (DuckDNS)

You don't buy a domain — DuckDNS gives you a free HTTPS subdomain.

1. Go to **duckdns.org** → **Sign in** with Google/GitHub/Twitter.
2. Under **Domains**, type a name (e.g. `ets2store`) → **Add Domain**.  
   Your address is now **`ets2store.duckdns.org`**.
3. Click **update ip** next to your domain → paste your VM's **Public IP** → **Update**.
4. Still on that page, **copy your Token** (top right). You'll paste it in Part C.

---

## PART C — Put your store on the server

### C1. Package the store on YOUR computer
Your `.env` (PayPal + email settings) needs to go to the server too, so don't
exclude it. Open a terminal **in your store folder** (`ets2-photoreal-store`):

```bash
# Linux/macOS:
tar czf /tmp/ets2-store.tar.gz --exclude=.venv --exclude=data --exclude='*.db*' --exclude='__pycache__' --exclude='*.pyc' .

# Windows (PowerShell, Windows 10/11 has tar built in):
tar czf ets2-store.tar.gz --exclude=.venv --exclude=data --exclude="*.db*" --exclude="__pycache__" --exclude="*.pyc" .
```

### C2. Upload it to the server
`IP` = your VM's Public IP. `KEY` = the `.key`/`.pem` file you downloaded in A2.8.

```bash
# Linux/macOS:
scp -i KEY /tmp/ets2-store.tar.gz ubuntu@IP:~/

# Windows (PowerShell):
scp -i KEY ets2-store.tar.gz ubuntu@IP:~/
```

### C3. Log in and run the setup script
```bash
ssh -i KEY ubuntu@IP
mkdir -p ~/ets2store && tar xzf ~/ets2-store.tar.gz -C ~/ets2store
cd ~/ets2store
sudo bash deploy/setup_server.sh ets2store.duckdns.org
```
*(Use YOUR DuckDNS name from Part B, not the example.)*

The script installs everything, builds the zips, sets up free HTTPS, and starts
the store. When it finishes, wait ~60 seconds and open **`https://ets2store.duckdns.org`**.

---

## PART D — Tell the store where it lives + go LIVE

### D1. Point PayPal at your live site
On the server (you're still logged in via `ssh`):
```bash
nano /opt/ets2store/.env     # or: nano ~/ets2store/.env
```
Make these changes:
```
SITE_URL=https://ets2store.duckdns.org     ← your real address
PAYPAL_ENV=live                            ← switch from sandbox to live
PAYPAL_CLIENT_ID=<your LIVE Client ID>     ← from the Live tab of developer.paypal.com
PAYPAL_SECRET=<your LIVE Secret>
```
Save (`Ctrl+O`, Enter, `Ctrl+X`), then:
```bash
sudo systemctl restart ets2store
```

> Get the **LIVE** Client ID + Secret from developer.paypal.com → **Live** tab →
> your app (same place you got the sandbox ones). Keep them private — don't paste
> them in chat.

### D2. Test it
Open `https://ets2store.duckdns.org`, buy your own preset with real PayPal (you
can refund yourself), and confirm the key email arrives. Then you're live.

---

## Quick reference — running it day-to-day

| Task | Command (over `ssh -i KEY ubuntu@IP`) |
|------|----------------------------------------|
| Is it running? | `systemctl status ets2store` |
| See live logs | `journalctl -u ets2store -f` (Ctrl+C to exit) |
| Restart after edits | `sudo systemctl restart ets2store` |
| Rebuild zips after changing presets | `cd ~/ets2store && .venv/bin/python build_products.py && sudo systemctl restart ets2store` |
| Issue a key manually (lost email) | `cd ~/ets2store && .venv/bin/python -m server.cli reissue <order_id>` |

## Costs
* **Oracle Always-Free VM:** $0/month (keep it Running).
* **DuckDNS subdomain:** $0.
* **HTTPS certificate:** $0 (Caddy/Let's Encrypt auto-renews).
* **Total: $0.** The only thing you pay is for the presets people buy.

## Troubleshooting
* **Site won't open:** check ports 80/443 are open in Oracle (Part A3) and the VM
  is **Running**. DNS can take a few minutes after setting DuckDNS.
* **"502 Bad Gateway":** the store app crashed — `journalctl -u ets2store -f` for why.
* **HTTPS padlock missing:** Caddy may still be getting the cert — wait a few
  minutes and reload. Check `journalctl -u caddy -f`.
* **Oracle declined your signup:** common — try again, or use a different browser;
  Oracle sometimes rejects the first card attempt.
