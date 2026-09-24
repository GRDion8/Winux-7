# Winux 7 desktop

Winux 7 provides one integrated desktop: its own theme package, session, Control Panel, fixed Aero appearance and bundled background. Plasma and Aero components supply the underlying window management and services; this is not a replacement for their entire codebase or a complete Windows implementation.

## Update your installed desktop

From your project checkout **inside the working Aero installation**:

```bash
git pull --ff-only
sudo python update-desktop.py --desktop-profile
```

Save your work and restart. The command builds the small native Qt Control Panel using the compiler and Qt development files already installed by Aero setup. It does not upgrade or remove packages, reinstall Aero, repartition, or reset your desktop layout. It replaces the active vendor wallpaper gallery with the Winux background and retains copies of the retired package-owned images for recovery. If a compiler dependency is missing, the build stops before changing the session. The build tools are `gcc`, `pkgconf`, and `qt6-base` on Arch.

The ordinary Start-menu Control Panel now opens Winux's settings categories instead of Plasma's Quick Settings page. It opens individual installed modules for networking, sound, display resolution, power, input devices, accounts, language, date, accessibility, and default applications. Missing optional components such as printers or Bluetooth are disabled visibly. The **Appearance and Looks → Desktop Background** page lets you browse for a picture and save it. There is no theme, Plasma Style, Global Theme, or Get New Themes selector. Wine settings and a Winux System information page are included.

The Aero Start menu's direct `systemsettings MODULE` actions are routed through the same approved module list. An unknown or appearance module opens Control Panel Home. Package-owned executables and their credits remain intact. Individual settings pages still use their underlying KDE controls: this is not a pixel-identical recreation of every Windows dialog.

## Fixed appearance and first login

The profile fixes the Aero global theme, widget style, color scheme, icon theme, cursor theme, splash and window decoration using system-level KConfig policy. SDDM continues to use the working Winux X11 session.

The appearance policy and taskbar/widget locks activate once the original Aero setup and Winux wallpaper/desktop setup have finished and the user starts their next session. This ordering is necessary: immutable keys and Plasma's layout lock prevent the configuration writes and scripting calls needed to initialize the desktop. On a fresh installation, a full-screen **Getting things ready** page waits for Aero, sets up the desktop and Wine, and verifies the wallpaper. It then restarts after a 15-second countdown; **Restart later** cancels that restart. The welcome appears after restarting. Failed setup shows an explanation and leaves setup available to retry on the next login. An inhibited restart leaves a button to continue to the desktop; restart normally from Start when ready. Completed installations do not restart automatically when applying this update.

Once locked, Plasma's Edit Mode and widget configuration are unavailable. The lock also prevents adding/removing pinned taskbar launchers or Start-menu favorites, as part of Plasma's layout policy. Normal application launching, taskbar Task Manager, files, screen locking, shutdown, and practical computer settings remain available. Wallpaper remains changeable through Control Panel.

This is an interface policy, not a security boundary. A user who intentionally bypasses the session environment or an administrator editing system files can change the desktop. Licensing information, credits and advanced recovery tools are not removed.

## Desktop background persistence

The Winux theme package (`org.winux7.desktop`) and Aero bootstrap defaults explicitly select the `Winux7` wallpaper package. Previously, Aero had no `[Wallpaper] Image` default, which lets the underlying desktop fall through to a vendor background. Setting the image after login alone did not cover later shell or screen initialization.

The supplied Windows 7 image is the only bundled background. Package-owned wallpapers from Plasma/Breeze are moved out of the active system gallery, using pacman's ownership records. Personal files and unrelated wallpaper packages are not deleted. A package-update hook reapplies the Winux defaults and retires vendor pictures that updates reintroduce. Recovery copies are kept under `/var/lib/winux-desktop-core/`.

The **Appearance and Looks → Desktop Background** page still lets you browse for a personal picture, as requested earlier. It saves a copy under `~/.local/share/winux-7/wallpapers/` and records the choice in `~/.config/winux-7/wallpaper.json`. If that copy becomes missing or unreadable, the desktop falls back to the bundled Winux image. The background service waits until initial setup finishes, then checks every five seconds for changes, including late shell initialization, shell restarts and newly connected screens. It writes only when the image differs. One saved picture applies to connected screens in the current activity; an activity switch is corrected on the next check. Choices made outside the Winux page are superseded by the saved choice.

For troubleshooting, read `~/.local/state/winux-desktop-v1/setup.log` and `~/.local/state/win7-aero-postinstall/first-login.log`. A harmless preparation-screen preview is available with `python desktop-first-login.py --demo` (Escape closes it).

## New installations

Every installation includes the Winux desktop. The standard Plasma option has been removed from Setup, and the installation engine rejects requests to omit Winux desktop setup before touching a disk. Rebuild your ISO to bundle the new module, Control Panel source/header and session launcher.

New installations request an explicit Plasma runtime package list instead of `plasma-meta`: the desktop, X11 session, window manager, login manager, network/audio/power/display integration, authentication agent and file/portal integration. Existing installations are not pruned. Aero build dependencies and the previously requested Firefox, Wine and TMOG remain installed. Wayland-related libraries required by Plasma/Aero build dependencies remain even though login uses X11.

## Undo this profile

From the same updated project checkout:

```bash
sudo python update-desktop.py --remove-desktop-profile
```

Then restart. Retired vendor wallpaper files and original theme defaults are restored from the core asset backups. Original login and launcher files are restored from `/var/lib/winux-desktop-profile/manifest.json`; new profile files are removed. Later manual changes to managed files cause restoration to stop for review instead of silently losing those edits. This does not uninstall desktop packages or reset your wallpaper. Remove this profile before using the older full/defaults-only desktop updater, then reapply the profile afterward.

## Validation

Tests run the native Control Panel offscreen, exercise its approved action map and blocked appearance requests, inspect the staged ISO, verify installation/restoration against temporary roots, and test session-policy gating without starting a desktop. A private D-Bus test exercises wallpaper selection, copying, late background resets, shell restarts and rejection detection without connecting to the host desktop. An isolated real KConfig check confirms the immutable theme value takes precedence over a user override. No host desktop configuration is changed. A full installed Aero session and individual settings modules still need VM acceptance testing.

Implementation references: [KDE Kiosk policy](https://develop.kde.org/docs/administration/kiosk/keys/), [immutable configuration](https://develop.kde.org/docs/administration/kiosk/introduction/), and [Arch's minimal Plasma installation](https://wiki.archlinux.org/title/KDE).
