# Winux 7 desktop profile

Winux 7 now has a dedicated Control Panel and a fixed Aero appearance on top of Plasma. It is a desktop profile and settings front end, not a new window manager or a complete Windows implementation.

## Update your installed desktop

From your project checkout **inside the working Aero installation**:

```bash
git pull --ff-only
sudo python update-desktop.py --desktop-profile
```

Save your work and restart. The command builds the small native Qt Control Panel using the compiler and Qt development files already installed by Aero setup. It does not upgrade or remove packages, reinstall Aero, repartition, or reset your desktop. If a compiler dependency is missing, the build stops before changing the session. The build tools are `gcc`, `pkgconf`, and `qt6-base` on Arch.

The ordinary Start-menu Control Panel now opens Winux's settings categories instead of Plasma's Quick Settings page. It opens individual installed modules for networking, sound, display resolution, power, input devices, accounts, language, date, accessibility, and default applications. Missing optional components such as printers or Bluetooth are disabled visibly. The **Appearance and Looks → Desktop Background** page lets you browse for a picture and save it. There is no theme, Plasma Style, Global Theme, or Get New Themes selector. Wine settings and a Winux System information page are included.

The Aero Start menu's direct `systemsettings MODULE` actions are routed through the same approved module list. An unknown or appearance module opens Control Panel Home. Package-owned executables and their credits remain intact. Individual settings pages still use their underlying KDE controls: this is not a pixel-identical recreation of every Windows dialog.

## Fixed appearance and first login

The profile fixes the Aero global theme, widget style, color scheme, icon theme, cursor theme, splash and window decoration using system-level KConfig policy. SDDM continues to use the working Winux X11 session.

The appearance policy and taskbar/widget locks activate once the original Aero setup and Winux wallpaper/desktop setup have finished and the user starts their next session. This ordering is necessary: immutable keys and Plasma's layout lock prevent the configuration writes and scripting calls needed to initialize the desktop. On a fresh installation, a full-screen **Getting things ready** page waits for Aero, sets up the desktop and Wine, and verifies the wallpaper. It then restarts after a 15-second countdown; **Restart later** cancels that restart. The welcome appears after restarting. Failed setup shows an explanation and leaves setup available to retry on the next login. An inhibited restart leaves a button to continue to the desktop; restart normally from Start when ready. Completed installations do not restart automatically when applying this update.

Once locked, Plasma's Edit Mode and widget configuration are unavailable. The lock also prevents adding/removing pinned taskbar launchers or Start-menu favorites, as part of Plasma's layout policy. Normal application launching, taskbar Task Manager, files, screen locking, shutdown, and practical computer settings remain available. Wallpaper remains changeable through Control Panel.

This is an interface policy, not a security boundary. A user who intentionally bypasses the session environment or an administrator editing system files can change the desktop. Licensing information, credits and advanced recovery tools are not removed.

## Desktop background persistence

The old desktop finisher applied the wallpaper only once and removed its autostart entry. This version keeps a login task that restores the saved picture after Aero setup. It uses Plasma's dedicated `setWallpaper` API, which synchronizes its configuration and supports the locked desktop, then checks that the desktop reports the requested picture. It does not use the scripting API blocked by the layout lock.

The first restore uses the supplied Winux wallpaper. Choosing another picture in Control Panel saves a local copy under `~/.local/share/winux-7/wallpapers/` and records it in `~/.config/winux-7/wallpaper.json`. That choice survives restarts and removal of the original picture. One picture applies to all connected screens in the current activity. If a saved image is missing or unreadable, the task logs the failure without silently replacing that choice. Backgrounds chosen outside this page are superseded by the saved Winux choice at login.

For troubleshooting, read `~/.local/state/winux-desktop-v1/setup.log` and `~/.local/state/win7-aero-postinstall/first-login.log`. A harmless preparation-screen preview is available with `python desktop-first-login.py --demo` (Escape closes it).

## New installations

Aero installations apply the profile automatically. The standard Plasma fallback remains available in Setup and does not receive Aero-specific restrictions. Rebuild your ISO to bundle the new module, Control Panel source/header and session launcher.

New installations request an explicit Plasma runtime package list instead of `plasma-meta`: the desktop, X11 session, window manager, login manager, network/audio/power/display integration, authentication agent and file/portal integration. Existing installations are not pruned. Aero build dependencies and the previously requested Firefox, Wine and TMOG remain installed. Wayland-related libraries required by Plasma/Aero build dependencies remain even though login uses X11.

## Undo this profile

From the same updated project checkout:

```bash
sudo python update-desktop.py --remove-desktop-profile
```

Then restart. Original login and launcher files are restored from `/var/lib/winux-desktop-profile/manifest.json`; new profile files are removed. Later manual changes to managed files cause restoration to stop for review instead of silently losing those edits. This does not uninstall desktop packages or reset your wallpaper. Remove this profile before using the older full/defaults-only desktop updater, then reapply the profile afterward.

## Validation

Tests run the native Control Panel offscreen, exercise its approved action map and blocked appearance requests, inspect the staged ISO, verify installation/restoration against temporary roots, and test session-policy gating without starting a desktop. A private D-Bus test exercises wallpaper selection, copying, restoration after a desktop restart and rejection detection without connecting to the host desktop. An isolated real KConfig check confirms the immutable theme value takes precedence over a user override. No host desktop configuration is changed. A full installed Aero session and individual settings modules still need VM acceptance testing.

Implementation references: [KDE Kiosk policy](https://develop.kde.org/docs/administration/kiosk/keys/), [immutable configuration](https://develop.kde.org/docs/administration/kiosk/introduction/), and [Arch's minimal Plasma installation](https://wiki.archlinux.org/title/KDE).
