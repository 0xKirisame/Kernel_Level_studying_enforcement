# CLAUDE.md

## Project Overview

**qudurat_kernel_jail** — A Linux study-enforcement jail for Arch Linux that:

1. Blocks all apps except Firefox (AppArmor)
2. Blocks DNS resolution except whitelisted educational/AI domains (dnsmasq via NetworkManager)
3. Blocks all network traffic except to whitelisted IPs (nftables)
4. Disables Firefox's built-in DoH (Firefox enterprise policies)
5. Uses AES-encrypted YAML config (password-protected whitelist)
6. Runs as `systemctl start/stop qudurat-jail`

## Project Structure

```
qudurat_kernel_jail/
├── config.yaml.example        # Plain example — copy, edit, then encrypt
├── config.yaml.enc            # Encrypted active config (git-ignored)
├── install.sh                 # One-time system setup (run as root, then reboot)
├── src/
│   ├── apply_rules.py         # ExecStart: decrypt config → apply all subsystems
│   ├── stop_rules.py          # ExecStop: tear down all rules cleanly
│   ├── config_manager.py      # encrypt / decrypt / edit YAML (CLI tool)
│   ├── firewall_manager.py    # nftables rule generation + IP resolution
│   ├── dns_manager.py         # dnsmasq config generation via NetworkManager
│   └── apparmor_manager.py    # AppArmor profile generation/loading
├── templates/
│   ├── nftables.j2            # Jinja2 nftables ruleset (reference)
│   └── dnsmasq.j2             # Jinja2 dnsmasq config (reference)
├── profiles/
│   └── qudurat-exec-jail      # AppArmor profile (regenerated at start)
├── firefox-policies/
│   └── policies.json          # Firefox enterprise policy
└── systemd/
    ├── qudurat-jail.service
    ├── qudurat-refresh.service
    └── qudurat-refresh.timer
```

## Setup Commands

```bash
# One-time install (installs packages, configures GRUB, copies files)
sudo bash install.sh

# Reboot to activate AppArmor kernel params
sudo reboot

# Create encrypted config
cp config.yaml.example config.yaml
# edit config.yaml as needed
python src/config_manager.py encrypt config.yaml
sudo cp config.yaml.enc /opt/qudurat-jail/

# Set password
sudo nano /etc/qudurat-jail/secret   # Set QUDURAT_PASSWORD=yourpassword

# Enable and start
sudo systemctl start qudurat-jail
sudo systemctl enable qudurat-refresh.timer
```

## Runtime Commands

```bash
sudo systemctl start qudurat-jail      # Enable all restrictions
sudo systemctl stop qudurat-jail       # Remove all restrictions
sudo systemctl status qudurat-jail     # Check status
journalctl -u qudurat-jail -f          # Follow logs

# Edit encrypted config
python src/config_manager.py edit /opt/qudurat-jail/config.yaml.enc
```

## Dependencies

- `apparmor`, `nftables` (system packages)
- `python-pyyaml`, `python-cryptography` (Python packages)
- NetworkManager with dnsmasq plugin (built-in, no extra install)
- Firefox 148+ at `/usr/bin/firefox`

## Verification After Start

```bash
nft list ruleset                      # Should show qudurat_jail table
cat /etc/resolv.conf                  # Should show 127.0.0.1
dig google.com                        # Should return SERVFAIL
dig qiyas.sa                          # Should resolve
curl -I https://youtube.com           # Should fail/timeout
curl -I https://nabeedu.com           # Should succeed
aa-status                             # Should show qudurat-exec-jail enforcing
```

## Notes

- AppArmor requires GRUB parameters + reboot (handled by install.sh)
- The jail profile is written to `/opt/qudurat-jail/profiles/` at runtime
- The refresh timer re-resolves CDN IPs every 30 minutes
- Password stored in `/etc/qudurat-jail/secret` (chmod 600, root-owned)
- Encrypted config at `/opt/qudurat-jail/config.yaml.enc`
