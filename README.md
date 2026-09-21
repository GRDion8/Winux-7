# Winux 7

**A Windows 7–inspired graphical installer for Arch Linux, with an Aero desktop.**

Boot a current Arch ISO, launch Setup, and work through a familiar wizard: preferences → connection → drive → account → review → installation. A custom ISO builder is included for booting directly into Setup.

> **Development preview — not a production-tested distribution.** The engine performs real whole-disk installation, but an end-to-end VM installation and boot test must be completed before using it on valuable hardware. Start with a disposable virtual disk. All data on the selected drive is erased.

## Start here

- **[Repair a disk that will not boot](BOOT-REPAIR.md)** — preserve your existing installation.
- **[Desktop update guide](DESKTOP.md)** — update an existing installation without reinstalling.
- **[Complete installation tutorial](TUTORIAL.md)** — preview, stock ISO, custom ISO, first login, and recovery.
- **[Existing post-install guide](POSTINSTALL.md)** — for an already installed Arch system.
- **[Validation and VM test checklist](TESTING.md)** — what was tested and what remains.

### Safe desktop preview

Install Python, Tk, and Pillow using your distribution's package manager, then:

```bash
python setup.py --demo
```

The default `python setup.py` is also a preview. It uses fictional drives and simulated progress, never the installation engine.

### From a booted Arch ISO

Connect to the internet, then run these commands **in the live ISO**, not your installed system:

```bash
pacman -Sy --needed git
git clone https://github.com/GRDion8/Winux-7.git
cd Winux-7
bash launch.sh
```

Setup installs its graphical dependencies into the temporary live environment. This requires enough free live-overlay space. See the tutorial for Wi-Fi and custom ISO instructions.

## Build the ISO

From this project folder on an installed x86_64 Arch Linux system:

```bash
bash build-iso.sh
```

The script requests sudo, installs missing Archiso tools after the package manager’s confirmation, and builds the image automatically. Allow at least 30 GiB free in `/var/tmp`. The ISO and SHA-256 checksum are saved in `iso-output/`; their paths are printed when finished. Do not run the builder inside the live ISO.

## What you get

- Native local graphical wizard with a blue Aero-style background and familiar setup sequence.
- Whole-disk GPT partitioning for UEFI or legacy BIOS.
- Arch Linux, Linux kernel, firmware, GRUB, KDE Plasma X11, audio and desktop applications.
- Optional AeroThemePlasma source build using the original post-install wrapper inside the installed system's chroot.
- Full glibc locale catalog, keyboard layout, time zone, hostname, and administrator account.
- Winux 7 X11 login, the supplied profile picture and wallpaper, Recycle Bin, Firefox, Wine/Mono/Gecko/Winetricks, and native TMOG Task Manager (including the taskbar action).
- NetworkManager, time synchronization, compressed RAM swap, and a first-login welcome.
- Explicit disk review, Yes/No erase confirmation naming the selected disk, blocked busy/live disks, preflight package checks, password input through stdin, and protected logs.
- A custom Archiso image builder. No prebuilt ISO is supplied.

## Scope

This is an independently branded Linux setup experience, not Microsoft Windows or an exact reproduction of its installer. It includes Wine for compatible Windows applications, but does not install Windows itself, Windows drivers, product activation, or Microsoft fonts. The setup UI is English; selected regional settings apply to the installed desktop.

The initial installer supports **x86_64, one entire disk of at least 48 GiB, UEFI or BIOS, and an online installation**. It does not support partition preservation, dual boot, encryption, RAID/LVM targets, Secure Boot signing, hibernation, or offline installs. NVIDIA proprietary driver selection is not automated; test your GPU with the standard open drivers before relying on this release.

Aero targets Plasma **6.7.x**. Setup checks repository metadata before erasing; it stops on a mismatch instead of forcing incompatible components. Arch repositories and upstream sources are mutable, so a successful preflight cannot guarantee a later build. The standard Plasma option bypasses the Aero version restriction and installs without the Aero look.

UEFI installs now register an active **Winux 7** firmware boot entry for the selected disk and also install the standard fallback EFI loader. Setup verifies the GPT layout, mounted partitions, kernel, normal/fallback startup images, GRUB menu and root UUID before reporting success. UEFI requires writable firmware variables.

Hardware detection selects Intel or AMD CPU microcode, Intel/AMD/Nouveau graphics packages, applicable audio firmware, and VMware/VirtualBox/QEMU guest tools. Storage-controller modules are checked against the installed kernel and included in its startup images. Linux handles network/storage driver loading; `linux-firmware` supplies the baseline firmware. NVIDIA uses conservative Nouveau initially, not an unverified proprietary-driver choice. The package plan is saved to `/var/log/winux-hardware.json`. Run `python hardware.py` for a read-only report.

## Source map

| File | Purpose |
| --- | --- |
| `desktop.py`, `desktop-first-login.py`, `update-desktop.py` | X11 defaults, apps and existing-system update |
| `locales.py` | Complete supported-locale catalog |
| `wallpaper.jpg` | User-supplied installer/desktop wallpaper |
| `setup.py` | Graphical wizard and harmless preview |
| `bootloader.py`, `repair-boot.py` | Shared boot verification and repair without repartitioning |
| `hardware.py` | Read-only hardware detection and package selection |
| `boot_tests.py`, `repair_tests.py` | Boot, hardware, and repair regression tests |
| `engine.py` | Validation, discovery, preflight, partitioning, chroot setup, cleanup |
| `launch.sh`, `xsession.sh` | Start the graphical installer from Archiso |
| `build-iso.sh` | Build a custom releng-based ISO with graphical startup |
| `arch-win7-aero-postinstall.sh` | Existing Aero desktop installer, preserved unchanged |
| `network.py` | Wi-Fi selection and connection dialog for the custom ISO |
| `welcome.py` | First-login welcome and installed guide link |
| `tests.py` | Fake-device, non-destructive backend tests |
| `gui_test.py` | Display-based, preview-only wizard smoke test |
| `TUTORIAL.md`, `POSTINSTALL.md`, `TESTING.md` | User and developer guides |

## Development

```bash
python -m unittest discover -p '*tests.py'
python -m py_compile engine.py setup.py welcome.py
bash -n launch.sh xsession.sh build-iso.sh arch-win7-aero-postinstall.sh
# Requires a graphical display (or Xvfb):
python gui_test.py
```

Do not run actual disk installation tests on a development machine. Use a VM with a new disposable virtual disk and no physical-disk passthrough. See `TESTING.md` for the required boot tests.

## Credits and license

The software retains its [GPL-3.0 license](LICENSE). The user-supplied `wallpaper.jpg` and `user.bmp` are third-party artwork and are not licensed under that GPL grant. AeroThemePlasma and its components retain their own licenses and credits. Windows is a Microsoft trademark; this community project is not affiliated with Microsoft or the Arch Linux project.

Implementation references: [pacstrap](https://man.archlinux.org/man/pacstrap.8.en), [arch-chroot](https://man.archlinux.org/man/arch-chroot.8.en), [sfdisk](https://man.archlinux.org/man/sfdisk.8.en), [grub-install](https://man.archlinux.org/man/grub-install.8.en), [mkarchiso](https://man.archlinux.org/man/mkarchiso.1.en), [Archiso releng profile](https://github.com/archlinux/archiso/tree/master/configs/releng), and [AeroThemePlasma installation instructions](https://github.com/aeroshell-desktop/aerothemeplasma/blob/Plasma/6.7/INSTALL.md).
