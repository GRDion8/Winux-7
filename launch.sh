#!/usr/bin/env bash
# Run from a booted Arch ISO; never run this on an installed desktop.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ${1:-} == --demo ]]; then
  exec python setup.py --demo
fi
if [[ $EUID != 0 || ! -d /run/archiso || $(uname -m) != x86_64 ]]; then
  printf 'Boot an x86_64 Arch ISO to install. For a safe preview: python setup.py --demo\n' >&2
  exit 1
fi
if ! python -c 'import tkinter; import PIL' 2>/dev/null || ! command -v startx >/dev/null || ! command -v openbox >/dev/null; then
  printf 'Preparing the graphical installer in the live environment. Connect to the internet first.\n'
  pacman -Sy --needed --noconfirm python python-pillow tk xorg-server xorg-xinit xorg-xauth xorg-xkbcomp xorg-setxkbmap openbox ttf-dejavu git
fi
if [[ -n ${DISPLAY:-} ]]; then
  exec python setup.py --install
fi
# Xorg runs locally on the live console. No browser server or remote API exists.
exec startx /bin/bash "$PWD/xsession.sh" -- :0 -nolisten tcp vt1
