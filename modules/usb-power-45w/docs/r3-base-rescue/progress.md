# BASE routing rescue — active working record

Input object: `1f6f298d31388c9c69234490ac8888acd3921ee4`; input BASE SHA256 `3058a7674e8cbc9be68ef285dd7c942790fde58a328e663c30252684a678d460`.
TOP unchanged SHA256 `922d34ab36596f123d9b7b7c67e7a22c116e14a0e083846d21c92b0f8b1a91eb`.

RS01 replaces the enclosing RESET_N F crossbar south of U13 with a local dogbone and B run. MAIN_OK under-body branch goes west to x68 instead of partitioning U13 at x72.38. No footprint moves. RS02 completes BAD_FILTERED through individually inspected F corridors beside D11 and under U1, with 0.5/0.3 vias. Native DRC/parity and stored/refilled support checks clean: **24 opens**.

Early local-search limitation: NOT_FAULT from U13.2 to U12.8 cannot currently escape using the existing single-connection helper after multiple endpoint/margin probes. Region: U13 south x69..78/y71..75, MAIN_OK B y74.2/diagonal to78, PD_BASE B x72.9, VPD_U1 B x78.85, plus dense PD circuitry at y76..82. The southern F lane RS02 used leaves an exact minimum-clearance slot beside PD_SENSE, not represented robustly by the raster helper. This is **not a proof of impossibility**. Proceeding with manual reroute/placement refinements, not stopping or requesting a rule waiver.

Commands so far: `python3 -B modules/usb-power-45w/tools/route_base_rescue.py apply RS01-free-u13`, `... apply RS02-bad`. All raw plans, rejected candidates, native reports and support audits under ignored `research/routing-rescue/`; canonical BASE saved after each accepted batch. Failed candidates never copied over canonical.

## RS14 status

Native BASE: 19 opens, 0 other DRC findings, parity 0; support copper stored/refilled clean. P12_OK TP12-to-XB2 and Q7-to-TP12 completed. NOT_FAULT RS04 was deliberately removed after it fenced the west-XB1 crossing; it remains one open, not claimed done. Q8 moved +0.2 mm X; its collector F lead re-laid. Only the U9 low-current VPD crossover via shifted to (81.05,89.525), not input or U8 power/Kelvin. RS12 rejected candidate never written to canonical; RS14 replaces it with DRC-clean paths.

Remaining counts: {'/MAIN_OK': 1, '/RUN': 1, '/P12_OK': 1, '/P5_OK': 3, '/VPD': 1, '/N12_OK': 2, '/MAIN_LED_OK': 1, '/NOT_FAULT': 1, '/MON_20': 1, '/V20_OK': 2, '/LED_RETURN': 4, 'Net-(D18-K)': 1}

## Coordinated placement/corridor stage (RS15–RS18)

Native clean placement accepted after isolated fit trials. U14 rotated 90 at (64.8,69.2); U13 rotated 0 at (73.25,69.6). C53/C54 now beside the actual VDD pins, not across MHB2. R27/R28/R63/R83 and TP3/4/5/7/8 plus R4 relocated to retain all courtyards. Exact positions are explicit in RS15. U14/U13 GND vias moved under their bodies; low-current PD_BASE and VPD_U1 crossovers re-laid below the intended B control bus, removing the two vertical fences. High-current input, U8/Kelvin and TOP untouched. Controlled rip raised opens to44; local reconnection RS16/RS18 reduces to30. Native DRC and parity0; stored/refilled support copper0. The sole added inner-layer path is a short ~5.14-mm POWER-net VPD hop, width0.25, across the PD auxiliaries (not a signal escape); all planes remain one piece.

Reserved B bands: N12_OK around y72.7, P5_OK y73.2, P12_OK y73.7, MAIN_LED_OK y74.3, with endpoint/fanout transitions kept out of the MHB2 neck. Other logic crossings use north lanes and F lanes, not a new blocking B diagonal.

RS44 was immediately rolled back: its B crossing below J2 split the existing -12V B heat/current pour, producing an extra power open despite other native DRC findings staying zero. The pre-RS44 canonical checkpoint (6 control opens) was restored from its own /tmp backup. No power-pour change accepted.
