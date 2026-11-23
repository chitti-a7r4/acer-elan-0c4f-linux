# Acer ELAN fingerprint reader on Linux

A touch-to-unlock driver port for the **Acer Aspire A715-76G** with USB reader **04f3:0c4f**, firmware **0165**, and an **80 × 80 pixel** sensor. Tested on x86-64 Ubuntu 26.04.1 LTS with fprintd, Niri and the DankMaterialShell lock screen. A real desktop unlock produced a fprintd verification match. The enrolled finger was also available after the service exited and D-Bus started a fresh process.

The USB capture path comes from libfprint. An ELAN Windows matching engine runs locally through the upstream fork’s x86-64 loader. The active installation uses **ELAN engine 1.1.0.2111**. Acer’s model-specific **3.6.11001.10802** package was a separate experiment. [Upstream libfprint fork](https://github.com/skrimix/libfprint_elan) · [Acer model support](https://www.acer.com/us-en/support/product-support/A715-76G)

## Install on another laptop

Check the USB ID first. This build gives fprintd the single ported driver. Other reader models require a different build.

```sh
lsusb -d 04f3:0c4f
uname -m
sudo apt install build-essential git meson ninja-build pkg-config libglib2.0-dev libgusb-dev libcairo2-dev fprintd libpam-fprintd curl cabextract usbutils
./tools/build
./tools/fetch-engine
```

Run these commands from the repository root. The build script fetches a pinned libfprint revision, applies the port, builds it and runs its unit tests. The download script checks the engine DLL against the digest the driver expects. Both put generated files in the ignored `.work/` directory. The driver sources and compiler are only needed during the build.

Install the files in a root-owned directory and configure fprintd to use them. On a machine that already has a different custom fprintd drop-in, review `systemctl cat fprintd` first. Replacing a live library uses a rename so running processes can finish using their current copy.

```sh
sudo install -d -m 0755 /usr/local/lib/acer-elan-0c4f /etc/systemd/system/fprintd.service.d
sudo install -m 0644 .work/build/libfprint/libfprint-2.so.2.0.0 /usr/local/lib/acer-elan-0c4f/libfprint-2.so.2.new
sudo install -m 0644 .work/EngineAdapter.dll /usr/local/lib/acer-elan-0c4f/EngineAdapter.dll.new
sudo mv /usr/local/lib/acer-elan-0c4f/libfprint-2.so.2.new /usr/local/lib/acer-elan-0c4f/libfprint-2.so.2
sudo mv /usr/local/lib/acer-elan-0c4f/EngineAdapter.dll.new /usr/local/lib/acer-elan-0c4f/EngineAdapter.dll
sudo install -m 0644 systemd/60-acer-oem.conf /etc/systemd/system/fprintd.service.d/60-acer-oem.conf
sudo systemctl daemon-reload
sudo systemctl restart fprintd
fprintd-list "$(id -un)"
```

Look for **ELAN Fingerprint Sensor (OEM matcher)**. A fresh user profile starts empty. Enroll once as the user who will unlock the desktop. If the reader already lists your right index, go directly to verification.

```sh
fprintd-enroll -f right-index-finger
fprintd-verify -f right-index-finger
```

Start each operation with the sensor clear. Rest your right index on the reader, hold briefly, and lift fully. Vary the placement slightly during enrollment. To check rejection, run the same verification command and touch with another finger. The desktop locker must support fingerprint authentication. In DankMaterialShell, enable fingerprint unlock in Lock Screen settings. On the tested system, opening that settings panel refreshed detection after enrollment.

**Optional GUI.** Install `python3-tk` and run `python3 gui/fingerprint_studio.py` for a hand diagram, saved fingers, enrollment progress and a test button. The production unlock path runs through fprintd even when the GUI is closed.

## Reboot and recovery

Ubuntu stores the system enrollment under the root-owned `/var/lib/fprint` state directory. The service drop-in in `/etc` and matching library in `/usr/local/lib` persist on disk. D-Bus starts fprintd on demand. An idle, inactive fprintd service is normal. After reboot, check with:

```sh
fprintd-list "$(id -un)"
fprintd-verify -f right-index-finger
```

A disk-encryption prompt, first desktop login, or login-keyring prompt can still need your password. Once signed in, fingerprint unlock can use the existing enrollment. The tested machine passed a fresh service activation and desktop unlock. A full cold-boot login was not tested during this project.

**Rollback.** Disable just the project’s drop-in. Ubuntu then loads its distribution driver. Driver-specific templates stay on disk.

```sh
sudo mv /etc/systemd/system/fprintd.service.d/60-acer-oem.conf /etc/systemd/system/fprintd.service.d/60-acer-oem.conf.disabled
sudo systemctl daemon-reload
sudo systemctl restart fprintd
```

To reactivate, reverse the rename and repeat the last two commands. If a future Ubuntu update changes fprintd compatibility, use the rollback while rebuilding and retesting.

## Project files

| Location | Purpose |
| --- | --- |
| `patches/elan-0c4f.patch` | Native sensor port, applied to the pinned libfprint fork |
| `tools/`, `systemd/` | Reproducible build, vendor download, and installed service settings |
| `gui/` | Fingerprint Studio for the active fprintd reader |
| `experiments/` | Research and verification programs from the investigation |
| [Development record](docs/development.md) | Driver identification, failed approaches, tests and limitations |
| [Source and licensing notes](docs/sources.md) | Exact dependencies, provenance and binary hashes |
