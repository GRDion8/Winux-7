# Validation and release checklist

This is a development installer, not a verified production release. No destructive installation has been performed on the developer's computer.

## Automated checks

Run `python tests.py`. Tests use fake disk metadata and mocked commands; they never call the actual partitioning or installation tools. They cover validation, drive-name handling, mounted/live media exclusion, swap and LVM exclusion, disk identity changes, non-live refusal, version mismatch before partitioning, password stdin/log handling, BIOS and UEFI command flows, failure cleanup, and no success after failed unmount.

Run `python gui_test.py` under a graphical display or Xvfb for a preview-only wizard flow. Python compilation and Bash syntax checks cover the shipped entrypoints. These checks do not prove that Arch package downloads, GRUB boot, upstream builds, firmware or hardware work.

## Results for this development version

- 25 backend tests: passed using fake disks and mocked subprocesses.
- Full preview wizard flow: passed in an isolated Xvfb display with Tk.
- Wi-Fi dialog scan/result rendering: passed with mocked network results; no real connection was attempted.
- All wizard pages fit at 1024×768 by geometry checks.
- Python compilation and Bash syntax checks: passed.
- Existing post-install script: byte-for-byte unchanged.
- Custom ISO build, actual disk installation, reboot, and Aero source build: **not performed**.

## Required before a production release

- [ ] Build the custom ISO with the current Archiso releng profile.
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
