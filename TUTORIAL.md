# Install Winux 7

Winux installs Arch Linux and gives it a Windows 7–inspired desktop. The new graphical Setup runs **from a booted Arch live ISO**. The older `arch-win7-aero-postinstall.sh` remains available for machines that already have Arch installed.

For the new X11, wallpaper, application defaults and an update without reinstalling, see [Desktop update](DESKTOP.md).

This is a development release. A full VM install/boot validation is still required. Try it on a disposable virtual machine before using hardware.

## 1. Try the appearance without installing

On a Linux desktop with Python, Tk and Pillow installed:

```bash
git clone https://github.com/GRDion8/Winux-7.git
cd Winux-7
python setup.py --demo
```

On Arch, install the preview dependencies with `sudo pacman -S python tk ttf-dejavu` if needed. Other distributions use their own package manager. Preview runs as your normal account. It shows a fictional 128 GiB SSD and installation USB, and uses simulated progress. Even its final “Simulate installation” button cannot install anything. Use a made-up password in the preview.

## 2. Prepare a test computer

For the first test, create a VM with:

- x86_64 CPU, preferably 4 or more virtual cores;
- 8 GiB RAM recommended for the live desktop and source builds;
- a new virtual disk of at least 64 GiB (the installer enforces 48 GiB minimum);
- internet access, usually the VM's default NAT network;
- a current official Arch Linux ISO attached as its virtual DVD;
- UEFI or legacy BIOS enabled; test both separately;
- no physical disks passed through to the VM.

For hardware, make a separate backup and unplug drives you do not intend to erase. Prepare boot media using your trusted ISO-writing tool. Download the official ISO from [Arch Linux](https://archlinux.org/download/) and follow its verification instructions. Secure Boot signing is not included in this project.

## 3. Boot the stock Arch ISO

Choose the Arch live environment from the boot menu. Its console automatically signs in as root.

### Connect to the internet

With Ethernet or a VM's NAT network, the connection will usually already work. For Wi-Fi:

```text
iwctl
device list
station wlan0 scan
station wlan0 get-networks
station wlan0 connect "Your Wi-Fi name"
exit
```

Replace `wlan0` with the device name shown by `device list`. Enter the Wi-Fi password when prompted. Do not put your password in a shared script or command example.

### Download and start Setup

Run these commands **only in the live ISO**:

```bash
pacman -Sy --needed git
git clone https://github.com/GRDion8/Winux-7.git
cd Winux-7
bash launch.sh
```

The launcher downloads the small graphical environment into the disposable live system. It does not install Arch onto your disk at this point. It refuses to launch real installation outside an x86_64 Archiso root session.

If package installation reports no space left, the ISO's writable RAM overlay is full. Boot the custom ISO described below (graphical dependencies are already included), or restart the VM with more RAM. Do not attempt to solve this by deleting unknown files from a physical drive.

## 4. Follow the wizard

### Welcome

Choose **Install now**. A preview instead says **Try the setup** and clearly labels itself as non-destructive.

### Preferences

Choose the installed system's language/format, keyboard, and time zone. Setup itself remains English. Click **Apply keyboard**, then type a few characters in the keyboard test. Confirm this before entering your account password.

### Connection and desktop

Keep internet access active. On the custom ISO, **Network settings** opens a Wi-Fi picker; choose your network and enter its password. Use Advanced for hidden or enterprise networks. On the stock ISO, keep the connection made with `iwctl` before launching.

Winux 7 always installs its own desktop. Source compilation can take substantially longer than installing the base system. If the available repositories are incompatible with the desktop's underlying Plasma 6.7 components, Setup stops before erasing. There is no alternate generic desktop option.

### Drive selection

Choose the whole disk, checking its path, model, capacity, and serial number. Mounted drives, swap devices, active storage mappings, read-only drives, and disks below the minimum size are unavailable. Installation media with a mounted filesystem is blocked.

Only **erase the entire selected disk** is supported. Existing Windows partitions, Linux partitions, and recovery partitions on that disk will all be lost. This version does not shrink partitions, preserve data, or create a dual-boot setup. Filesystem labels and free-space estimates are not used to infer that data is disposable.

### Your account

Enter a lowercase user name, computer name, and password of at least 8 characters. This account can use `sudo` with its password. The root account is locked; automatic login is off. Passwords are not saved in the installer configuration or logs.

### Final review

Review the exact disk and settings, then press **Install**. The Yes/No confirmation names the selected disk, its size and model. **No** is the default and leaves the disk unchanged. Choose **Yes** only when that is the drive you intend to erase; it permanently deletes all partitions and files on that disk. The preview uses simulated disks and never writes to a drive.

### Installation

Setup displays the active stage and live command output. The animated progress bar means work is ongoing; it is not a fake percentage or time estimate. The stages are:

1. Validate the live environment, disk identity, package metadata, and Aero compatibility.
2. Create GPT partitions and format the selected disk.
3. Install Arch, kernel/firmware, desktop packages, and audio.
4. Create your account, locale, clock, network service, and administrator access.
5. Build the Winux desktop and install its core theme, background and Control Panel.
6. Generate normal/fallback startup images, install GRUB, register the UEFI entry where applicable, and verify boot files.
7. Add the welcome guide, save the log, and unmount the target.

Do not remove power or close Setup while it is working. There is no mid-install cancellation or automatic rollback. Source builds may be quiet for a while. If an error occurs, Setup shows failure instead of claiming completion.

## 5. First start

When Setup reports success, select **Restart now**. Remove or detach the installation ISO/USB during restart. If firmware boots the USB again, choose the installed disk in its boot menu. UEFI registers a Winux firmware entry and also supplies a fallback loader. If the system falls through to network/PXE boot, follow [Boot repair](BOOT-REPAIR.md) to repair the existing installation without erasing it.

The login screen uses the Winux 7 session automatically. Sign in with your new account. The Getting things ready screen finishes desktop and Wine configuration, then restarts after a countdown. The welcome appears after that restart. If setup fails, read its error and log instead of restarting repeatedly.

Use the Start menu for applications, Dolphin for files, and the network icon for Wi-Fi. The live ISO's saved network passwords are not copied to the installed system, so connect to Wi-Fi again if necessary. Your existing Windows software and drivers do not automatically run on Linux.

Microsoft fonts are not bundled. The optional font-import instructions are in [POSTINSTALL.md](POSTINSTALL.md).

## 6. Build an ISO that opens Setup automatically

This is the most convenient path for end users after the image has been built and tested. The custom live image includes the graphical dependencies and starts the wizard on console 1. It remains an **online installer**, not a self-contained offline OS image.

Use an installed x86_64 Arch Linux system or Arch VM with internet and at least **30 GiB free in `/var/tmp`**. Do not build inside the live ISO. With Git installed:

```bash
git clone https://github.com/GRDion8/Winux-7.git
cd Winux-7
bash build-iso.sh
```

The script requests sudo itself. If Archiso is missing, it installs it with a normal package-manager upgrade confirmation. After that, building is automatic. An optional output directory can be supplied: `bash build-iso.sh /path/to/output`.

The script copies the system's current `releng` profile into a unique build directory under `/var/tmp`, includes Setup and its graphical dependencies, and calls `mkarchiso`. It never flashes a disk. Build artifacts are retained for troubleshooting, and the final ISO and matching `.iso.sha256` file go in `iso-output`. The script prints their exact paths and retains `build.log` in its build directory on failure. Older same-name images are kept. Verify the output with `sha256sum -c NAME.iso.sha256` from that directory.

Use a display resolution of at least 1024×768. Test that ISO in a VM before copying it to installation media. Choose **Network settings** if you need Wi-Fi. The custom image uses NetworkManager in the live session; the stock ISO path retains its existing network stack.

No prebuilt ISO or signed release is supplied; the builder generates a SHA-256 checksum for each image it produces. A user has successfully built and booted the custom ISO; full installation validation is still ongoing. Archiso package changes can require updates to the builder.

## First sign-in

After installing, let the **Getting things ready** screen finish. It waits for Aero configuration, initializes Wine for your account and verifies the background. Winux restarts after a 15-second countdown; you can choose **Restart later**. If a stage fails, an error and a setup-log button appear instead of restarting. Sign in again to retry once the problem is resolved.

After that restart, the welcome and finished desktop appear. Change the wallpaper through **Control Panel → Appearance and Looks → Desktop Background**. Your selected picture is copied locally and restored on later logins. See [the desktop profile guide](WINUX-DESKTOP.md) to update an existing installation.

## Updating Setup on an existing live ISO

An ISO contains the code as it existed when you built it. To use an installer fix without rebuilding the ISO, close the failed Setup window, return to the live terminal, and run:

```bash
cd /root
git clone https://github.com/GRDion8/Winux-7.git Winux-7-fixed
cd Winux-7-fixed
bash launch.sh
```

Use a new folder name if `Winux-7-fixed` already exists, or run `git pull --ff-only` inside that checkout. This downloads only the project, so you do not need to reinstall the graphical dependencies already present on the custom ISO. The current version fixes the EFI mount error “Can't find a SQUASHFS superblock.” Start Setup again and carefully reselect the target disk; retrying installation erases it again.

To embed the fix into a new ISO instead, update your build-machine checkout with `git pull --ff-only` and run `sudo bash build-iso.sh "$PWD/iso-output"` again. Boot the newly built ISO, not the old one.

## If something goes wrong

- **Setup will not open on your usual desktop:** run `python setup.py --demo`. Real mode requires booting the ISO.
- **No graphical display:** the launcher needs a local console with working Xorg graphics. Run it from tty1. Switch to tty2 with Ctrl+Alt+F2 to inspect errors, and back to tty1 with Ctrl+Alt+F1.
- **No available drive:** check that the test disk is at least 48 GiB and is not mounted or being used as swap/LVM/RAID. Do not force-select a busy device. Reboot the live ISO if previous tools mounted it.
- **Aero version mismatch:** no target disk writes have occurred in this preflight failure. Use a compatible repository/package set, or select standard Plasma. The installer does not force unsupported versions.
- **Download or source build failure after partitioning:** the disk is already partly installed and may not boot. There is no automatic resume. Save the log, fix the cause, reboot the live environment, and reinstall on the disposable target. Reinstalling erases it again.
- **Cleanup/unmount error:** shut down before unplugging the selected drive. Do not treat the installation as fully verified.
- **NVIDIA graphics problems:** automatic proprietary driver setup is outside this release. Use a VM or supported graphics device for initial validation; hardware-specific drivers may require manual setup.
- **Installed desktop looks incomplete:** inspect the first-login log below and check the chosen X11 session. See `POSTINSTALL.md` for theming details.

### Log locations

- During installation: `/var/log/winux-setup.log` in the live environment.
- If the target reached the filesystem stage, Setup attempts to copy that log to the installed system at `/var/log/winux-setup.log` (root-readable).
- After first login: `~/.local/state/win7-aero-postinstall/first-login.log`.

Save the live log before rebooting; the live filesystem is temporary. Review it before sharing, as it contains drive identifiers and paths (but not the account password).

## Updates and recovery

Arch is a rolling-release system. Before upgrading Plasma/KWin, check AeroThemePlasma compatibility. Rebuilding Aero may be necessary after upgrades. The wrapper's configuration backup is not a disk backup and cannot recover data erased by Setup.

For a standard Arch installation/recovery reference, see the [Arch installation guide](https://wiki.archlinux.org/title/Installation_guide). For theme changes and source rebuilds, consult [AeroThemePlasma](https://github.com/aeroshell-desktop/aerothemeplasma/blob/Plasma/6.7/INSTALL.md).
