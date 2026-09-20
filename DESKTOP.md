# Winux 7 desktop update

This update adds X11 as the default session, the supplied wallpaper, a Recycle Bin desktop link, Firefox, Wine with Mono/Gecko/Winetricks, and the native Linux version of TMOG.

## Update your working installation

Run this **inside your installed Winux 7 desktop**, not the live ISO. You do not need to reinstall, format a drive, or rebuild an ISO:

```bash
git clone https://github.com/GRDion8/Winux-7.git Winux-7-desktop
cd Winux-7-desktop
sudo python update-desktop.py
```

If you already have that checkout, run `git pull --ff-only` inside it instead of cloning again. If running directly as root, specify the desktop account with `--user YOUR_USERNAME`.

The updater first downloads and verifies TMOG, then uses a normal full Arch package upgrade to install the applications. Review the package manager's prompt. It preserves the bootloader and partition layout. It backs up the affected SDDM settings once, retains your existing login policy, and selects the new X11 session. It does **not** turn automatic login on.

Save your work and **restart** when it finishes. First-login setup then creates the desktop link, applies the wallpaper, makes Firefox the default browser, registers Windows executable associations, and initializes your user's Wine environment. An existing Wine prefix is retained. Wine can take a few minutes the first time.

## New installations and ISO builds

New installations automatically include these defaults. Update your source checkout and rebuild with `sudo bash build-iso.sh "$PWD/iso-output"` to embed the new installer UI and wallpaper in an ISO. An old ISO still contains its old code. You can instead clone the latest project into its live session and run `bash launch.sh`; it installs the image-display dependency if missing.

The format prompt is now **Yes/No**, defaults to **No**, and names the exact disk with its size/model. Selecting Yes authorizes erasing that entire disk. Mounted/live/busy-drive blocking and the final disk-identity checks remain in place.

The language/format list uses glibc's `/usr/share/i18n/SUPPORTED` catalog rather than a fixed shortlist. Type a language, country, or locale code to filter, then choose a listed value. Available entries depend on the ISO's glibc version (502 on the development system). The setup interface itself remains English; this selects installed-system language and formats. Keyboard selection remains separate.

## Applications

- **Firefox:** installed from the Arch repository and updated through the system package manager. This release uses Firefox rather than Helium.
- **Wine:** includes Wine, Wine Mono, Wine Gecko and Winetricks. “Windows Application Settings” opens `winecfg`; supported `.exe` and `.msi` files can open through Wine. The Wine environment belongs to your account and is never initialized as root. Current Arch Wine uses WoW64 for 32-bit and 64-bit applications; the installer does not force an incompatible 32-bit prefix. Application-specific runtimes and game compatibility still vary; this is not a guarantee that every Windows application runs. Use Winetricks for the particular application's requirements.
- **Task Manager:** launches TMOG's native Linux AppImage, with `fuse2` installed. The Plasma System Monitor launcher is overridden for the configured user so existing menu entries use TMOG. A dedicated Task Manager menu entry is also provided. TMOG runs as your user, not root. It is the free edition; no Pro license is supplied.

TMOG is downloaded directly from its publisher during installation, not redistributed in this repository or the ISO. The integration pins version **0.1.4**, SHA-256 `a9873347ee2b1a4895cf2c8f39660d8cf4b86ab89b24c08d541f237e365b4346`, matching the [publisher's release manifest](https://tmog.org/downloads/release-linux.json). A changed file fails verification. [Official release notes](https://tmog.org/release-notes.html). Updating this pinned release requires updating the verified URL/hash together; Arch's package manager does not update this AppImage.

## Wallpaper and desktop setup

`wallpaper.jpg` is the exact supplied Windows 7 wallpaper. The installer displays it behind the setup window, and the installed desktop applies it after Aero's initial layout setup finishes. This preserves the order so the theme does not immediately replace the selected wallpaper. The visual installer is a Linux/Tk recreation inspired by Windows 7, not Microsoft's native Windows setup executable.

To use a different wallpaper on the installed system:

```bash
sudo python update-desktop.py --wallpaper /absolute/path/to/image.jpg
```

The Recycle Bin link points to KDE's `trash:/` location and uses the account's localized desktop folder, such as `Desktop` or `Schreibtisch`. The account's existing Wine files are not deleted during repeat updates. Applying this updater again intentionally reapplies the requested default wallpaper and browser.

First-login log: `~/.local/state/winux-desktop-v1/setup.log`. If setup fails, its autostart remains enabled and it retries next login. Do not start that first-login script with sudo. Login changes take effect after restarting; the updater does not terminate your current desktop session.

The wallpaper remains third-party artwork supplied by the user and is not covered by this repository's GPL software license. TMOG, Firefox, Wine and the desktop components retain their respective licenses and names.
