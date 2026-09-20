# MuliOS Arch Installer

A GUI frontend for **Archinstall** - this installer collects choices
through a 16-step wizard, generates the two JSON files Archinstall's
unattended mode expects, and calls the real `archinstall` executable.
It never reimplements Arch installation logic. After Archinstall
finishes, it bridges into your existing `mupdate` tool (unchanged,
called exactly as `sudo mupdate <profile> -y`) to apply the chosen
MuliOS profile.

## Directory structure

```
installer/
├── main.py                     <- entry point, wizard shell + navigation
├── theme.py                    <- dark-gray theme, #319cc8 / #1748a0 accents
├── config/
│   └── settings.py              <- paths, profile list, DE/bootloader/filesystem options
├── branding/
│   └── logo.png                 <- YOU NEED TO ADD THIS (see below)
├── assets/                      <- (reserved for future icons/screenshots)
├── widgets/
│   ├── toggle_switch.py          <- animated iOS-style switch
│   ├── select_card.py            <- checkable card (profiles + DE picker)
│   └── searchable_picker.py      <- filter box + list (locale/keyboard/timezone)
├── backend/
│   ├── system_info.py            <- read-only: lsblk, localectl, timedatectl, nmcli
│   ├── archinstall_config.py     <- builds user_configuration.json / user_credentials.json
│   ├── archinstall_worker.py     <- QThread: runs archinstall, then mupdate
│   └── mupdate_bridge.py         <- calls mupdate inside the new system via arch-chroot
├── utils/
│   └── validators.py              <- hostname/username/password validation
└── pages/                         <- one file per wizard step (16 total)
```

## Wizard flow

```
Welcome -> Language -> Keyboard -> Timezone -> Network -> Disk -> Partitioning
-> Bootloader -> Account -> Desktop -> Packages -> Profile -> Advanced
-> Summary -> Install -> Finished
```

## Running it

```bash
pip install PySide6
python3 main.py
```

Safe to run anywhere for UI testing - nothing touches a disk until you
confirm on the Summary page. The real install needs root and should
only be run inside a MuliOS Arch live session (VM or real live USB):

```bash
sudo python3 main.py
```

## Add your logo

Drop your logo at `branding/logo.png`. It's picked up automatically in
four places: the sidebar, the Welcome page, the Finished page, and the
window/taskbar icon. If it's missing, all four gracefully fall back to
showing "MuliOS" as text instead of breaking.

## READ THIS: Archinstall config schema

Corrected against the actual, current `examples/config-sample.json`
fetched live from `archlinux/archinstall`'s master branch (matching
ArchInstall 4.4, shipped on the Arch Linux 2026.07.01 ISO) - not
guessed. Every key/nesting - `bootloader_config`, `profile_config`,
`swap` as a dict, `pacman_config`, `mirror_config.optional_repositories`
for multilib - comes directly from that real file. `build_config()`
was also test-run against realistic fake wizard state to confirm it
produces valid, well-formed JSON matching that structure.

**Two areas are still genuinely unverified** (flagged with loud
comments in `archinstall_config.py` itself, not hidden):
- `disk_encryption`'s exact shape - the reference file doesn't use LUKS,
  so this is best-effort based on prior Archinstall behavior
- `network_config`'s non-"manual" type values (`"nm"` /
  `"copy_iso_config"`) - the reference file only demonstrates `"manual"`
  with an explicit NIC list

Before a real build, generate a known-good reference yourself: boot the
ISO, run `archinstall`, walk the guided menu once, choose "Save
configuration", and diff that file against what `build_config()`
produces - especially for those two areas.

**Mirror URLs are now real, not placeholders.** Picking a mirror region
other than "Worldwide" triggers a live fetch from archlinux.org's own
mirrorlist endpoint (`fetch_mirror_urls()` in `archinstall_config.py`),
done by the install worker right before writing the config (since it
needs network access and shouldn't run every time the Summary page's
"show config" preview button is clicked). "Worldwide" or a failed fetch
both just omit `mirror_config.mirror_regions` entirely, which leaves
Archinstall using the live ISO's own already-configured mirrorlist -
a safe fallback, since an *empty* URL list would leave the installed
system with no mirrors at all.

## mupdate integration

**⚠️ Outdated - see "Update utility" section below.** This section
describes the CLI the code currently *calls*, kept here unmodified so
you can see exactly what changed:
```
arch-chroot /mnt mupdate install -y
arch-chroot /mnt mupdate <profile> -y
```
Now that the real `mupdate a1.0.4` binary is bundled in this repo, an
audit shows this CLI does not actually exist in a1.0.4. Do not treat
this section as accurate until `mupdate_bridge.py` is updated to match
the real interface.

`archinstall_worker.py` runs these after Archinstall succeeds. If
there's no internet connection (checked on the Network page), both
calls are skipped and the Finished/log output tells the user to run
them manually after first boot instead.

**Assumption worth checking:** this assumes `mupdate` is already
present inside the freshly-installed system (e.g. shipped via your
`profile/packages.x86_64`, same as Archinstall itself). If it isn't
installed by that point, add it there or as one of the "Additional
packages" the installer passes to Archinstall.

If a profile pack fails to install via mupdate, the installer treats
that as a **warning, not a failure** - the base OS is still installed
and bootable at that point, so the Finished page shows success with a
note about the profile, rather than a scary total-failure screen.

## Logging

Everything the install worker logs is streamed to the UI and also
written to `/var/log/mulios/install.log` (created with parent dirs on
first run). The Finished page's "View logs" button opens this file.

## Update utility

The old bundled `update` (a1.0.0) script has been **removed** from this
project. It is no longer shipped, referenced, or called anywhere.

The real `mupdate` (a1.0.4) executable is now bundled directly in the
repo root (`./mupdate`, installs to `/usr/bin/mupdate`) instead of being
assumed to exist. It is the single OTA/update tool for MuliOS - there
is no second updater.

**Important - CLI mismatch found during this audit:** the real
`mupdate a1.0.4` script's actual command surface is only:
```
mupdate --version | -v
mupdate --help    | -h
mupdate ota <stable|beta>
```
There is **no** `mupdate install -y` and **no** `mupdate <profile> -y`
subcommand in a1.0.4. Profile is not an argument you pass to it at all -
`detect_active_profile()` inside the script derives the profile from
the *running kernel's* release string (`<version>-mulios-<profile>`),
and `ota <channel>` does a full ISO-based OTA reinstall of an
**already-installed and already-booted** MuliOS system - it does not
operate on a chroot at `/mnt` during first install.

This means `installer/backend/mupdate_bridge.py` (`run_mupdate_base_install`
calling `mupdate install -y`, `run_mupdate_profile` calling
`mupdate <profile> -y`) calls a CLI that **does not exist** in the real
a1.0.4 binary now bundled here. Those calls will fail with "Unknown
option" against the real script. This is flagged, not silently fixed,
because resolving it requires a real decision about how profile
selection is meant to work during initial installation (e.g. baking the
profile into the installed kernel/package selection so mupdate can
detect it after first boot, vs. some other real a1.0.4-compatible
mechanism) - see the audit notes in `mupdate_bridge.py`.

## What I could not verify here

I don't have internet access in my working environment, so I couldn't
`pip install PySide6` and actually watch this render - I verified every
file compiles cleanly (`python3 -m py_compile`) and the architecture
follows normal, well-tested Qt patterns, but haven't seen it on screen.
Please run it and tell me what you actually see, especially:
- Whether the 16-step sidebar reads clearly at this length
- Whether the generated Archinstall config actually works against your
  ISO's bundled Archinstall version (see the schema section above)
- Whether `mupdate` is reachable via `arch-chroot /mnt mupdate ...`
  immediately after Archinstall finishes, before any reboot
