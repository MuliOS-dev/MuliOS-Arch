# MUpdate: direct repository merge

MUpdate synchronizes MuliOS-owned files from the MuliOS-dev/MuliOS-Arch repository into an installed MuliOS Arch system. It does not download an ISO, unpack an ISO, or use a recovery environment.

## Commands

```bash
sudo mupdate update
sudo mupdate update --dry-run
sudo mupdate update --safe
sudo mupdate status
```

- `update` compares the repository tree and merges new or changed files.
- `--dry-run` downloads candidate files for validation and reports changes without writing them.
- `--safe` lists changes without applying them.
- `status` displays the last synchronized repository tree and version.

## Source mapping

Each file under `profile/airootfs/` maps to the same path under the installed root:

- `profile/airootfs/usr/share/backgrounds/mulios/wallpaper.png` maps to `/usr/share/backgrounds/mulios/wallpaper.png`.
- `profile/airootfs/usr/local/bin/mupdate` maps to `/usr/local/bin/mupdate`.
- `profile/airootfs/etc/skel/.config/kdeglobals` maps to `/etc/skel/.config/kdeglobals`.

MUpdate compares local file content using Git blob hashes. Downloads are checked against the blob hash returned by GitHub before installation. The updater's own file is deferred until the other files have been processed.

## Safety rules

MUpdate never removes repository-untracked files. It excludes live-ISO-only content such as:

- SDDM live-user autologin.
- The live installer sudoers override and desktop shortcut.
- Live systemd unit files and enablement symlinks.
- ArchISO-specific initramfs configuration.
- Live mirror and cleanup hooks.
- The live installer and first-run welcome app.

It protects machine-specific account databases, hostname, hosts file, machine ID, timezone link, filesystem tables, SSH host configuration, `/var`, `/home`, `/root`, `/boot`, and `/efi`.

New files are non-executable by default. Existing permissions are preserved, and known executable directories receive executable permissions for new files.

The ROUNDED KDE theme is built from the pinned commit in `scripts/install-rounded-theme.sh`. MUpdate reads that pin and installs the theme assets directly when the installed theme is missing or out of date.

## Important limitations

This synchronizer is a file overlay, not a package manager. It does not install packages merely because a package was added to `profile/packages.x86_64`, because that list contains live-ISO and installer dependencies as well as desktop packages. Kernel/package upgrades must be handled by an explicit installed-system package workflow.

Files are not deleted automatically. If a file is removed from the repository, MUpdate leaves the installed copy in place. This avoids accidentally deleting user or locally managed data.

MUpdate requires network access to GitHub and administrator privileges. Review repository changes before using it on a production system.