#!/usr/bin/env bash
# arch-win7-aero-postinstall.sh
#
# Fresh Arch Linux -> KDE Plasma X11 -> AeroThemePlasma (Windows 7-style) post-install.
# Designed for a freshly installed Arch system after the first reboot into a TTY.
#
# Targets AeroThemePlasma Plasma/6.7 (checked against Arch Plasma 6.7.x in Aug 2026).
# Upstream: https://gitgud.io/wackyideas/aerothemeplasma
#
# IMPORTANT
#   * AeroThemePlasma modifies/rebuilds pieces of KWin/libplasma. It is not a normal theme.
#   * X11 is installed and preferred because upstream currently considers it the more
#     complete AeroThemePlasma experience.
#   * Microsoft Segoe UI fonts are NOT downloaded. You may import them from your own
#     Windows 7 installation/ISO with --fonts-dir.
#   * A full system update is performed. Arch does not support partial upgrades.
#
# Typical use after rebooting a fresh Arch install:
#   1) Log in as your normal user
#   2) curl/wget/copy this script onto the machine
#   3) chmod +x arch-win7-aero-postinstall.sh
#   4) ./arch-win7-aero-postinstall.sh --reboot
#
# Root-TTY mode is also supported:
#   ./arch-win7-aero-postinstall.sh --user yourusername --reboot

set -Eeuo pipefail
IFS=$'\n\t'
umask 022

SCRIPT_VERSION="2026.08.30"
ATP_BRANCH="Plasma/6.7"
ATP_PRIMARY_REPO="https://gitgud.io/wackyideas/aerothemeplasma.git"
ATP_MIRROR_REPO="https://github.com/aeroshell-desktop/aerothemeplasma.git"

ASSUME_YES=0
REBOOT_AFTER=0
RESET_FIRST_LOGIN=0
KEEP_NETWORK_STACK=0
WITH_BLUETOOTH=1
TARGET_USER_ARG=""
FONTS_DIR=""
GPU_MODE="auto"       # auto|amd|intel|nvidia-open|none
FORCE_PLASMA=0

ROOT_MODE=0
TARGET_USER=""
TARGET_UID=""
TARGET_GID=""
TARGET_HOME=""
ATP_SRC=""
STATE_DIR=""
BACKUP_ROOT=""
BACKUP_DIR=""
FIRST_LOGIN_SCRIPT=""
FIRST_LOGIN_DESKTOP=""
FIRST_LOGIN_MARKER=""
TMP_SUDOERS=""
SUDO_KEEPALIVE_PID=""

# ---------- UI ----------
bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARNING:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Fresh Arch -> Windows 7 Aero KDE post-install

Usage:
  ./arch-win7-aero-postinstall.sh [options]

Options:
  -y, --yes                 Non-interactive confirmation / pacman --noconfirm.
      --user USER           Target desktop user. Required in ambiguous root mode.
      --fonts-dir DIR       Import Segoe UI fonts from your own Windows Fonts dir.
      --gpu MODE            auto|amd|intel|nvidia-open|none (default: auto).
      --keep-network-stack  Do not switch the next boot to NetworkManager.
      --no-bluetooth        Do not install/enable BlueZ.
      --reset-first-login   Re-arm the one-shot graphical theme setup.
      --force-plasma        Continue even if installed Plasma is not 6.7.x.
      --reboot              Reboot automatically when stage 1 succeeds.
  -h, --help                Show this help.

Examples:
  ./arch-win7-aero-postinstall.sh --reboot
  ./arch-win7-aero-postinstall.sh --fonts-dir /mnt/win7/Windows/Fonts --reboot
  sudo ./arch-win7-aero-postinstall.sh --user alice --reboot

What happens:
  Stage 1 (TTY): full upgrade, KDE Plasma, X11, SDDM, audio/network stack,
                 graphics userspace, AeroThemePlasma dependencies and source build.
  Stage 2 (first KDE login): applies authui7/Win7 layout, Kvantum, cursors, icons,
                             KWin Aero effects and other Windows-7-like settings once.
EOF
}

while (($#)); do
  case "$1" in
    -y|--yes) ASSUME_YES=1 ;;
    --reboot) REBOOT_AFTER=1 ;;
    --reset-first-login) RESET_FIRST_LOGIN=1 ;;
    --keep-network-stack) KEEP_NETWORK_STACK=1 ;;
    --no-bluetooth) WITH_BLUETOOTH=0 ;;
    --force-plasma) FORCE_PLASMA=1 ;;
    --user)
      shift; (($#)) || die "--user requires a username."
      TARGET_USER_ARG="$1"
      ;;
    --fonts-dir)
      shift; (($#)) || die "--fonts-dir requires a directory."
      FONTS_DIR="$1"
      ;;
    --gpu)
      shift; (($#)) || die "--gpu requires auto|amd|intel|nvidia-open|none."
      GPU_MODE="$1"
      case "$GPU_MODE" in
        auto|amd|intel|nvidia-open|none) ;;
        *) die "Invalid --gpu mode: $GPU_MODE" ;;
      esac
      ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1 (try --help)" ;;
  esac
  shift
done

# ---------- cleanup / error reporting ----------
cleanup() {
  if [[ -n "$SUDO_KEEPALIVE_PID" ]]; then
    kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
  fi
  if [[ -n "$TMP_SUDOERS" && -e "$TMP_SUDOERS" ]]; then
    rm -f "$TMP_SUDOERS" || true
  fi
}
trap cleanup EXIT
trap 'printf "\n\033[1;31mPost-install failed near line %s.\033[0m\n" "$LINENO" >&2; [[ -n "${BACKUP_DIR:-}" ]] && printf "Backup/state: %s\n" "$BACKUP_DIR" >&2; printf "Fix the reported error and rerun the same script.\n" >&2' ERR

# ---------- platform / user resolution ----------
command -v pacman >/dev/null 2>&1 || die "pacman not found. This script is for Arch Linux."
[[ -r /etc/os-release ]] || die "/etc/os-release is missing."
grep -Eiq '^(ID|ID_LIKE)=.*arch' /etc/os-release || warn "This system does not clearly identify as Arch Linux; continuing because pacman exists."

if (( EUID == 0 )); then ROOT_MODE=1; fi

resolve_target_user() {
  local candidate=""

  if [[ -n "$TARGET_USER_ARG" ]]; then
    candidate="$TARGET_USER_ARG"
  elif (( ! ROOT_MODE )); then
    candidate="$(id -un)"
  elif [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    candidate="$SUDO_USER"
  else
    mapfile -t _users < <(getent passwd | awk -F: '$3 >= 1000 && $3 < 60000 && $1 != "nobody" && $7 !~ /(nologin|false)$/ {print $1}')
    if ((${#_users[@]} == 1)); then
      candidate="${_users[0]}"
    elif ((${#_users[@]} == 0)); then
      die "No regular desktop user was found. Create one first, or pass --user USER."
    else
      die "Multiple regular users were found (${_users[*]}). Pass --user USER."
    fi
  fi

  getent passwd "$candidate" >/dev/null || die "User '$candidate' does not exist."
  TARGET_USER="$candidate"
  TARGET_UID="$(id -u "$TARGET_USER")"
  TARGET_GID="$(id -g "$TARGET_USER")"
  TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

  [[ -n "$TARGET_HOME" && -d "$TARGET_HOME" ]] || die "Home directory for $TARGET_USER is missing: $TARGET_HOME"
  (( TARGET_UID >= 1000 )) || warn "Target user has UID $TARGET_UID; normally a desktop user has UID >= 1000."

  ATP_SRC="$TARGET_HOME/.local/share/aerothemeplasma-src"
  STATE_DIR="$TARGET_HOME/.local/state/win7-aero-postinstall"
  BACKUP_ROOT="$TARGET_HOME/.local/state/win7-aero-postinstall/backups"
  FIRST_LOGIN_SCRIPT="$TARGET_HOME/.local/bin/aerothemeplasma-first-login.sh"
  FIRST_LOGIN_DESKTOP="$TARGET_HOME/.config/autostart/aerothemeplasma-first-login.desktop"
  FIRST_LOGIN_MARKER="$STATE_DIR/first-login-complete"
}
resolve_target_user

as_root() {
  if (( ROOT_MODE )); then
    "$@"
  else
    sudo "$@"
  fi
}

as_user() {
  if (( ROOT_MODE )); then
    runuser -u "$TARGET_USER" -- env \
      HOME="$TARGET_HOME" USER="$TARGET_USER" LOGNAME="$TARGET_USER" \
      PATH="/usr/local/sbin:/usr/local/bin:/usr/bin" "$@"
  else
    env HOME="$TARGET_HOME" USER="$TARGET_USER" LOGNAME="$TARGET_USER" "$@"
  fi
}

pacman_root() {
  local args=(pacman)
  (( ASSUME_YES )) && args+=(--noconfirm)
  args+=("$@")
  as_root "${args[@]}"
}

bold "Arch Linux -> Windows 7 Aero KDE post-install"
printf 'Version: %s\nTarget user: %s (%s)\nHome: %s\n\n' "$SCRIPT_VERSION" "$TARGET_USER" "$TARGET_UID" "$TARGET_HOME"
printf '%s\n' \
  "This performs a full Arch upgrade, installs KDE Plasma + X11 + SDDM," \
  "builds AeroThemePlasma from source, modifies KWin/libplasma components," \
  "and arms a one-shot setup that finishes the Win7 look on first KDE login."
printf '\n'

if (( ! ASSUME_YES )); then
  read -r -p "Continue? [y/N] " answer
  [[ "$answer" =~ ^[Yy]$ ]] || exit 0
fi

# ---------- privilege bootstrap ----------
if (( ROOT_MODE )); then
  info "Root wrapper mode: installing sudo/build bootstrap packages."
  pacman_root -Syu --needed sudo git base-devel pciutils ca-certificates

  # Upstream explicitly requires its installer to run as a normal user, but it invokes
  # sudo internally. Give only the chosen user temporary passwordless sudo, then remove it.
  TMP_SUDOERS="/etc/sudoers.d/90-win7-aero-postinstall-${TARGET_USER}"
  printf '%s ALL=(ALL:ALL) NOPASSWD: ALL\n' "$TARGET_USER" > "$TMP_SUDOERS"
  chmod 0440 "$TMP_SUDOERS"
  visudo -cf "$TMP_SUDOERS" >/dev/null || die "Temporary sudoers rule failed validation."
  info "Temporary sudo access armed for the upstream installer (removed automatically)."
else
  command -v sudo >/dev/null 2>&1 || die "sudo is not installed. Run this wrapper once as root with --user $TARGET_USER, or install/configure sudo first."
  info "Authenticating sudo."
  sudo -v
  (
    while sleep 50; do
      sudo -n true 2>/dev/null || exit
      kill -0 "$$" 2>/dev/null || exit
    done
  ) &
  SUDO_KEEPALIVE_PID=$!

  info "Updating the fresh Arch base and installing bootstrap packages."
  pacman_root -Syu --needed sudo git base-devel pciutils ca-certificates
fi

# ---------- backup ----------
TIMESTAMP="$(date +'%Y%m%d-%H%M%S')"
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
as_user mkdir -p "$BACKUP_DIR" "$STATE_DIR"

backup_if_exists() {
  local src="$1" dest="$2"
  [[ -e "$src" ]] || return 0
  as_root cp -a "$src" "$dest"
  as_root chown -R "$TARGET_UID:$TARGET_GID" "$dest"
}

info "Saving a pre-desktop backup/state snapshot."
as_user bash -c "pacman -Qqe > '$BACKUP_DIR/explicit-packages.txt' || true"
as_user bash -c "pacman -Q > '$BACKUP_DIR/all-packages.txt' || true"
backup_if_exists "$TARGET_HOME/.config" "$BACKUP_DIR/user-config"
if [[ -d /etc/sddm.conf.d ]]; then
  as_root cp -a /etc/sddm.conf.d "$BACKUP_DIR/sddm.conf.d"
  as_root chown -R "$TARGET_UID:$TARGET_GID" "$BACKUP_DIR/sddm.conf.d"
fi

cat > /tmp/win7-aero-restore.$$ <<EOF
Backup created: $TIMESTAMP
Target user: $TARGET_USER
AeroThemePlasma source tree: $ATP_SRC

Uninstall AeroThemePlasma itself (do this from a normal Plasma session / TTY):
  cd "$ATP_SRC"
  bash uninstall.sh
  sudo pacman -S libplasma polkit-kde-agent

The original explicit package list is in:
  $BACKUP_DIR/explicit-packages.txt

The first-login log will be in:
  $STATE_DIR/first-login.log
EOF
as_root install -o "$TARGET_UID" -g "$TARGET_GID" -m 0644 /tmp/win7-aero-restore.$$ "$BACKUP_DIR/RESTORE.txt"
rm -f /tmp/win7-aero-restore.$$
ok "Backup/state snapshot: $BACKUP_DIR"

# ---------- package installation ----------
info "Installing KDE Plasma, X11, SDDM, desktop essentials and AeroThemePlasma dependencies."

PACKAGES=(
  # Complete Plasma desktop + explicit X11 path
  plasma-meta plasma-x11-session kwin-x11 sddm sddm-kcm

  # Useful baseline desktop applications
  dolphin konsole ark kate gwenview

  # Network / audio / desktop integration
  networkmanager
  pipewire pipewire-audio pipewire-pulse wireplumber
  xdg-user-dirs xdg-utils

  # Font/rendering fallbacks
  fontconfig noto-fonts ttf-dejavu

  # AeroThemePlasma upstream Arch prerequisites
  git cmake extra-cmake-modules ninja curl unzip
  qt6-virtualkeyboard qt6-multimedia qt6-5compat qt6-wayland
  plasma-wayland-protocols wayland-protocols vulkan-headers
  plasma5support kvantum sddm sddm-kcm base-devel
  plasma-nm plasma-pa plasma-workspace plasma-desktop

  # General graphics baseline
  mesa
)

if (( WITH_BLUETOOTH )); then
  PACKAGES+=(bluez bluez-utils)
fi

pacman_root -S --needed "${PACKAGES[@]}"

# ---------- graphics detection ----------
detect_gpu_packages() {
  local pci=""
  pci="$(lspci -nn 2>/dev/null | grep -Ei 'VGA compatible controller|3D controller|Display controller' || true)"
  printf '%s\n' "$pci" > "$BACKUP_DIR/detected-gpu.txt"
  as_root chown "$TARGET_UID:$TARGET_GID" "$BACKUP_DIR/detected-gpu.txt"

  local want_amd=0 want_intel=0 want_nvidia=0
  case "$GPU_MODE" in
    amd) want_amd=1 ;;
    intel) want_intel=1 ;;
    nvidia-open) want_nvidia=1 ;;
    none) return 0 ;;
    auto)
      grep -qiE 'AMD|ATI|\[1002:' <<<"$pci" && want_amd=1
      grep -qiE 'Intel|\[8086:' <<<"$pci" && want_intel=1
      grep -qiE 'NVIDIA|\[10de:' <<<"$pci" && want_nvidia=1
      ;;
  esac

  local gpupkgs=()
  (( want_amd )) && gpupkgs+=(mesa vulkan-radeon libva-mesa-driver)
  (( want_intel )) && gpupkgs+=(mesa vulkan-intel intel-media-driver)

  if (( want_nvidia )); then
    # nvidia-open-dkms avoids binding this script to one specific kernel package.
    # It is appropriate for modern NVIDIA GPUs; legacy cards may need another driver.
    local pkgbase headerpkg=""
    pkgbase="$(cat "/usr/lib/modules/$(uname -r)/pkgbase" 2>/dev/null || true)"
    [[ -n "$pkgbase" ]] && headerpkg="${pkgbase}-headers"
    gpupkgs+=(nvidia-open-dkms nvidia-utils egl-wayland)
    if [[ -n "$headerpkg" ]] && pacman -Si "$headerpkg" >/dev/null 2>&1; then
      gpupkgs+=("$headerpkg")
    else
      warn "Could not determine/install headers for the running kernel. NVIDIA DKMS may require your kernel's -headers package."
    fi
    warn "NVIDIA detected/selected: using nvidia-open-dkms. Older pre-Turing GPUs may require a legacy/closed driver instead."
  fi

  if ((${#gpupkgs[@]})); then
    info "Installing detected graphics userspace/driver packages: ${gpupkgs[*]}"
    pacman_root -S --needed "${gpupkgs[@]}"
  else
    warn "No AMD/Intel/NVIDIA display controller was detected; only Mesa baseline was installed."
  fi
}
detect_gpu_packages

# ---------- Plasma version guard ----------
if command -v plasmashell >/dev/null 2>&1; then
  PLASMA_VERSION="$(plasmashell --version 2>/dev/null | awk '{print $NF}' | head -n1 || true)"
  if [[ -n "$PLASMA_VERSION" && "$PLASMA_VERSION" != 6.7.* ]]; then
    if (( FORCE_PLASMA )); then
      warn "Installed Plasma is $PLASMA_VERSION; AeroThemePlasma branch $ATP_BRANCH targets Plasma 6.7.x. Continuing because --force-plasma was supplied."
    else
      die "Installed Plasma is $PLASMA_VERSION, but $ATP_BRANCH targets Plasma 6.7.x. Re-run with --force-plasma only if you accept possible breakage."
    fi
  fi
  ok "KDE Plasma ${PLASMA_VERSION:-6.7.x} installed."
fi

# ---------- services ----------
info "Configuring desktop services for the next boot."
as_root systemctl enable sddm.service
as_root systemctl set-default graphical.target

if (( ! KEEP_NETWORK_STACK )); then
  # Do not stop anything now (which could kill the connection running this script).
  # We only make NetworkManager the manager on the NEXT boot.
  as_root systemctl disable systemd-networkd.service systemd-networkd-wait-online.service 2>/dev/null || true
  as_root systemctl enable NetworkManager.service
else
  warn "Keeping the existing network stack; Plasma's network applet expects NetworkManager for full GUI management."
fi

if (( WITH_BLUETOOTH )); then
  as_root systemctl enable bluetooth.service
fi

# ---------- optional Segoe import ----------
install_segoe_fonts() {
  [[ -n "$FONTS_DIR" ]] || {
    warn "Segoe UI was not downloaded. For exact Win7 typography, rerun with --fonts-dir /path/to/Windows/Fonts from your own Windows installation/ISO."
    return 0
  }
  [[ -d "$FONTS_DIR" ]] || die "Fonts directory does not exist: $FONTS_DIR"

  local dest="$TARGET_HOME/.local/share/fonts/Windows7"
  as_root install -d -o "$TARGET_UID" -g "$TARGET_GID" -m 0755 "$dest"

  local count=0 font base
  while IFS= read -r -d '' font; do
    base="$(basename "$font")"
    as_root install -o "$TARGET_UID" -g "$TARGET_GID" -m 0644 "$font" "$dest/$base"
    ((count+=1))
  done < <(find "$FONTS_DIR" -maxdepth 1 -type f \( -iname 'segoe*.ttf' -o -iname 'segui*.ttf' -o -iname 'segoe*.ttc' -o -iname 'segui*.ttc' \) -print0)

  (( count > 0 )) || die "No Segoe UI font files were found in $FONTS_DIR"
  as_user fc-cache -f
  ok "Imported $count Segoe-related font files from your supplied Windows source."
}
install_segoe_fonts

# ---------- clone/update AeroThemePlasma ----------
info "Cloning/updating AeroThemePlasma $ATP_BRANCH as $TARGET_USER."
as_user mkdir -p "$(dirname "$ATP_SRC")"

if [[ -d "$ATP_SRC/.git" ]]; then
  as_user git -C "$ATP_SRC" fetch --all --prune
  as_user git -C "$ATP_SRC" checkout "$ATP_BRANCH"
  if ! as_user git -C "$ATP_SRC" pull --ff-only origin "$ATP_BRANCH"; then
    warn "Primary origin pull failed. Leaving the existing checked-out source tree intact."
  fi
elif [[ -e "$ATP_SRC" ]]; then
  die "$ATP_SRC exists but is not a Git checkout. Move/remove it and rerun."
else
  if ! as_user git clone --depth 1 --branch "$ATP_BRANCH" "$ATP_PRIMARY_REPO" "$ATP_SRC"; then
    warn "Primary GitGud clone failed; trying the read-only GitHub mirror."
    as_user git clone --depth 1 --branch "$ATP_BRANCH" "$ATP_MIRROR_REPO" "$ATP_SRC"
  fi
fi

[[ -f "$ATP_SRC/install.sh" ]] || die "AeroThemePlasma install.sh was not found after clone: $ATP_SRC"

# ---------- build/install upstream as a NORMAL user ----------
info "Building/installing AeroThemePlasma from source (including X11 components)."
CPU_JOBS="$(nproc 2>/dev/null || echo 2)"
as_user bash -lc "cd \"$ATP_SRC\" && CMAKE_GENERATOR=Ninja CMAKE_BUILD_PARALLEL_LEVEL=\"$CPU_JOBS\" bash install.sh"
ok "AeroThemePlasma source installation finished."

# ---------- SDDM Windows 7 theme ----------
info "Configuring the AeroThemePlasma SDDM/login screen."
as_root install -d -m 0755 /etc/sddm.conf.d
cat > /tmp/99-aerothemeplasma.conf.$$ <<'EOF'
[General]
GreeterEnvironment=QML_DISABLE_DISTANCEFIELD=1

[Theme]
Current=sddm-theme-mod
CursorTheme=aero-drop
EOF
as_root install -m 0644 /tmp/99-aerothemeplasma.conf.$$ /etc/sddm.conf.d/99-aerothemeplasma.conf
rm -f /tmp/99-aerothemeplasma.conf.$$

as_root install -d -m 0755 /usr/share/icons/default
printf '[Icon Theme]\nInherits=aero-drop\n' > /tmp/aero-index-theme.$$
as_root install -m 0644 /tmp/aero-index-theme.$$ /usr/share/icons/default/index.theme
rm -f /tmp/aero-index-theme.$$

[[ -d /usr/share/sddm/themes/sddm-theme-mod ]] || warn "Expected SDDM theme /usr/share/sddm/themes/sddm-theme-mod was not found after upstream install."

# Preselect an installed Aero X11 session in SDDM without enabling autologin.
AERO_X11_SESSION=""
if [[ -d /usr/share/xsessions ]]; then
  mapfile -t _aero_x11 < <(find /usr/share/xsessions -maxdepth 1 -type f \( -iname '*aero*.desktop' -o -iname '*aerotheme*.desktop' \) -printf '%f\n' 2>/dev/null | sort)
  if ((${#_aero_x11[@]} >= 1)); then
    AERO_X11_SESSION="${_aero_x11[0]}"
  fi
fi

if [[ -n "$AERO_X11_SESSION" ]]; then
  info "Preselecting SDDM session: $AERO_X11_SESSION (no autologin)."
  as_root install -d -o sddm -g sddm -m 0755 /var/lib/sddm
  cat > /tmp/sddm-state.$$ <<EOF
[Last]
User=$TARGET_USER
Session=$AERO_X11_SESSION
EOF
  as_root install -o sddm -g sddm -m 0600 /tmp/sddm-state.$$ /var/lib/sddm/state.conf
  rm -f /tmp/sddm-state.$$
else
  warn "No Aero-named X11 session file was found. At SDDM, use the session selector and choose AeroThemePlasma/AeroShell X11 if offered."
fi

# ---------- one-shot first graphical login ----------
info "Installing the one-shot first KDE login finisher."
as_user mkdir -p "$TARGET_HOME/.local/bin" "$TARGET_HOME/.config/autostart" "$STATE_DIR"

if (( RESET_FIRST_LOGIN )); then
  as_user rm -f "$FIRST_LOGIN_MARKER"
fi

cat > /tmp/aerothemeplasma-first-login.$$ <<'FIRSTLOGIN'
#!/usr/bin/env bash
# One-shot graphical finisher generated by arch-win7-aero-postinstall.sh.
set -Eeuo pipefail
IFS=$'\n\t'

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/win7-aero-postinstall"
MARKER="$STATE_DIR/first-login-complete"
LOG="$STATE_DIR/first-login.log"
AUTOSTART="$HOME/.config/autostart/aerothemeplasma-first-login.desktop"
mkdir -p "$STATE_DIR"
exec >>"$LOG" 2>&1

echo "=== AeroThemePlasma first-login setup: $(date --iso-8601=seconds) ==="
[[ -f "$MARKER" ]] && { echo "Already completed."; rm -f "$AUTOSTART"; exit 0; }

# Do not accidentally configure a non-Plasma desktop session.
if [[ "${XDG_CURRENT_DESKTOP:-}" != *KDE* && "${XDG_CURRENT_DESKTOP:-}" != *Plasma* ]]; then
  echo "Not a KDE Plasma session yet; keeping autostart armed for next login."
  exit 0
fi

# Plasma/DBus can still be registering services when XDG autostart starts.
for _ in {1..30}; do
  if pgrep -x plasmashell >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

kcfg() {
  local file="$1" group="$2" key="$3" value="$4"
  kwriteconfig6 --file "$file" --group "$group" --key "$key" "$value"
}

apply_lnf() {
  local rc=1
  for delay in 2 6 6; do
    sleep "$delay"
    if plasma-apply-lookandfeel -a authui7 --resetLayout; then
      rc=0
      break
    fi
    echo "Look-and-feel attempt failed; retrying."
  done
  return "$rc"
}

if ! command -v plasma-apply-lookandfeel >/dev/null 2>&1; then
  echo "plasma-apply-lookandfeel is missing; leaving first-login task armed."
  exit 1
fi

if ! apply_lnf; then
  echo "Could not apply authui7; leaving first-login task armed for another login."
  exit 1
fi

# Qt/Kvantum styling.
if command -v kvantummanager >/dev/null 2>&1; then
  kvantummanager --set Windows7Aero || echo "Kvantum profile selection returned an error."
fi
kcfg kdeglobals KDE widgetStyle kvantum

# Reinforce the parts of the look-and-feel that are especially important for Win7.
kcfg kdeglobals General ColorScheme Aero
kcfg kdeglobals Icons Theme "Windows 7 Aero"
kcfg plasmarc Theme name Seven-Black
kcfg kdeglobals KDE SingleClick false

if command -v plasma-apply-cursortheme >/dev/null 2>&1; then
  plasma-apply-cursortheme aero-drop --size 32 || true
fi
kcfg kcminputrc Mouse cursorTheme aero-drop
kcfg kcminputrc Mouse cursorSize 32

# AeroThemePlasma KWin stack.  These IDs match the project's current components;
# unknown keys are harmless, while the installed plugins consume the relevant ones.
enable_plugins=(
  smodpeekscript
  minimizeall
  aeroglassblur
  aeroglide
  smodglow
  smodpeekeffect
  libkwin_effect_smodsnap
  launchfeedback
  fadingpopupsaero
  squashaero
  dimscreenaero
  aeroshell-thumbnails
  minimize3d
)
disable_plugins=(
  blur contrast login logout maximize scale squash slide fade
  slidingpopups slidingnotifications dialogparent fadingpopups windowaperture
)
for plugin in "${enable_plugins[@]}"; do
  kcfg kwinrc Plugins "${plugin}Enabled" true
done
for plugin in "${disable_plugins[@]}"; do
  kcfg kwinrc Plugins "${plugin}Enabled" false
done

# Windows 7 task switchers shipped by AeroShell.
kcfg kwinrc TabBox LayoutName thumbnail_seven
kcfg kwinrc TabBoxAlternative LayoutName flip3d

# Windows 7 typography when the user supplied Segoe UI legally.
if fc-list 2>/dev/null | grep -qi 'Segoe UI'; then
  FONT9='Segoe UI,9,-1,5,50,0,0,0,0,0'
  FONT8='Segoe UI,8,-1,5,50,0,0,0,0,0'
  kcfg kdeglobals General font "$FONT9"
  kcfg kdeglobals General smallestReadableFont "$FONT8"
  kcfg kdeglobals General toolBarFont "$FONT9"
  kcfg kdeglobals General menuFont "$FONT9"
  kcfg kdeglobals WM activeFont "$FONT9"
fi

# Tell AeroThemePlasma's own OOTB logic that the equivalent setup was completed.
kcfg aerothemeplasmarc OOTB wizardRun true

if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 --noincremental || true
fi
if command -v qdbus6 >/dev/null 2>&1; then
  qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true
fi

printf 'completed_at=%s\n' "$(date --iso-8601=seconds)" > "$MARKER"
rm -f "$AUTOSTART"
echo "AeroThemePlasma first-login setup completed successfully."

if command -v notify-send >/dev/null 2>&1; then
  notify-send "Windows 7 Aero setup complete" "AeroThemePlasma was applied. Log out/in once if any visual element has not refreshed." || true
fi
FIRSTLOGIN

as_root install -o "$TARGET_UID" -g "$TARGET_GID" -m 0755 /tmp/aerothemeplasma-first-login.$$ "$FIRST_LOGIN_SCRIPT"
rm -f /tmp/aerothemeplasma-first-login.$$

if [[ ! -f "$FIRST_LOGIN_MARKER" ]]; then
  cat > /tmp/aerothemeplasma-first-login.desktop.$$ <<EOF
[Desktop Entry]
Type=Application
Name=Finish Windows 7 Aero setup
Comment=One-shot AeroThemePlasma first-login configuration
Exec=$FIRST_LOGIN_SCRIPT
Terminal=false
OnlyShowIn=KDE;
X-KDE-autostart-after=panel
X-KDE-StartupNotify=false
EOF
  as_root install -o "$TARGET_UID" -g "$TARGET_GID" -m 0644 /tmp/aerothemeplasma-first-login.desktop.$$ "$FIRST_LOGIN_DESKTOP"
  rm -f /tmp/aerothemeplasma-first-login.desktop.$$
else
  info "First-login marker already exists; keeping your existing desktop layout. Use --reset-first-login to re-arm it."
fi

# XDG user dirs are useful on a totally fresh user account. This does not require Plasma.
as_user xdg-user-dirs-update || true

# Record stage-1 state.
cat > /tmp/postinstall-stage1.$$ <<EOF
script_version=$SCRIPT_VERSION
completed_at=$(date --iso-8601=seconds)
target_user=$TARGET_USER
atp_branch=$ATP_BRANCH
atp_source=$ATP_SRC
backup=$BACKUP_DIR
aero_x11_session=$AERO_X11_SESSION
gpu_mode=$GPU_MODE
EOF
as_root install -o "$TARGET_UID" -g "$TARGET_GID" -m 0644 /tmp/postinstall-stage1.$$ "$STATE_DIR/stage1-complete"
rm -f /tmp/postinstall-stage1.$$

# Explicitly remove temporary root-mode sudo now rather than waiting for EXIT.
if [[ -n "$TMP_SUDOERS" && -e "$TMP_SUDOERS" ]]; then
  rm -f "$TMP_SUDOERS"
  TMP_SUDOERS=""
  ok "Temporary passwordless sudo rule removed."
fi

printf '\n'
bold "Stage 1 complete."
printf 'KDE Plasma + X11 + SDDM are installed.\n'
printf 'AeroThemePlasma source: %s\n' "$ATP_SRC"
printf 'Backup/state: %s\n' "$BACKUP_DIR"
printf 'First-login log: %s\n' "$STATE_DIR/first-login.log"
if [[ -n "$AERO_X11_SESSION" ]]; then
  printf 'SDDM will preselect: %s\n' "$AERO_X11_SESSION"
fi
printf '\nOn the first graphical login, the one-shot finisher will apply the Windows 7 layout/effects automatically.\n'
printf 'If SDDM does not preselect it, choose the AeroThemePlasma/AeroShell X11 session manually once.\n'
printf 'After major Plasma/KWin upgrades, rerun this post-install script or at least the upstream install.sh; AeroThemePlasma patches may need rebuilding.\n'

if (( REBOOT_AFTER )); then
  info "Rebooting into SDDM."
  as_root systemctl reboot
else
  printf '\nReboot when ready with:\n  sudo systemctl reboot\n'
fi
