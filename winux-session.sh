#!/bin/sh
# Winux 7 session policy. Keep KDE in the desktop identity for service integration.
set -eu
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
state_home=${XDG_STATE_HOME:-"$HOME/.local/state"}
policy=/etc/xdg/aerothemeplasma
# Aero's initial layout and wallpaper setup need the Plasma scripting API.
# Enable the permanent layout policy only once both finishers have succeeded.
if [ -f "$state_home/winux-desktop-v1/desktop-complete" ] &&
   { [ ! -f "$config_home/autostart/aerothemeplasma-first-login.desktop" ] ||
     [ -f "$state_home/win7-aero-postinstall/first-login-complete" ]; }; then
    policy="/etc/winux-7/locked:/etc/winux-7/theme:$policy"
fi
export XDG_CONFIG_DIRS="$policy:${XDG_CONFIG_DIRS:-/etc/xdg}"
export XDG_CURRENT_DESKTOP=KDE
export XDG_SESSION_DESKTOP=winux-7
export QT_QPA_PLATFORMTHEME=kde
export PLASMA_DEFAULT_SHELL=io.gitgud.wackyideas.desktop
export USE_UAC_AGENT=1
exec /usr/bin/startatp
