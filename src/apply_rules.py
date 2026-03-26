#!/usr/bin/env python3
"""
apply_rules.py — Entry point for `systemctl start qudurat-jail`.

Steps:
  1. Read password from /etc/qudurat-jail/secret
  2. Decrypt config.yaml.enc
  3. Parse YAML
  4. Apply DNS whitelist (dnsmasq via NetworkManager)
  5. Resolve whitelisted IPs
  6. Apply nftables firewall
  7. Apply AppArmor execution jail
"""

import sys
import logging
import yaml

from config_manager import decrypt_data, load_secret_file
from dns_manager import apply as dns_apply, resolve_all_allowed
from firewall_manager import apply as fw_apply, update_allowed_ips
from apparmor_manager import apply as aa_apply

CONFIG_ENC_PATH = "/opt/qudurat-jail/config.yaml.enc"
SECRET_PATH = "/etc/qudurat-jail/secret"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("apply_rules")


def _load_config() -> dict:
    password = load_secret_file(SECRET_PATH)
    with open(CONFIG_ENC_PATH, "rb") as fh:
        ciphertext = fh.read()
    plaintext = decrypt_data(ciphertext, password)
    config = yaml.safe_load(plaintext)
    if not isinstance(config, dict):
        raise ValueError("Invalid config format")
    return config


def refresh_ips_only() -> None:
    """Re-resolve domains and update the nftables set (no DNS/AppArmor changes)."""
    log.info("=== qudurat-jail: refreshing IP whitelist ===")
    try:
        config = _load_config()
    except Exception as exc:
        log.error("Config load failed: %s", exc)
        sys.exit(1)

    allowed_ips = resolve_all_allowed(config)
    log.info("Resolved %d IPs", len(allowed_ips))
    update_allowed_ips(allowed_ips)
    log.info("=== qudurat-jail: IP refresh complete ===")


def main() -> None:
    if "--refresh-ips-only" in sys.argv:
        refresh_ips_only()
        return

    log.info("=== qudurat-jail: applying rules ===")

    # 1–3. Load and decrypt config
    try:
        config = _load_config()
    except Exception as exc:
        log.error("Config load failed: %s", exc)
        sys.exit(1)

    # 4 & 5. DNS + IP resolution
    log.info("--- Applying DNS whitelist ---")
    try:
        allowed_ips = dns_apply(config)
        log.info("Resolved %d IPs total", len(allowed_ips))
    except Exception as exc:
        log.error("DNS apply failed: %s", exc)
        sys.exit(1)

    # 6. Firewall
    log.info("--- Applying nftables firewall ---")
    try:
        fw_apply(allowed_ips, config)
    except Exception as exc:
        log.error("Firewall apply failed: %s", exc)
        sys.exit(1)

    # 7. AppArmor
    log.info("--- Applying AppArmor execution jail ---")
    try:
        aa_apply(config)
    except Exception as exc:
        log.error("AppArmor apply failed: %s", exc)
        sys.exit(1)

    log.info("=== qudurat-jail: all rules applied successfully ===")


if __name__ == "__main__":
    main()
