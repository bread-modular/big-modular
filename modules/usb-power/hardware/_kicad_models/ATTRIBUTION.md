# Third-party 3D model attribution

Unmodified STEP resources copied byte-exactly from the locally installed KiCad
`kicad-packages3d` library into `hardware/_kicad_models/<provider-path-sha256>/`
so canonical `hardware/usb-power.kicad_pcb` (SHA256 `69a1e329e919ca0f8ddaaec38e30de119fa0d0639823c0017e1675554ff52adc`)
stays byte-exact and portable with its `${KIPRJMOD}` model references.

License facts were read locally from `/usr/share/doc/kicad-packages3d/copyright`
(upstream `https://kicad.github.io/packages3d/`); they are not inferred.

| file | provider path | bytes | SHA256 | license / copyright |
| --- | --- | ---: | --- | --- |
| `D_SMA.step` | `Diode_SMD.3dshapes/D_SMA.step` | 70794 | `1cfddd4e3b1bf22b8fc6ee3258c2aade882ed7b85b528e23b9db42437775a1db` | GPL-3+ (Copyright 2017, kicad StepUp) |
| `LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm.step` | `LED_THT.3dshapes/LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm.step` | 48854 | `8f5355877fb800c2ab9c9edb0c9553c940df7f91bda73c298d6dc0d451bfdd3b` | CC-BY-SA-4.0-with-exception (Copyright 2018-2026, KiCad Community; Debian default rule) |
| `C_0603_1608Metric.step` | `Capacitor_SMD.3dshapes/C_0603_1608Metric.step` | 43450 | `4857b3dc717675bf1fb22edda622ac3b3ae03cf44d81eefaf3fa3ba3a86d84c1` | CC-BY-SA-4.0-with-exception (Copyright 2017-2021, kicad StepUp) |
| `R_0603_1608Metric.step` | `Resistor_SMD.3dshapes/R_0603_1608Metric.step` | 40618 | `1875571c326d0d9e96f36b4efeb8094068ef7619f0a449c781caf0b49c2e5861` | CC-BY-SA-4.0-with-exception (Copyright 2017-2021, kicad StepUp) |
| `Fuse_1206_3216Metric.step` | `Fuse.3dshapes/Fuse_1206_3216Metric.step` | 40429 | `5e6dcbe286696143d35a8ea37d91eef4b54ff3d1bd7c2c2b4dedda83d3f8e203` | CC-BY-SA-4.0-with-exception (Copyright 2017-2021, kicad StepUp) |
| `C_1206_3216Metric.step` | `Capacitor_SMD.3dshapes/C_1206_3216Metric.step` | 43450 | `11e948c72c90e2b6322436b72745f40ff4e8ba0da64fb2a0df943dfa61e89c1a` | CC-BY-SA-4.0-with-exception (Copyright 2017-2021, kicad StepUp) |
| `SOT-23-6.step` | `Package_TO_SOT_SMD.3dshapes/SOT-23-6.step` | 99639 | `c9fe686b4d1b56927a41fa84a9bc1efb61d8a45a123a3db43bcaa05c2891d635` | CC-BY-SA-4.0-with-exception (Copyright 2017-2021, kicad StepUp) |
| `HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.66x2.46mm.step` | `Package_SO.3dshapes/HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.66x2.46mm.step` | 210194 | `f8217a19e2965bc3617c97b8bb851829f4470fb33a5c50462eb6df0f7cc2cd4a` | CC-BY-SA-4.0-with-exception (Copyright 2017-2021, kicad StepUp) |
| `SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm.step` | `Package_SO.3dshapes/SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm.step` | 153600 | `3623be00464827bd6d94a12acf96d5923399b878c328184fa76e1ecbc0a63bc2` | CC-BY-SA-4.0-with-exception (Copyright 2017-2021, kicad StepUp) |
| `C_0805_2012Metric.step` | `Capacitor_SMD.3dshapes/C_0805_2012Metric.step` | 43618 | `9a669c1a2f1ea25b88b401acef6efeaa80a067bd7da9db6993de719a7fbe155c` | CC-BY-SA-4.0-with-exception (Copyright 2017-2021, kicad StepUp) |

## License notice

Most files: **CC-BY-SA-4.0-with-exception** (KiCad libraries). The upstream
exception states: "To the extent that the creation of electronic designs that use
'Licensed Material' can be considered to be 'Adapted Material', then the copyright
holder waives article 3 of the license with respect to these designs and any
generated files which use data provided as part of the 'Licensed Material'."

`D_SMA.step` is listed under `Diode_SMD.3dshapes/*` as **GPL-3+**
(Copyright 2017, kicad StepUp), not CC-BY-SA. It is copied unmodified and stays
under GPL-3+; this repository does not relicense it. `LED_THT.3dshapes` has no
specific entry, so the Debian default rule (`Files: *`, CC-BY-SA-4.0-with-exception,
KiCad Community) applies.

The MIT license of this repository does not supersede these third-party terms.

## Supplied license and copyright texts

Copied unmodified from the local Debian packages that supplied the models and
licenses; they carry the actual upstream notices (not a summary):

| local copy | source on this machine | bytes | SHA256 |
| --- | --- | ---: | --- |
| `licenses/kicad-packages3d-debian-copyright.txt` | `/usr/share/doc/kicad-packages3d/copyright` | 103515 | `46fab4abd8347f4aba796756e90351c711c5f19deeaca7c079f6ef51c844d560` |
| `licenses/GPL-3.txt` | `/usr/share/common-licenses/GPL-3` | 35149 | `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986` |

The Debian copyright file is the full machine-readable metadata: upstream source,
the exact KiCad exception wording, the per-directory copyright/license assignments
used for the table above, the complete **CC-BY-SA 4.0** legal code, and the note
that GPL-3 full text is supplied separately as `GPL-3.txt`.

Sources and canonical license links:

- KiCad 3D packages: <https://kicad.github.io/packages3d/> (upstream project
  <https://gitlab.com/kicad/libraries/kicad-packages3d>)
- CC-BY-SA 4.0: <https://creativecommons.org/licenses/by-sa/4.0/legalcode>
- CC-BY-SA 4.0 human-readable deed: <https://creativecommons.org/licenses/by-sa/4.0/>
- KiCad library license exception: as quoted verbatim in
  `licenses/kicad-packages3d-debian-copyright.txt`
- GNU GPL version 3: <https://www.gnu.org/licenses/gpl-3.0.html>

No model file was modified and no license was changed or dropped.
