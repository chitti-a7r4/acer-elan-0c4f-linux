# Development and verification record

## Hardware and initial failure

The Acer Aspire A715-76G reported USB 04f3:0c4f, firmware 0165 and an 80 × 80 sensor. Ubuntu 26.04.1 had fprintd 1.94.5-4, libfprint 1:1.95.1+tod1-0ubuntu2, and libpam-fprintd installed. The stock reader registered in swipe mode. Logs included short swipes while idle, protocol errors, unexpected finger-state transitions and failed minutiae detection. Six-stage enrollment sometimes succeeded, but fresh verification repeatedly returned no match. Fingerprint Studio initially misinterpreted a valid saved-finger listing; the parser was corrected and checked against the actual output.

A pre-existing local udev rule named 99-elan-fingerprint-power.rules forced this device’s power/control to on. We renamed that override with a .disabled suffix, reloaded udev and set the reader’s runtime power policy to auto. It subsequently reported suspended while idle. The protocol errors could still occur after this change. No sensor temperature measurement established overheating as the cause. On a different machine, check for an existing override before changing power settings.

## Experimental touch matcher

The elan-touch project captured steady touches on this firmware. In an isolated run, all eight idle checks were clear. An initial memory-only calibration trial timed out near the end; the progress counter was corrected to count accepted touches. A later 24-touch calibration passed. The experimental matcher accepted 5/5 genuine touches and 3/5 during an other-finger group. A persistent trial then saved sensor correction maps separately from 15 enrollment views labeled right index. Its test path compared against the saved template without adding new samples.

One wrong right-middle touch scored about 6.09 against the default 6.0 cutoff. A pinky scored about 8.3, and the operator reported another wrong-finger score around 9.6. Genuine index scores included 8.18. The distributions overlapped. Candidate cutoffs around 7.13 and 9.24 could not resolve all observed errors. These are local observations from a small test, not a population accuracy estimate. The community matcher was kept out of the login service.

## Windows engine investigation

The official model-specific Acer package contains WbfUsbDriver.inf, WbfUsbDriver.dll, EngineAdapter.dll and ELANFPService.exe. The INF explicitly maps VID_04F3 and PID_0C4F and registers ELAN’s engine with the Windows Biometric Framework. An isolated Wine probe loaded the DLL, queried WinBio interface 3.0 and ANSI 381 format, and opened an empty enrollment session with a sample hint of seven. It handled the sensor geometry query and the engine-information exchange. A blank 80 × 80 record and a live touch in the tested record layout both returned WINBIO_E_BAD_CAPTURE (0x80098008). Diagnostic strings indicated additional vendor frame metadata; the required record was not established.

## Working OEM engine and native driver

The upstream elan_oem fork already integrated an older ELAN engine for a 96 × 96 reader. Its pinned DLL could process the smaller image geometry. The prototype reused 15 right-index views and added three fresh touches to produce a separate OEM template. The enrollment engine accepted a blank as an intermediate enrollment input, but verification rejected the blank control. A reported 3/5 right-index result in the early GUI test used two incorrectly labeled touches during verification. That group was excluded from the index-accuracy result. The enrollment itself used the right index.

The native port changes the reader ID and frame geometry, interprets zero-based dimensions, issues the reader activation command, gives calibration more time, and handles firmware statuses encountered during real scans. Status 0xff starts bounded recalibration. Status 0xaf waits for another status. Only 0x55 triggers reading a fingerprint image. The OEM driver treats the sensor as a press reader. The Linux GUI queries enrollment stages from D-Bus and adjusts its instructions for touch.

| Native test with a fresh set of touches | Result |
| --- | --- |
| Right index, enrolled | 4/5 matched |
| Right pinky, unenrolled | 0/5 matched |
| Right middle, unenrolled | 0/5 matched |
| libfprint device, state-machine and assembling unit suites | All three passed |
| Actual Niri / DankMaterialShell unlock | Desktop locked, fprintd emitted verify-match, desktop unlocked |
| Persistence | fprintd exited; D-Bus activated a new invocation; the same right-index enrollment was listed |
| Idle power after unlock | Runtime control auto, state suspended |

The installed service uses a root-owned private library directory and a systemd drop-in. MemoryDenyWriteExecute remained enabled. Ubuntu’s packaged library, password stack and prior driver-specific enrollments were preserved. Only the right index was enrolled via fprintd for the new driver. Subsequent everyday use was reported as reliable by the laptop owner. First login after a full reboot and broad false-accept rates remain unmeasured.
