"""Resolve requester IP to Pi-hole client IP via the kernel neighbor table."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def resolve_requester_ipv4(requester_ip: str, client_ips: set[str]) -> str | None:
    """Try to match the HTTP requester's IP to a Pi-hole client IPv4.

    If the requester is already an IPv4 in the client set, return it directly.
    Otherwise, look up the ARP/NDP neighbor table to map IPv6 → MAC → IPv4.
    Returns None if no match is found.
    """
    if not requester_ip:
        return None

    # Strip IPv4-mapped IPv6 prefix
    ip = requester_ip
    if ip.startswith("::ffff:"):
        ip = ip[7:]

    # Direct match (requester is already IPv4 and in client list)
    if ip in client_ips:
        return ip

    # Not a direct match — try neighbor table resolution
    mac = _ip_to_mac(ip)
    if not mac:
        return None

    return _mac_to_ipv4(mac, client_ips)


def _ip_to_mac(ip: str) -> str | None:
    """Look up a MAC address for an IP via the kernel neighbor table."""
    try:
        # Try IPv6 first (most common case: browser connects via IPv6)
        result = subprocess.run(
            ["ip", "-6", "neigh", "show"],
            capture_output=True, text=True, timeout=2,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == ip and parts[3] == "lladdr":
                return parts[4].lower()

        # Try IPv4
        result = subprocess.run(
            ["ip", "-4", "neigh", "show"],
            capture_output=True, text=True, timeout=2,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == ip and parts[3] == "lladdr":
                return parts[4].lower()
    except Exception:
        logger.debug("Neighbor table lookup failed for %s", ip, exc_info=True)

    return None


def _mac_to_ipv4(mac: str, client_ips: set[str]) -> str | None:
    """Find the IPv4 address that shares a MAC with the given address."""
    try:
        result = subprocess.run(
            ["ip", "-4", "neigh", "show"],
            capture_output=True, text=True, timeout=2,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[3] == "lladdr" and parts[4].lower() == mac:
                if parts[0] in client_ips:
                    return parts[0]
    except Exception:
        logger.debug("MAC-to-IPv4 lookup failed for %s", mac, exc_info=True)

    return None
