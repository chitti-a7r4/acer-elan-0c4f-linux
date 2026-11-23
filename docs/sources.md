# Sources and binary provenance

| Component | Exact input |
| --- | --- |
| Native libfprint base | [skrimix/libfprint_elan at 3b4a2b1](https://github.com/skrimix/libfprint_elan/tree/3b4a2b16489faeb083c615fb81b793d974d1d6ee) |
| Native loader lineage | [OMGrant/ft9201-libfprint](https://github.com/OMGrant/ft9201-libfprint), credited by the upstream ELAN fork |
| Community touch experiment | [mmhanda/elan-touch at caf1996](https://github.com/mmhanda/elan-touch/tree/caf1996cb80bc84a5f360f26f39615a7ffbb74ac) |
| Working vendor engine | ELAN 1.1.0.2111, SHA-256 `8f9254d10594ff7479741e72d22abec9417807257ac0c7a967ec7eaa8865a9e9`. [Microsoft driver CAB](https://catalog.s.download.windowsupdate.com/c/msdownload/update/driver/drvs/2017/07/2553b5f6-cd54-4cb2-a552-c4ee4d4ebe9a_4394725e4cd2b8d73ab385804e2f9e1e760a4e28.cab) |
| Model-specific Windows probe | Acer archive SHA-256 `3ee0d8221f3f81cc71404320fbe18f91bfabe1bb466999912e9b2a703f1de606`; contained EngineAdapter.dll SHA-256 `50f5cec6910fbcabd65efa0e5d41224a917a34248245617971b5403fa9864eb8`. [Official Acer ZIP](https://global-download.acer.com/GDFiles/Driver/Fingerprint/Fingerprint_ELANTECH_3.6.11001.10802_W11x64_A.zip?BC=ACER&LC=en&OS=ALL&SC=PA_6&Step1=&Step2=&Step3=ASPIRE+A715-76G&acerid=637860342724797685) |
| Windows interface | [Microsoft WinBio engine adapter](https://learn.microsoft.com/en-us/windows/win32/secbiomet/engine-adapter-functions) and [adapter workflow](https://learn.microsoft.com/en-us/windows/win32/secbiomet/adapter-workflow) |
| Original machine’s native shared library | SHA-256 `c9250a3825436e4067dfd59b986f54483cb327e3531da251ed8482723ed39d8e`. Compiler, debug paths and distribution versions can change this hash on a fresh build. |

The patch modifies LGPL-2.1-or-later upstream driver files. The corresponding license text is in licenses/LGPL-2.1.txt. Upstream dependencies retain their own notices. ELAN’s binary is supplied separately by the vendor through Microsoft’s catalog. The repository contains source, a patch and download instructions. No blanket license has been chosen for the project’s original standalone tools.
