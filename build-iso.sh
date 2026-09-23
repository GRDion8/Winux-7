#!/usr/bin/env bash
# Build on Arch Linux, not inside a target install. Does not flash any disks.
set -Eeuo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  printf 'Build Winux 7 on an installed x86_64 Arch Linux system.\nUsage: bash build-iso.sh [output-directory]\n\nRequests sudo when needed, installs missing Archiso tools (with a normal\npackage upgrade confirmation), and builds the ISO plus SHA-256 checksum.\nNeeds internet and at least 30 GiB free in /var/tmp. Do not run in a live ISO.\n'
  exit 0
fi
if (( $# > 1 )); then
  printf 'Usage: bash build-iso.sh [output-directory]\n' >&2
  exit 2
fi
if [[ $(uname -m) != x86_64 || ! -f /etc/arch-release ]]; then
  printf 'Build Winux 7 on an installed x86_64 Arch Linux system or Arch build VM.\n' >&2
  exit 1
fi
if [[ -d /run/archiso ]]; then
  printf 'Build from an installed Arch system, not the live ISO: its temporary storage is too small.\n' >&2
  exit 1
fi
if [[ $EUID != 0 ]]; then
  exec sudo bash "$source_dir/build-iso.sh" "$@"
fi
if ! command -v mkarchiso >/dev/null; then
  printf 'Installing Archiso build tools. Review the package manager upgrade confirmation.\n'
  pacman -Syu --needed archiso
fi
if [[ ! -f /usr/share/archiso/configs/releng/profiledef.sh ]]; then
  printf 'Archiso releng profile is missing. Reinstall the archiso package.\n' >&2
  exit 1
fi
available_kib=$(df -Pk /var/tmp | awk 'END {print $4}')
if (( available_kib < 30 * 1024 * 1024 )); then
  printf 'At least 30 GiB free in /var/tmp is required for the ISO build.\n' >&2
  exit 1
fi
output_dir=${1:-"$source_dir/iso-output"}
mkdir -p -- "$output_dir"
output_dir=$(realpath -- "$output_dir")
build_dir=$(mktemp -d /var/tmp/winux-iso.XXXXXXXX)
log_file="$build_dir/build.log"
exec > >(tee -a "$log_file") 2>&1
trap 'printf "\nBuild stopped. Diagnostic files were retained in %s\nLog: %s\n" "$build_dir" "$log_file"' ERR
printf 'Build workspace: %s\nISO output: %s\n' "$build_dir" "$output_dir"
# Keep the build tree on failure for diagnosis; mkarchiso manages its own mounts.
cp -a /usr/share/archiso/configs/releng "$build_dir/profile"
profile="$build_dir/profile"
install -d "$profile/airootfs/opt/winux-setup"
for file in setup.py engine.py locales.py desktop.py desktop-first-login.py update-desktop.py winux_profile.py winux-session.sh control-panel.cpp WINUX-DESKTOP.md DESKTOP.md wallpaper.jpg user.bmp hardware.py bootloader.py repair-boot.py BOOT-REPAIR.md network.py welcome.py launch.sh xsession.sh arch-win7-aero-postinstall.sh README.md TUTORIAL.md POSTINSTALL.md; do
  install -m 0644 "$source_dir/$file" "$profile/airootfs/opt/winux-setup/$file"
done
chmod 0755 "$profile/airootfs/opt/winux-setup/launch.sh" "$profile/airootfs/opt/winux-setup/xsession.sh"
cat >> "$profile/packages.x86_64" <<'EOF'
python
python-pillow
tk
xorg-server
xorg-xinit
xorg-xauth
xorg-xkbcomp
xorg-setxkbmap
openbox
ttf-dejavu
git
networkmanager
nm-connection-editor
network-manager-applet
EOF
sort -u -o "$profile/packages.x86_64" "$profile/packages.x86_64"
# The custom live image uses NetworkManager. The installed OS config is separate.
find "$profile/airootfs/etc/systemd/system" -type l \( -name 'iwd.service' -o -name 'systemd-networkd.service' -o -name 'systemd-networkd.socket' -o -name 'systemd-networkd-wait-online.service' \) -delete
install -d "$profile/airootfs/etc/systemd/system/multi-user.target.wants"
ln -sf /usr/lib/systemd/system/NetworkManager.service "$profile/airootfs/etc/systemd/system/multi-user.target.wants/NetworkManager.service"
# The releng profile already autologins root on the console. Preserve its setup.
cat >> "$profile/airootfs/root/.zlogin" <<'EOF'
if [[ $(tty) == /dev/tty1 && -z $DISPLAY ]]; then
  bash /opt/winux-setup/launch.sh
fi
EOF
cat >> "$profile/profiledef.sh" <<'EOF'
iso_name="winux-7"
iso_label="WINUX_$(date +%Y%m)"
iso_publisher="Winux 7"
iso_application="Winux 7"
file_permissions["/opt/winux-setup/launch.sh"]="0:0:755"
file_permissions["/opt/winux-setup/xsession.sh"]="0:0:755"
EOF
# Separate artifacts from older builds so only this run's images are published.
mkarchiso -v -w "$build_dir/work" -o "$build_dir/artifacts" "$profile"
shopt -s nullglob
images=("$build_dir/artifacts/"*.iso)
if (( ${#images[@]} == 0 )); then
  printf 'Archiso finished without producing an ISO. See %s\n' "$log_file" >&2
  exit 1
fi
for image in "${images[@]}"; do
  name=$(basename -- "$image")
  # Retain older images rather than silently replacing them on a same-day rebuild.
  if [[ -e "$output_dir/$name" ]]; then
    name="${name%.iso}-$(basename -- "$build_dir").iso"
  fi
  cp -- "$image" "$output_dir/$name"
  (cd -- "$output_dir" && sha256sum -- "$name" > "$name.sha256")
  if [[ ${SUDO_UID:-} =~ ^[0-9]+$ && ${SUDO_GID:-} =~ ^[0-9]+$ ]]; then
    chown "$SUDO_UID:$SUDO_GID" "$output_dir/$name" "$output_dir/$name.sha256"
  fi
  printf '\nWinux 7 ISO ready: %s\nChecksum: %s\n' "$output_dir/$name" "$output_dir/$name.sha256"
done
printf '\nBuild workspace and log retained at %s\n' "$build_dir"
