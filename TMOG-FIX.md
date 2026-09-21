# TMOG installation folder fix

The installer previously installed yay successfully, then stopped with:

```text
error fetching tmog-bin: fatal: cannot change to '.../packages': No such file or directory
```

The installer supplied a custom yay build directory without creating it. It now creates that directory with private permissions and assigns it to the desktop user before running yay. TMOG is still installed using `yay -S tmog-bin` as the regular user. Temporary build files and the temporary sudo rule are removed on success or failure.

## Get the fix

Update your project checkout and rebuild the ISO:

```bash
git pull --ff-only
bash build-iso.sh
```

Boot the newly built ISO for the next installation attempt. An older ISO contains the old installer even after the project checkout is updated. Setup erases the selected installation disk again; it does not resume an interrupted installation.

If launching Setup from a project checkout inside the live ISO, update that checkout and relaunch `bash launch.sh` instead. Do not update files while Setup is running.

## Verification

The regression test reproduces the missing-directory error with the previous implementation. With the fix it verifies the directory exists, has mode 0700, is included in the ownership change before yay starts, and supports an actual local `git -C ... init`. Both a fresh yay bootstrap and reuse of an existing yay installation are covered. Existing tests cover cleanup after AUR failure. Package installation and a complete VM installation were not performed for this fix.
