# qudurat_kernel_jail

A Linux study-enforcement jail for Arch Linux. Locks the system down to Firefox + a whitelist of study sites so there's nothing left to do but actually study.

> **Note:** This is purely vibecoded. I needed a kernel-level procrastination blocker and I was not going to let building it become the procrastination.

---

## What it does

- **Blocks all app execution** except Firefox (AppArmor)
- **Blocks all DNS** except whitelisted study/AI domains (dnsmasq via NetworkManager)
- **Blocks all network traffic** except to resolved IPs of whitelisted domains (nftables)
- **Disables Firefox DoH** so DNS blocking can't be bypassed (Firefox enterprise policy)
- **Blocks VPN extensions** in Firefox
- **AES-encrypted config** — the whitelist is password-protected so you can't easily edit it mid-session
- **Controlled via systemd** — `start` locks it down, `stop` restores everything

## Whitelisted domains (default)

- `qiyas.sa` — GAT/Qiyas official platform
- `nabeedu.com`
- `anaostori.com`
- `notebooklm.google.com`
- `gemini.google.com`
- `accounts.google.com`, `apis.google.com`, `gstatic.com` — required for Google services to work

Edit `config.yaml.example` to change the list.

---

## Setup

**1. Install**
```bash
sudo bash install.sh
sudo reboot   # required to activate AppArmor in kernel
```

**2. Create encrypted config**
```bash
cp config.yaml.example config.yaml
# edit config.yaml if you want different domains
python src/config_manager.py encrypt config.yaml
sudo cp config.yaml.enc /opt/qudurat-jail/
```

**3. Set password**
```bash
sudo nano /etc/qudurat-jail/secret
# Set: QUDURAT_PASSWORD=yourpassword
```

**4. Start**
```bash
sudo systemctl start qudurat-jail
sudo systemctl enable qudurat-refresh.timer   # refreshes CDN IPs every 30min
```

## Usage

```bash
sudo systemctl start qudurat-jail    # lock down
sudo systemctl stop qudurat-jail     # restore everything
sudo systemctl status qudurat-jail
journalctl -u qudurat-jail -f

# Edit the domain whitelist
python src/config_manager.py edit /opt/qudurat-jail/config.yaml.enc
```

## Verify it's working

```bash
nft list ruleset          # shows qudurat_jail table
dig google.com            # SERVFAIL
dig qiyas.sa              # resolves
curl https://youtube.com  # fails
curl https://nabeedu.com  # works
aa-status                 # qudurat-exec-jail enforcing
```

---

## Dependencies

```bash
sudo pacman -S apparmor nftables python-pyyaml python-cryptography
```

NetworkManager dnsmasq plugin is used (built-in, no separate install).

---

## Stack

- **AppArmor** — execution restriction
- **nftables** — network traffic filtering
- **dnsmasq** (via NetworkManager) — DNS whitelist
- **Firefox enterprise policies** — disable DoH + VPN extensions
- **Python** — glue (config crypto, rule generation, systemd entry points)
- **Fernet + PBKDF2-HMAC-SHA256** — config encryption
