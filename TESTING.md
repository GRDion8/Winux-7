# Validation and release checklist

This is a development installer, not a verified production release. No destructive installation has been performed on the developer's computer.

## Automated checks

Run `python -m unittest discover -p '*tests.py'`. Most tests use fake disk metadata and mocked commands. One optional regression test uses filesystem tools on a temporary regular file to convert an old SquashFS image to FAT32; it never uses a block device, mounts anything, or needs root. They cover validation, drive-name handling, mounted/live media exclusion, swap and LVM exclusion, disk identity changes, non-live refusal, version mismatch before partitioning, password stdin/log handling, BIOS and UEFI command flows, failure cleanup, and no success after failed unmount.

Run `python gui_test.py` under a graphical display or Xvfb for a preview-only wizard flow. Python compilation and Bash syntax checks cover the shipped entrypoints. These checks do not prove that Arch package downloads, GRUB boot, upstream builds, firmware or hardware work.

## Results for this development version

- 57 backend, boot, hardware, desktop and repair regression tests: passed, including a real temporary-file SquashFS-to-FAT32 conversion.
- Full preview wizard flow: passed in an isolated Xvfb display with Tk.
- Wi-Fi dialog scan/result rendering: passed with mocked network results; no real connection was attempted.
- All wizard pages fit at 1024×768 by geometry checks.
- Python compilation and Bash syntax checks: passed.
- Existing post-install script: byte-for-byte unchanged.
- The user successfully built and booted the custom ISO in VMware. Their first installation reached partition formatting, then failed because the EFI mount attempted SquashFS instead of FAT32. The filesystem preparation/mount fix has regression coverage, the user subsequently reported installation completion but network/PXE boot after restart. The new named-entry/fallback-loader repair has automated coverage; the user subsequently confirmed the installation boots successfully. This desktop update has not yet received an end-to-end installed-session test.

## Required before a production release

- [x] User reported successfully building the custom ISO.
- [ ] Boot custom ISO and confirm automatic GUI start, keyboard input and networking.
- [ ] Launch from the official stock ISO after connecting with iwctl.
- [ ] Complete an Aero installation onto a disposable UEFI virtual disk.
- [ ] Detach the ISO, boot GRUB and log in as the created user.
- [ ] Confirm first-login layout, effects, sound, networking and welcome screen.
- [ ] Repeat on a disposable legacy BIOS virtual disk.
- [ ] Test no-network and interrupted-download behavior.
- [ ] Test non-US keyboard password entry at Setup, SDDM and sudo.
- [ ] Test 1024×768 display and scaled/high-DPI screens.
- [ ] Confirm mounted USB, swap, LVM/RAID and read-only disks cannot be selected.
- [ ] Test failure during Aero build; confirm failure message, log preservation and unmount.
- [ ] Verify no password appears in logs or process arguments.
- [ ] Test representative Intel/AMD graphics and document NVIDIA requirements.

Use at least 8 GiB RAM and a new 64 GiB virtual disk for the initial build test. Never pass physical disks into the test VM. A successful standard Plasma installation does not validate the optional Aero build. Record ISO date, repository versions, firmware mode, virtual hardware and Aero source revisions with test results; upstream dependencies are not pinned.

## EFI mount regression

Setup now clears signatures on newly created target partitions, directly probes their new filesystem types, refreshes udev metadata, and explicitly mounts root as ext4 and EFI as vfat. Tests reject an unexpected SquashFS probe result and verify the explicit mount arguments. The supplied VM log establishes the wrong filesystem attempt; it does not establish whether old on-disk signatures or stale detection metadata caused it.

## Boot and hardware regressions

Coverage includes exact GPT partition type/layout checks, NVMe EFI registration on the correct parent disk, EFI partition identity, existing-entry reuse, BIOS whole-disk GRUB, image generation before menu generation, missing-image/EFI/fstab/mount/firmware-entry failures, installed-kernel storage module selection, and CPU/GPU/VM package plans. Repair tests verify inspection has no target writes, the apply path contains no format/partition commands, and cleanup runs after failure. Commands and boot binaries are simulated; they do not establish that a generated EFI binary boots.

VM acceptance: boot the updated ISO in UEFI, install to disposable NVMe storage, power off, detach ISO, confirm Winux entry persists and reaches login. Repeat with SATA and BIOS. Test repair against an old installed image without changing its partition UUIDs or user data.

## Desktop and setup changes

57 automated tests pass, including X11 default selection, existing autologin/theme preservation, rejection of missing X11 sessions, TMOG checksum/cache handling, exact wallpaper copying, localized Recycle Bin path, one-time per-user Wine setup and retry on failure. The preview flow tests both No and Yes at the formatting prompt, never invoking the real engine. All six pre-install pages fit at 1024×768. The wallpaper preview was visually inspected. TMOG 0.1.4 was downloaded and matched the publisher’s SHA-256; it was not executed on the development host.

Still required in the test VM: restart into the new default X11 session, confirm the wallpaper survives Aero setup, open the Recycle Bin, Firefox and native TMOG, and launch a representative supported Windows application through Wine. App/menu integration and first-login commands are mocked in the automated tests; no live user configuration was modified here.

## Automatic ISO builder

`python build_iso_tests.py`: three tests pass (help, argument validation, and a simulated complete build using fake Archiso tools). The simulated build verifies bundled desktop assets, checksum output and preservation of an existing same-name ISO. Shell syntax validation passes. The revised builder has not been used for a full ISO build in this development environment.

## TMOG via yay fix

The direct AppImage fetch has been removed from preflight and both installation paths. Setup bootstraps yay through yay-bin, installs tmog-bin as the desktop user, verifies the native executable, and removes temporary package-install permissions even if the AUR command fails. 61 tests pass, including yay reuse and failure cleanup. The current tmog-bin source archive was fetched and matched the checksum in its AUR PKGBUILD. A real yay installation and TMOG launch have not been run on the development host.
