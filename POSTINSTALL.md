# Winux-7

## Arch Linux Windows 7 Aero desktop setup

A Bash post-install script that configures an existing Arch Linux installation with KDE Plasma, an X11 session, SDDM, and a Windows 7–style desktop using AeroThemePlasma.

This repository contains the setup wrapper, not an Arch installation image or Windows installer. Install Arch and create a regular desktop user before running it. The script does not partition disks or install the Arch base system.

## Files and compatibility

- `arch-win7-aero-postinstall.sh` — original setup script, version `2026.08.30`.
- `README.md` — usage, behavior, limitations, and recovery notes derived from the script.

The script targets AeroThemePlasma branch `Plasma/6.7` and expects Plasma `6.7.x`. These are the script's configured targets, not a claim that today's Arch packages or upstream branch are compatible. The upstream source is fetched at runtime without pinning a commit.

Upstream locations configured in the script:

- Primary: <https://gitgud.io/wackyideas/aerothemeplasma>
- Clone fallback: <https://github.com/aeroshell-desktop/aerothemeplasma>

## Before running

Use a fresh Arch installation, preferably testing in a virtual machine first. You need an existing regular user with a home directory, working internet and package repositories, and sufficient disk space and time for a full system upgrade and source build. Normal-user mode requires configured `sudo`; root mode installs the bootstrap packages itself.

Back up important data separately. AeroThemePlasma rebuilds or replaces desktop components, including KWin/libplasma; this is more extensive than selecting a theme. The script changes desktop configuration, enables services, and may change the network manager used after reboot. Its own backup is partial and is created **after** the initial full system upgrade.

## Quick start

Clone this repository with `git clone https://github.com/GRDion8/Winux-7.git` and enter it with `cd Winux-7`, or copy/download the script to your installed Arch system. Reboot into that installation, sign in at a TTY as the intended desktop user, inspect the script, and run:

```bash
bash arch-win7-aero-postinstall.sh --help
bash arch-win7-aero-postinstall.sh
```

The default invocation asks for confirmation and leaves rebooting to you. When stage 1 succeeds:

```bash
sudo systemctl reboot
```

To reboot automatically on success instead:

```bash
bash arch-win7-aero-postinstall.sh --reboot
```

From a root TTY, specify an existing regular user (replace `alice`):

```bash
bash arch-win7-aero-postinstall.sh --user alice --reboot
```

From a normal account, the equivalent root-wrapper invocation is:

```bash
sudo bash arch-win7-aero-postinstall.sh --user alice --reboot
```

Use `--user` with root-wrapper mode when targeting another account. In ordinary non-root mode, user commands execute as the invoking account.

At SDDM, choose the AeroThemePlasma/AeroShell X11 session if it is not already selected. The script attempts to preselect an Aero-named installed X11 session without enabling automatic login. The first Plasma login applies the desktop layout; log out and back in if some visual changes have not refreshed.

## What the script does

### Stage 1: setup from the terminal

1. Resolves the target user and asks for confirmation unless `--yes` is supplied.
2. Performs a full `pacman -Syu` upgrade and installs bootstrap/build tools.
3. Saves package lists, the existing user `.config` directory, and existing `/etc/sddm.conf.d` configuration when present.
4. Installs Plasma, X11, SDDM, Dolphin, Konsole, Ark, Kate, Gwenview, PipeWire/WirePlumber, NetworkManager, fonts, build dependencies, and optional Bluetooth packages.
5. Detects AMD, Intel, and NVIDIA graphics and installs the selected packages. NVIDIA mode chooses `nvidia-open-dkms` and attempts to locate headers for the running kernel. Driver suitability still depends on the hardware and kernel.
6. Checks the installed Plasma version when it can be determined. A mismatch stops execution unless `--force-plasma` is supplied. **This check occurs after package installation and the system upgrade.**
7. Enables SDDM and graphical boot. By default it disables `systemd-networkd` and its wait-online unit for future boots and enables NetworkManager; it does not stop the current network service immediately. It does not migrate existing network configuration or disable every other network manager.
8. Optionally copies Segoe-related font files from a directory you provide.
9. Clones or updates AeroThemePlasma and runs its `install.sh` as the desktop user, using Ninja and a parallel build. Root-wrapper mode temporarily grants that user passwordless sudo for the upstream installer and removes the rule on normal completion or shell exit.
10. Writes the SDDM theme configuration and system default cursor configuration, then installs a one-time desktop autostart task and records completion state.

### Stage 2: first Plasma login

The generated task waits for Plasma, applies the `authui7` look-and-feel with a layout reset, selects the `Windows7Aero` Kvantum profile when available, and configures Aero colors, Windows 7 icons, the `Seven-Black` Plasma theme, `aero-drop` cursors, double-click behavior, KWin effects, and task switchers. If Segoe UI is installed, it also configures that font.

The task writes a completion marker and removes its autostart entry after completion. Some optional commands allow errors, so a completion marker does not prove every visual effect loaded successfully. Failures applying the main look-and-feel leave the task armed for another login.

## Command-line options

| Option | Effect |
| --- | --- |
| `-h`, `--help` | Show help and exit without installing anything. |
| `-y`, `--yes` | Skip the wrapper confirmation and pass `--noconfirm` to pacman. Upstream installer prompts may still occur. |
| `--user USER` | Choose the desktop user, especially when running as root. Does not create an account. |
| `--fonts-dir DIR` | Import matching Segoe `.ttf` and `.ttc` files from the supplied directory, without recursively searching it. |
| `--gpu MODE` | Select `auto` (default), `amd`, `intel`, `nvidia-open`, or `none`. `none` skips extra GPU packages; baseline Mesa is still installed. |
| `--keep-network-stack` | Skip the NetworkManager/systemd-networkd service switch. NetworkManager is still included in the package list. |
| `--no-bluetooth` | Skip installing/enabling Bluetooth through the optional step. Does not remove existing Bluetooth software. |
| `--reset-first-login` | Remove the completion marker and re-arm the desktop setup. The next Plasma login resets the layout. |
| `--force-plasma` | Bypass the detected Plasma version mismatch. Does not make incompatible components work. |
| `--reboot` | Reboot automatically after stage 1 succeeds. |

Example retaining the existing network services and skipping optional Bluetooth setup:

```bash
bash arch-win7-aero-postinstall.sh --keep-network-stack --no-bluetooth
```

### Optional Windows fonts

No Microsoft fonts or Windows installation files are included or downloaded by this wrapper. If you have a Windows font source you are authorized to use:

```bash
bash arch-win7-aero-postinstall.sh --fonts-dir /mnt/win7/Windows/Fonts
```

Matching files are copied into `~/.local/share/fonts/Windows7/` for the target user. Without them, the installed fallback fonts remain available.

## Files, logs, and backups

Paths below use the target user's home directory:

| Path | Purpose |
| --- | --- |
| `~/.local/share/aerothemeplasma-src/` | Upstream source checkout and installer/uninstaller. |
| `~/.local/state/win7-aero-postinstall/backups/<timestamp>/` | Configuration backup, package lists, detected GPU information, and `RESTORE.txt`. |
| `~/.local/state/win7-aero-postinstall/stage1-complete` | Latest successful stage-1 metadata. |
| `~/.local/state/win7-aero-postinstall/first-login.log` | Appended first-login setup output. |
| `~/.local/state/win7-aero-postinstall/first-login-complete` | Marker preventing repeated layout application. |
| `~/.local/bin/aerothemeplasma-first-login.sh` | Generated graphical setup script. |
| `~/.config/autostart/aerothemeplasma-first-login.desktop` | One-time autostart entry, removed after completion. |
| `/etc/sddm.conf.d/99-aerothemeplasma.conf` | SDDM theme and cursor settings. |
| `/usr/share/icons/default/index.theme` | System default cursor setting. |
| `/var/lib/sddm/state.conf` | Last-user/session selection, written if an Aero X11 session is found. |

The generated first-login task respects `XDG_STATE_HOME`; the wrapper uses `~/.local/state`. A custom `XDG_STATE_HOME` can therefore cause their markers and log locations to differ.

The backup is not a full-system snapshot. It does not preserve every system file, package binary, or previous service state, and does not automatically undo an interrupted installation.

## Troubleshooting and maintenance

- **Installation stops:** read the terminal error and the indicated line. Correct the cause before rerunning. Rerunning performs package/setup work again; it is not an automatic rollback or resume from a checkpoint.
- **Plasma version mismatch:** check the upstream project's supported version before proceeding. Avoid treating `--force-plasma` as a compatibility fix.
- **Source download/build fails:** check repository access, branch availability, dependencies, and the upstream installer output. The GitHub mirror is used only after a failed initial primary clone. Existing checkouts continue to use their configured origin; a failed pull may leave the script building older local source.
- **Desktop appearance is incomplete:** inspect `first-login.log`, verify that you selected the intended Plasma X11 session, then log out/in. To explicitly reset and reapply the layout, rerun the wrapper with `--reset-first-login`; this repeats stage 1 as well.
- **No network after reboot:** the script does not migrate the old connection configuration. Configure your connection in NetworkManager, or use `--keep-network-stack` when retaining existing network services is necessary.
- **NVIDIA build problems:** verify that the selected driver supports your GPU and that headers match the installed kernel(s). Automatic selection does not establish hardware compatibility.
- **Forced shutdown during root-wrapper mode:** normal exit cleanup cannot run after power loss or a forced kill. Check whether `/etc/sudoers.d/90-win7-aero-postinstall-<username>` remains and remove that temporary rule as root if the installation is no longer running.
- **Later Plasma/KWin upgrades:** the custom components may need rebuilding. Check upstream compatibility before rerunning the wrapper or upstream installer.

## Recovery / removal

Read the relevant backup's `RESTORE.txt` first. The script records this starting point for removing upstream components:

```bash
cd ~/.local/share/aerothemeplasma-src
bash uninstall.sh
sudo pacman -S libplasma polkit-kde-agent
```

Run upstream removal from the target user's account, and consult the upstream uninstaller before executing it. These commands are not a complete reversal of the wrapper. Review and restore backed-up user/SDDM configuration as appropriate; review the added SDDM configuration, cursor default, autostart task, default boot target, and network/Bluetooth service choices separately. Package lists help identify the previous package selection but do not restore package versions. If the graphical login fails, use a TTY to perform recovery.

## Validation and licensing

The published wrapper was checked with `bash -n` and its `--help` path was executed. Full installation, reboot, source compilation, and graphical behavior have not been tested as part of preparing this repository. The script was preserved unchanged.

This repository includes a [GNU General Public License v3.0](LICENSE) file selected by the repository owner. AeroThemePlasma and other dependencies retain their own terms. Microsoft fonts are not redistributed here.
