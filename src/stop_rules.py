#!/usr/bin/env python3
"""
stop_rules.py — Entry point for `systemctl stop qudurat-jail`.

Tears down all jail subsystems cleanly:
  1. Remove AppArmor execution profile
  2. Delete nftables table
  3. Remove dnsmasq whitelist config, reload NetworkManager
"""

import logging

from apparmor_manager import remove as aa_remove
from firewall_manager import delete as fw_delete
from dns_manager import remove as dns_remove

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("stop_rules")


def main() -> None:
    log.info("=== qudurat-jail: removing rules ===")

    log.info("--- Removing AppArmor profile ---")
    try:
        aa_remove()
    except Exception as exc:
        log.error("AppArmor remove failed: %s", exc)

    log.info("--- Deleting nftables table ---")
    try:
        fw_delete()
    except Exception as exc:
        log.error("Firewall delete failed: %s", exc)

    log.info("--- Removing DNS whitelist ---")
    try:
        dns_remove()
    except Exception as exc:
        log.error("DNS remove failed: %s", exc)

    log.info("=== qudurat-jail: all rules removed ===")


if __name__ == "__main__":
    main()
