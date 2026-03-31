#!/usr/bin/env bash
# Permitato infrastructure: install & configure Pi-hole v6
# Called by install_dev.sh when Permitato is in POTATO_IMAGE_APPS.
# Idempotent — safe to re-run.
set -euo pipefail

TARGET_ROOT="${POTATO_TARGET_ROOT:-/opt/potato}"
POTATO_USER="${POTATO_USER:-potato}"
POTATO_GROUP="${POTATO_GROUP:-potato}"

# Detect active network interface for Pi-hole DNS binding
_pihole_iface="$(ip route show default 2>/dev/null | awk '{print $5; exit}')"
_pihole_iface="${_pihole_iface:-eth0}"

if command -v pihole >/dev/null 2>&1; then
  printf 'Pi-hole already installed — skipping install, applying configuration.\n'
else
  printf 'Installing Pi-hole v6 (unattended, interface=%s)...\n' "${_pihole_iface}"
  mkdir -p /etc/pihole

  pihole_vars_tmp="$(mktemp)"
  cat > "${pihole_vars_tmp}" <<PIHOLE_VARS
PIHOLE_INTERFACE=${_pihole_iface}
PIHOLE_DNS_1=1.1.1.1
PIHOLE_DNS_2=8.8.8.8
QUERY_LOGGING=true
INSTALL_WEB_SERVER=true
INSTALL_WEB_INTERFACE=true
BLOCKING_ENABLED=true
DNSMASQ_LISTENING=local
WEBPASSWORD=
PIHOLE_VARS
  install -m 0644 "${pihole_vars_tmp}" /etc/pihole/setupVars.conf
  rm -f "${pihole_vars_tmp}"

  pihole_installer_tmp="$(mktemp)"
  curl -sSL https://install.pi-hole.net -o "${pihole_installer_tmp}"
  bash "${pihole_installer_tmp}" --unattended
  rm -f "${pihole_installer_tmp}"
fi

# Set web server to port 8081 (avoids conflict with llama-server on 8080)
# Enable allow_destructive so Permitato can flush DNS cache via restartdns.
if command -v pihole-FTL >/dev/null 2>&1; then
  pihole-FTL --config webserver.port 8081 || true
  pihole-FTL --config webserver.api.allow_destructive true || true
fi

# Generate app password if not already stored
if [ ! -f "${TARGET_ROOT}/config/permitato_pihole_password" ]; then
  pihole_pw="$(openssl rand -hex 16)"
  pihole setpassword "${pihole_pw}" || true
  pihole_pw_tmp="$(mktemp)"
  printf '%s\n' "${pihole_pw}" > "${pihole_pw_tmp}"
  install -m 0640 -o "${POTATO_USER}" -g "${POTATO_GROUP}" \
    "${pihole_pw_tmp}" "${TARGET_ROOT}/config/permitato_pihole_password"
  rm -f "${pihole_pw_tmp}"
fi

# Sudoers: let potato user manage pihole-FTL
pihole_sudoers_tmp="$(mktemp)"
cat > "${pihole_sudoers_tmp}" <<'SUDOERS'
potato ALL=(root) NOPASSWD: /bin/systemctl restart pihole-FTL
potato ALL=(root) NOPASSWD: /usr/bin/systemctl restart pihole-FTL
potato ALL=(root) NOPASSWD: /bin/systemctl stop pihole-FTL
potato ALL=(root) NOPASSWD: /usr/bin/systemctl stop pihole-FTL
potato ALL=(root) NOPASSWD: /bin/systemctl start pihole-FTL
potato ALL=(root) NOPASSWD: /usr/bin/systemctl start pihole-FTL
SUDOERS
install -m 0440 "${pihole_sudoers_tmp}" /etc/sudoers.d/potato-pihole
rm -f "${pihole_sudoers_tmp}"

systemctl restart pihole-FTL || true
printf 'Pi-hole configured — web UI at http://localhost:8081/admin/\n'
