#!/usr/bin/env bash
# Build on Arch Linux, not inside a target install. Does not flash any disks.
set -Eeuo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ $EUID != 0 ]] || ! command -v mkarchiso >/dev/null; then
  printf 'On an Arch build machine: sudo pacman -S archiso; then sudo bash build-iso.sh /absolute/output/directory\n' >&2
  exit 1
fi
output_dir=${1:-"$source_dir/iso-output"}
mkdir -p -- "$output_dir"
output_dir=$(realpath -- "$output_dir")
build_dir=$(mktemp -d /var/tmp/winux-iso.XXXXXXXX)
printf 'Build workspace: %s\nISO output: %s\n' "$build_dir" "$output_dir"
# Keep the build tree on failure for diagnosis; mkarchiso manages its own mounts.
cp -a /usr/share/archiso/configs/releng "$build_dir/profile"
profile="$build_dir/profile"
install -d "$profile/airootfs/opt/winux-setup"
for file in setup.py engine.py network.py welcome.py launch.sh xsession.sh arch-win7-aero-postinstall.sh README.md TUTORIAL.md POSTINSTALL.md; do
  install -m 0644 "$source_dir/$file" "$profile/airootfs/opt/winux-setup/$file"
done
chmod 0755 "$profile/airootfs/opt/winux-setup/launch.sh" "$profile/airootfs/opt/winux-setup/xsession.sh"
cat >> "$profile/packages.x86_64" <<'EOF'
python
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
iso_publisher="Winux 7 community project"
iso_application="Winux 7 Live Setup"
file_permissions["/opt/winux-setup/launch.sh"]="0:0:755"
file_permissions["/opt/winux-setup/xsession.sh"]="0:0:755"
EOF
mkarchiso -v -w "$build_dir/work" -o "$output_dir" "$profile"
printf '\nISO ready in %s\nBuild workspace retained at %s\n' "$output_dir" "$build_dir"
