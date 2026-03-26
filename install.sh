#!/usr/bin/env bash
# install.sh — One-time setup for qudurat_kernel_jail
# Run as root: sudo bash install.sh
# After running, reboot so AppArmor kernel parameters take effect.

set -euo pipefail

INSTALL_DIR="/opt/qudurat-jail"
SECRET_DIR="/etc/qudurat-jail"
GRUB_CONF="/etc/default/grub"

# ── Colour helpers ────────────────────────────────────────────────────────────
red()  { echo -e "\e[31m$*\e[0m"; }
grn()  { echo -e "\e[32m$*\e[0m"; }
yel()  { echo -e "\e[33m$*\e[0m"; }
bold() { echo -e "\e[1m$*\e[0m"; }

die() { red "ERROR: $*"; exit 1; }

# ── Root check ────────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run this script as root (sudo bash install.sh)"

bold "=== qudurat_kernel_jail installer ==="

# ── 1. Install packages ───────────────────────────────────────────────────────
bold "1. Installing packages..."
pacman -S --needed --noconfirm \
    apparmor \
    nftables \
    python-pyyaml \
    python-cryptography \
    grub
grn "   Packages installed."

# ── 2. Enable AppArmor in GRUB ───────────────────────────────────────────────
bold "2. Configuring GRUB for AppArmor..."

AA_PARAMS="apparmor=1 lsm=landlock,lockdown,yama,integrity,apparmor,bpf"

if grep -q "apparmor=1" "$GRUB_CONF"; then
    yel "   AppArmor already present in GRUB config — skipping."
else
    # Append to GRUB_CMDLINE_LINUX_DEFAULT (handles empty or existing value)
    if grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=""' "$GRUB_CONF"; then
        sed -i "s|^GRUB_CMDLINE_LINUX_DEFAULT=\"\"|GRUB_CMDLINE_LINUX_DEFAULT=\"${AA_PARAMS}\"|" "$GRUB_CONF"
    else
        # Insert before closing quote
        sed -i "s|^GRUB_CMDLINE_LINUX_DEFAULT=\"\(.*\)\"|GRUB_CMDLINE_LINUX_DEFAULT=\"\1 ${AA_PARAMS}\"|" "$GRUB_CONF"
    fi
    grub-mkconfig -o /boot/grub/grub.cfg
    grn "   GRUB updated. A reboot is required to activate AppArmor."
fi

# ── 3. Enable AppArmor systemd service ───────────────────────────────────────
bold "3. Enabling AppArmor service..."
systemctl enable --now apparmor.service || yel "   (AppArmor service may need reboot to fully activate)"

# ── 4. Install project files ──────────────────────────────────────────────────
bold "4. Installing project to ${INSTALL_DIR}..."
mkdir -p "$INSTALL_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "$SCRIPT_DIR"/src         "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR"/profiles    "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR"/templates   "$INSTALL_DIR/"
[[ -f "$SCRIPT_DIR/config.yaml.enc" ]] && cp "$SCRIPT_DIR/config.yaml.enc" "$INSTALL_DIR/"
grn "   Project files installed to ${INSTALL_DIR}"

# ── 5. Firefox enterprise policies ───────────────────────────────────────────
bold "5. Installing Firefox enterprise policies (disables DoH)..."
FIREFOX_POLICY_DIR="/usr/lib/firefox/distribution"
mkdir -p "$FIREFOX_POLICY_DIR"
cp "$SCRIPT_DIR/firefox-policies/policies.json" "$FIREFOX_POLICY_DIR/"
grn "   Firefox policies installed."

# ── 6. Secret directory ───────────────────────────────────────────────────────
bold "6. Setting up secret directory (${SECRET_DIR})..."
mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"

if [[ ! -f "${SECRET_DIR}/secret" ]]; then
    cat > "${SECRET_DIR}/secret" <<'EOF'
# qudurat-jail secret file — chmod 600, root-owned
# Set QUDURAT_PASSWORD to the password used to encrypt config.yaml.enc
QUDURAT_PASSWORD=changeme
EOF
    chmod 600 "${SECRET_DIR}/secret"
    yel "   Created ${SECRET_DIR}/secret with placeholder password."
    yel "   IMPORTANT: Edit ${SECRET_DIR}/secret and set the real password!"
else
    grn "   Secret file already exists — skipping."
fi

# ── 7. Systemd units ──────────────────────────────────────────────────────────
bold "7. Installing systemd units..."
cp "$SCRIPT_DIR/systemd/qudurat-jail.service"    /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/qudurat-refresh.timer"   /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/qudurat-refresh.service" /etc/systemd/system/
systemctl daemon-reload
grn "   Systemd units installed."

# ── 8. Check for encrypted config ────────────────────────────────────────────
bold "8. Checking for encrypted config..."
if [[ ! -f "${INSTALL_DIR}/config.yaml.enc" ]]; then
    yel "   No config.yaml.enc found at ${INSTALL_DIR}/config.yaml.enc"
    yel "   Create one with:"
    yel "     cp config.yaml.example config.yaml"
    yel "     # Edit config.yaml with your allowed domains"
    yel "     python src/config_manager.py encrypt config.yaml"
    yel "     sudo cp config.yaml.enc ${INSTALL_DIR}/"
else
    grn "   config.yaml.enc found."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
bold "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit ${SECRET_DIR}/secret and set QUDURAT_PASSWORD"
echo "  2. Copy your config.yaml.enc to ${INSTALL_DIR}/ (if not done)"
echo "  3. Reboot to activate AppArmor kernel parameters"
echo "  4. After reboot:"
echo "       sudo systemctl start qudurat-jail"
echo "       sudo systemctl enable qudurat-refresh.timer"
echo ""
if grep -q "apparmor=1" "$GRUB_CONF"; then
    yel "  *** REBOOT REQUIRED for AppArmor to take effect ***"
fi
