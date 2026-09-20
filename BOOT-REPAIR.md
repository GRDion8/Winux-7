# Repair a Winux disk that falls through to network/PXE boot

You can repair the existing installation without reinstalling or rebuilding the ISO. The repair command never creates, deletes, or formats partitions. It rewrites boot files and updates the UEFI boot entry only when you pass `--apply`.

## 1. Boot the live ISO again

Keep the installed virtual disk attached. Boot the ISO in the **same firmware mode used for installation**. The previously supplied VMware installation log used UEFI and an NVMe disk. For that installation, keep VMware set to UEFI; switching to legacy BIOS will not repair a UEFI installation. Secure Boot must be off because this project does not supply signed loaders.

Close the installer. Open a terminal, or switch to another console with Ctrl+Alt+F2 (VMware may require its Send Key menu). Run the following as root in the live environment:

```bash
cd /root
git clone https://github.com/GRDion8/Winux-7.git Winux-7-bootfix
cd Winux-7-bootfix
lsblk -o NAME,SIZE,MODEL,FSTYPE,MOUNTPOINTS
```

If this clone directory already exists, enter it and run `git pull --ff-only` instead of cloning again. The custom Winux ISO already includes Python and Git. On an official Arch ISO, install missing prerequisites with `pacman -Sy --needed python git`.

## 2. Inspect the installed disk

Identify the installed whole disk by size and model. The earlier VMware log used `/dev/nvme0n1`; **verify this on your machine** and replace it below if needed. Do not select the ISO or a partition such as `nvme0n1p1`.

```bash
python repair-boot.py --disk /dev/nvme0n1
```

Without `--apply`, this checks the partition layout and filesystem types without mounting or modifying the target. It writes a diagnostic log in the live environment. It supports the installer's two-partition GPT layout: UEFI system partition plus ext4 root, or BIOS boot partition plus ext4 root. A firmware/layout mismatch, busy disk or different layout stops the repair; it never repartitions to make them fit.

## 3. Apply the repair

If the inspection identifies the expected disk and layout:

```bash
python repair-boot.py --disk /dev/nvme0n1 --apply
```

The repair mounts the existing installation, checks its Winux configuration, backs up the original Linux startup-image preset once, and regenerates both normal and fallback startup images. Detected storage modules are checked against the **installed kernel**, not the live ISO kernel. It installs a named `Winux` EFI loader and the standard fallback loader, creates or reuses an active firmware entry for that exact EFI partition, checks BootOrder, and regenerates/verifies the GRUB menu. BIOS installs instead receive GRUB on the selected whole disk. Existing accounts and desktop packages are retained; this repair does not install new hardware packages.

Wait for **Boot repair completed and files verified**, then:

```bash
poweroff
```

Disconnect the ISO in VMware, keep the installed virtual disk connected, and start the VM. Select **Winux** in the firmware boot menu if needed; place it ahead of network boot. New hardware-aware package selection applies to future installations made using the updated installer.

## If it still fails

Do not repeat installation or erase the disk just to gather evidence. Save `/var/log/winux-boot-repair.log` before shutting down the live ISO. Report the exact screen and firmware mode. If the firmware cannot see the virtual disk at all, check VMware's disk connection and controller settings; software boot repair cannot fix a disconnected disk.

- Network/PXE again: check whether the firmware lists Winux and whether the virtual disk is connected. Firmware must retain its NVRAM across boots.
- GRUB appears, then the root disk is missing: try the fallback entry under Advanced options and save the exact error.
- Desktop black screen after GRUB: that is a later graphics/display issue; provide that screen separately.
- Repair stops: preserve its log; do not bypass its layout checks or format anything.

A successful file/entry check is not a substitute for an actual reboot test. This update has automated command-flow and failure tests; successful VMware reboot remains to be confirmed.
