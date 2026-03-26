#!/usr/bin/env python3
"""
firewall_manager.py — Apply and remove nftables rules for the qudurat jail.

The ruleset:
  - Drops all outbound traffic by default.
  - Allows loopback and established/related connections.
  - Allows DNS only to localhost (127.0.0.1) — blocks DoH to external resolvers.
  - Allows TCP 80/443 to whitelisted IPs only.
"""

import subprocess
import logging
from typing import Any

log = logging.getLogger(__name__)

TABLE_NAME = "qudurat_jail"
FAMILY = "inet"


def _nft(*args: str) -> None:
    cmd = ["nft"] + list(args)
    log.debug("nft: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _nft_silent(*args: str) -> bool:
    cmd = ["nft"] + list(args)
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def table_exists() -> bool:
    return _nft_silent("list", "table", FAMILY, TABLE_NAME)


def build_ruleset(allowed_ips: list[str], allow_ports: list[int]) -> str:
    if not allowed_ips:
        ip_elements = ""
    else:
        ip_elements = ", ".join(allowed_ips)

    ports_str = ", ".join(str(p) for p in allow_ports)

    ruleset = f"""
table {FAMILY} {TABLE_NAME} {{
  set allowed_ips {{
    type ipv4_addr
    flags interval
    elements = {{ {ip_elements} }}
  }}

  chain output {{
    type filter hook output priority 0; policy drop;

    # Allow loopback
    oif lo accept

    # Allow already-established connections
    ct state established,related accept

    # DNS only to localhost (blocks DoH to 8.8.8.8, 1.1.1.1, etc.)
    udp dport 53 ip daddr != 127.0.0.1 drop
    tcp dport 53 ip daddr != 127.0.0.1 drop

    # HTTP/HTTPS to whitelisted IPs only
    tcp dport {{ {ports_str} }} ip daddr @allowed_ips accept

    # Block everything else (policy drop handles it)
  }}
}}
"""
    return ruleset.strip()


def apply(allowed_ips: list[str], config: dict[str, Any]) -> None:
    allow_ports = config.get("firewall", {}).get("allow_ports", [80, 443])

    if table_exists():
        log.info("Deleting existing %s table before re-applying", TABLE_NAME)
        delete()

    ruleset = build_ruleset(allowed_ips, allow_ports)
    log.debug("Applying ruleset:\n%s", ruleset)
    subprocess.run(["nft", "-f", "-"], input=ruleset.encode(), check=True)
    log.info("nftables %s table applied with %d IPs", TABLE_NAME, len(allowed_ips))


def update_allowed_ips(allowed_ips: list[str]) -> None:
    """Flush and repopulate the allowed_ips set (used by the refresh timer)."""
    if not table_exists():
        log.warning("Table %s does not exist; skipping IP refresh", TABLE_NAME)
        return

    _nft("flush", "set", FAMILY, TABLE_NAME, "allowed_ips")
    if allowed_ips:
        elements = "{ " + ", ".join(allowed_ips) + " }"
        _nft("add", "element", FAMILY, TABLE_NAME, "allowed_ips", elements)
    log.info("Refreshed allowed_ips set with %d IPs", len(allowed_ips))


def delete() -> None:
    if table_exists():
        _nft("delete", "table", FAMILY, TABLE_NAME)
        log.info("Deleted nftables table %s", TABLE_NAME)
    else:
        log.info("nftables table %s not present — nothing to delete", TABLE_NAME)
