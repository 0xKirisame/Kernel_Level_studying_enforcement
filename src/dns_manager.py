#!/usr/bin/env python3
"""
dns_manager.py — Configure NetworkManager's built-in dnsmasq plugin to
whitelist only the domains listed in the jail config.

Non-whitelisted domains get SERVFAIL (no upstream defined for them).
Whitelisted domains are forwarded to 8.8.8.8.
"""

import subprocess
import socket
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

NM_CONF = Path("/etc/NetworkManager/NetworkManager.conf")
DNSMASQ_CONF_DIR = Path("/etc/NetworkManager/dnsmasq.d")
DNSMASQ_JAIL_CONF = DNSMASQ_CONF_DIR / "qudurat-jail.conf"
UPSTREAM_DNS = "8.8.8.8"


def _nm_uses_dnsmasq() -> bool:
    if not NM_CONF.exists():
        return False
    text = NM_CONF.read_text()
    return "dns=dnsmasq" in text


def enable_dnsmasq_in_nm() -> None:
    """Insert dns=dnsmasq into [main] section of NetworkManager.conf."""
    text = NM_CONF.read_text()
    if "dns=dnsmasq" in text:
        log.info("NetworkManager already using dnsmasq — skipping NM.conf edit")
        return

    lines = text.splitlines(keepends=True)
    new_lines = []
    in_main = False
    inserted = False
    for line in lines:
        new_lines.append(line)
        stripped = line.strip()
        if stripped == "[main]":
            in_main = True
        elif in_main and not inserted and (stripped.startswith("[") and stripped != "[main]"):
            new_lines.insert(-1, "dns=dnsmasq\n")
            inserted = True
            in_main = False

    if not inserted:
        if in_main:
            new_lines.append("dns=dnsmasq\n")
        else:
            new_lines.append("\n[main]\ndns=dnsmasq\n")

    NM_CONF.write_text("".join(new_lines))
    log.info("Added dns=dnsmasq to NetworkManager.conf")


def write_dnsmasq_jail_conf(config: dict[str, Any]) -> None:
    """Write the per-domain server= lines to the jail dnsmasq config."""
    DNSMASQ_CONF_DIR.mkdir(parents=True, exist_ok=True)
    domains = config.get("allowed_domains", [])

    lines = [
        "# qudurat-jail: auto-generated — do not edit manually\n",
        "no-resolv\n",          # ignore /etc/resolv.conf upstreams inside dnsmasq
        "server=\n",            # SERVFAIL for anything without an explicit server=
    ]
    for entry in domains:
        domain = entry["domain"]
        include_sub = entry.get("include_subdomains", False)
        if include_sub:
            # Forward <domain> and all *.domain to upstream
            lines.append(f"server=/{domain}/{UPSTREAM_DNS}\n")
        else:
            # Exact domain only — dnsmasq matches the exact label
            lines.append(f"server=/{domain}/{UPSTREAM_DNS}\n")

    DNSMASQ_JAIL_CONF.write_text("".join(lines))
    log.info("Wrote %s", DNSMASQ_JAIL_CONF)


def remove_dnsmasq_jail_conf() -> None:
    if DNSMASQ_JAIL_CONF.exists():
        DNSMASQ_JAIL_CONF.unlink()
        log.info("Removed %s", DNSMASQ_JAIL_CONF)


def reload_networkmanager() -> None:
    subprocess.run(["systemctl", "reload", "NetworkManager"], check=True)
    log.info("Reloaded NetworkManager")


def resolve_domain(domain: str) -> list[str]:
    """Return all IPv4 addresses for a domain (A records)."""
    try:
        results = socket.getaddrinfo(domain, None, socket.AF_INET)
        ips = list({r[4][0] for r in results})
        log.info("Resolved %s → %s", domain, ips)
        return ips
    except socket.gaierror as exc:
        log.warning("Could not resolve %s: %s", domain, exc)
        return []


def resolve_all_allowed(config: dict[str, Any]) -> list[str]:
    """
    Resolve every allowed domain (and www. variant if include_subdomains).
    Returns a deduplicated flat list of IPv4 addresses.
    """
    all_ips: set[str] = set()
    for entry in config.get("allowed_domains", []):
        domain = entry["domain"]
        include_sub = entry.get("include_subdomains", False)
        all_ips.update(resolve_domain(domain))
        if include_sub:
            all_ips.update(resolve_domain(f"www.{domain}"))
    return sorted(all_ips)


def apply(config: dict[str, Any]) -> list[str]:
    """Full DNS jail activation. Returns resolved IP list for firewall use."""
    enable_dnsmasq_in_nm()
    write_dnsmasq_jail_conf(config)
    reload_networkmanager()
    return resolve_all_allowed(config)


def remove() -> None:
    """Full DNS jail deactivation."""
    remove_dnsmasq_jail_conf()
    reload_networkmanager()
