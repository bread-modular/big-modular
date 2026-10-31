> **Superseded (2026-11-01):** BASE routing is finished (0 opens); see [final record](/modules/usb-power-45w/docs/r3-base/final/README.md). Kept as history.

# LAST handoff — preserved BASE rescue WIP for Opus completion

**Internal transfer, not mission completion, release, or abandonment. User still requires fully routed BASE and independent final verification. No routing/planning/research was performed in this handoff turn.**

## Exact checkpoint and safe import

- Branch: `okbrain/big-modular/208-cd94ed33`; parent: `4eb072f5fc28270ef5ad029ebfd7adb47fd36fa3`.
- Original imported WIP object: `1f6f298d31388c9c69234490ac8888acd3921ee4`. Do not restore that earlier board over this checkpoint.
- Canonical BASE SHA256: `bfdbf749093d668a348bf25d2bd6a983e5bc00c260b2581398723021d6c8c899`.
- TOP SHA256: `922d34ab36596f123d9b7b7c67e7a22c116e14a0e083846d21c92b0f8b1a91eb`; byte-identical to this branch parent. No TOP/rules/schematic/common-file edits.
- Fresh native canonical BASE: **2 opens; 0 other violations; 0 parity findings; 0 exclusions**. Exact native findings below.
- Commit containing this document is the transfer object; its SHA and post-commit clean status are recorded in the handoff response. One branch-local WIP commit only, with message `Preserve final base routing rescue state for Opus completion; two opens remain`.
- Import only the manifest below via this transfer object into a fresh isolated branch. Do not merge/cherry-pick, overwrite TOP/common files, replay batch history, or import an older PCB. Helpers describe manual accepted history, not a rebuild recipe.
- Verification did not alter canonical PCB bytes. Raw verification artifacts remain ignored under `research/routing-rescue/handoff-last/` in this workspace; the durable status and diagnostics below travel with this commit.

## Remaining islands (fresh native inspection)

```json
[
  {
    "description": "Missing connection between items",
    "items": [
      {
        "description": "Pad 8 [/NOT_RUN] of U14 on F.Cu",
        "pos": {
          "x": 68.61,
          "y": 66.725
        },
        "uuid": "86984cd0-7acc-56dd-9023-1c0c771e1c5e"
      },
      {
        "description": "Pad 1 [/NOT_RUN] of Q5 on F.Cu",
        "pos": {
          "x": 124.9125,
          "y": 98.15
        },
        "uuid": "65c3827c-b49a-5ddf-b211-b4932de258bf"
      }
    ],
    "severity": "error",
    "type": "unconnected_items"
  },
  {
    "description": "Missing connection between items",
    "items": [
      {
        "description": "Pad 6 [/FAULT_CLK] of U13 on F.Cu",
        "pos": {
          "x": 70.775,
          "y": 72.14
        },
        "uuid": "02b0c3dc-1a96-5d9c-929f-2d7b75bbaf30"
      },
      {
        "description": "Pad 11 [/FAULT_CLK] of U12 on F.Cu",
        "pos": {
          "x": 101.275,
          "y": 90.8
        },
        "uuid": "5d319690-92de-59a6-8419-3b058d0c6820"
      }
    ],
    "severity": "error",
    "type": "unconnected_items"
  }
]
```

All coordinates below are board millimetres. **Both remaining nets have zero existing tracks, zero vias and zero copper zones.** Thus there is no surviving U12 FAULT_CLK stub/via, and no hidden same-net track anchor to join; both islands of each net are isolated F.Cu pads. Pad surfaces/edges are legitimate endpoints, not just centres, but local accessibility still needs native checking.

```json
{
  "/FAULT_CLK": {
    "pads": [
      {
        "ref": "U12",
        "pad": "11",
        "xy": [
          101.275,
          90.8
        ],
        "layer": "F.Cu",
        "uuid": "5d319690-92de-59a6-8419-3b058d0c6820"
      },
      {
        "ref": "U13",
        "pad": "6",
        "xy": [
          70.775,
          72.14
        ],
        "layer": "F.Cu",
        "uuid": "02b0c3dc-1a96-5d9c-929f-2d7b75bbaf30"
      }
    ],
    "tracks_vias": [],
    "zones": []
  },
  "/NOT_RUN": {
    "pads": [
      {
        "ref": "U14",
        "pad": "8",
        "xy": [
          68.61,
          66.725
        ],
        "layer": "F.Cu",
        "uuid": "86984cd0-7acc-56dd-9023-1c0c771e1c5e"
      },
      {
        "ref": "Q5",
        "pad": "1",
        "xy": [
          124.9125,
          98.15
        ],
        "layer": "F.Cu",
        "uuid": "65c3827c-b49a-5ddf-b211-b4932de258bf"
      }
    ],
    "tracks_vias": [],
    "zones": []
  }
}
```

## Why the helper did not close the last two

The print-only raster helper reported NO_PATH, including from alternate B targets near U12 (99.4,90.8) and (104.6,92.1). Those targets are diagnostic coordinates, **not existing net anchors**. Repeated bounded searches exhausted their reachable raster region, not the physical design space. The finer 0.025-mm FAULT_CLK probe also failed. This does not prove impossibility or identify a definitive physical blocker.

U13.6 fanout was locally enclosed by its own GND/ARMED dogbones and the accepted parallel status bus. RS50 moved only those local dogbones, leaving the bus intact; it remained native-clean with two opens. Whether a different local escape, actual pad-edge join, or a small target-side re-fanout is sufficient has NOT been established. No broad redesign is prescribed.

Previous negative-margin runs were diagnostic suggestions only; no negative-margin clearance/rule acceptance is authorized. Native minimum 0.2-mm clearance remains authoritative. Do not count a suggested route as applied.

## Bounded local self-copper rework authorized by user

- Inspect U13.6 source escape and U12.11 target pin fanout. Nearby AI-created GND/V3V3, ARMED, RESET_N, START_READY and FAULT_LATCH dogbones may be locally re-laid while preserving their nets and connections. Under-body dogbones are allowed only clear of pad copper/mask openings.
- RS50 current U13 GND via is (72.65,70.6), fed via (72.65,73.41) from U13.7. ARMED via is (69.4,69.6); B fanout is through (70.1,69.6), (70.1,71.4) into the existing parallel bus. These are not FAULT_CLK anchors.
- NOT_RUN is U14.8 to Q5.1, with no existing copper. Local own low-current/GND/V3V3 fanout refinements are permitted; do not alter Q5 negative-control mission or accepted U8 protection/Kelvin copper.
- Preserve fixed J1/J2/SW1/LEDs/XB1/XB2, mounts/outline/panel/stack, values/packages/fields, all-F assembly, 2-mm front THT assembly margin, five support annuli r1.7..3.6, 5-mm base gap, and existing exact J1/SW1 PAD-only edge exceptions.
- No In1 tracks, no via-in-pad/mask-overlap except original footprint EP thermal vias, no new rules/severity/exclusions/NC/pin changes. In2 is short POWER/RETURN hops only, never FAULT_CLK/NOT_RUN/status routing. GND/N12_RAW/-12/LED_RETURN identities remain distinct.

## Accepted RS history (do not replay)

Every entry below had a native-clean writeback. Later accepted batches intentionally supersede earlier copper. RS12 was rejected and never promoted. RS44 was briefly promoted, then immediately restored from its own pre-batch backup because its signal crossing split the -12V B pour and introduced a power open; **RS44 is NOT in the current board**. No rollback/import occurred during this handoff.

| Accepted batch | Opens at that writeback |
| --- | ---: |
| `RS01-free-u13` | 25 |
| `RS02-bad` | 24 |
| `RS03-mainok-north` | 24 |
| `RS04-notfault` | 23 |
| `RS05-run-local` | 22 |
| `RS06-anybad` | 21 |
| `RS07-mainok-under-u14` | 21 |
| `RS08-notrun` | 20 |
| `RS09-p12-east` | 19 |
| `RS10-q8-gap` | 19 |
| `RS11-vpd-crossover` | 19 |
| `RS13-release-nf` | 20 |
| `RS14-p12-led` | 19 |
| `RS15-corridor-fit` | 44 |
| `RS16-locals` | 36 |
| `RS17-clear-bus` | 36 |
| `RS18-local-restore` | 30 |
| `RS19-p12-bus` | 29 |
| `RS20-status-bus` | 27 |
| `RS21-mainled-bus` | 26 |
| `RS22-u1-power-hop` | 26 |
| `RS23-p5-led` | 25 |
| `RS24-p5-east` | 24 |
| `RS25-n12-east` | 23 |
| `RS26-bad-bus` | 22 |
| `RS27-armed-bus` | 21 |
| `RS28-armed-latch` | 20 |
| `RS29-mainok-west` | 19 |
| `RS30-mainok-cross` | 18 |
| `RS31-mainok-east` | 17 |
| `RS32-vpd-tap` | 16 |
| `RS33-vin-tp` | 15 |
| `RS34-led-local` | 14 |
| `RS35-led-67` | 13 |
| `RS36-led-return-source` | 12 |
| `RS37-south-corridor` | 12 |
| `RS38-led-return-east` | 11 |
| `RS39-front-led-pair` | 10 |
| `RS40-timer-north` | 9 |
| `RS41-run-east` | 8 |
| `RS42-v20-west` | 7 |
| `RS43-v20-east` | 6 |
| `RS45-mon20` | 5 |
| `RS46-anybad` | 4 |
| `RS47-reset` | 3 |
| `RS48-return-local-hops` | 3 |
| `RS49-notfault` | 2 |
| `RS50-clock-escape-space` | 2 |

RS01–14 opened the west logic escape and connected LED/status branches. RS15–18 deliberately reoriented U13/U14 and nearby passives, re-established local control/decoupling, and moved PD auxiliary fences below the bus. RS19–28 completed the parallel P12/P5/N12/MAIN_LED/BAD_FILTERED/ARMED bands. RS29–33 restored MAIN_OK/VPD/VIN taps. RS34–39 re-fanned LED drivers and the south front crossing. RS40–43 restored TIMER_GO/RUN/V20_OK; RS45–47 completed MON_20/ANY_BAD/RESET_N. RS48 shortened the switched LED load return with two local In2 return hops; RS49 used the freed B perimeter for NOT_FAULT. RS50 is the last accepted copper edit. Subsequent path probes were print-only.

RS48 final return path is Q10.3 → (68.9,82.0), In2 to (68.9,84.4), B to (68.55,90.2), then local In2 around actual CC barrels through (68.25,90.5), (68.25,91.9), (69.0,92.65), (74.0,93.2), then F to Q6.2. It remains the switched LED LOAD CURRENT RETURN through Q10, not GND. Other added local In2 power hops are VPD and VPD_U1. Check actual filled pieces and current path again after edits.

## Current macroplacement (native coordinates, all moves preserved)

All listed components remain on F.Cu; this is the actual canonical position, not a proposal. Protected input/core-power/U8 groups were not moved. Q8 was shifted slightly for local fanout; R88/C57 and local supply vias were repositioned for the front crossing. U13/U14 and their decouplers/passives retain the accepted coherent corridor layout.

| Reference | X mm | Y mm | Rotation degrees | Layer |
| --- | ---: | ---: | ---: | --- |
| C53 | 60.99 | 64.1 | 180.0 | F.Cu |
| C54 | 77.7 | 64.1 | 180.0 | F.Cu |
| C57 | 129.4 | 100.25 | 0.0 | F.Cu |
| Q8 | 83.825 | 89.5 | 180.0 | F.Cu |
| R27 | 70.95 | 76.9 | 0.0 | F.Cu |
| R28 | 78.6 | 73.2 | 180.0 | F.Cu |
| R4 | 67.0 | 76.65 | 180.0 | F.Cu |
| R63 | 84.3 | 71.9 | 0.0 | F.Cu |
| R83 | 86.75 | 64.1 | 0.0 | F.Cu |
| R88 | 139.3 | 92.2 | 0.0 | F.Cu |
| TP3 | 64.75 | 74.8 | 90.0 | F.Cu |
| TP4 | 66.0 | 64.35 | 90.0 | F.Cu |
| TP5 | 87.05 | 69.5 | 90.0 | F.Cu |
| TP7 | 59.0 | 73.2 | 90.0 | F.Cu |
| TP8 | 68.2 | 74.1 | 90.0 | F.Cu |
| U13 | 73.25 | 69.6 | 0.0 | F.Cu |
| U14 | 64.8 | 69.2 | 90.0 | F.Cu |

## Fresh handoff verification status (not final routing acceptance)

- BASE native DRC/parity counts: `{"violations": 0, "unconnected_items": 2, "schematic_parity": 0, "excluded": 0}`.
- Strict regression discovery command: `/usr/bin/python3 -B -m unittest discover -s modules/usb-power-45w/tools -p test*.py -v`; tests run: **9**; exit: **0**. Exact output below; do not infer nine passes unless nine tests ran successfully.
- `check_stack.py` fresh execution exit: **0**. Its actual problems and native/aggregate/geometry results are reproduced below; opens are still unfinished work.
- Stored/refilled support checks, both boards: `{"base-stored": [], "base-refilled": [], "top-stored": [], "top-refilled": []}`.
- Canonical BASE and TOP SHA256 values were rechecked unchanged after all verification. No checker, assertion, baseline, rule or severity was changed to make a test pass.

### Strict regression output
```text
test_old_outline_plus_hole_is_seamed (test_support_keepout.SupportKeepout.test_old_outline_plus_hole_is_seamed) ... ./kicad/include/properties/property.h(607): assert "m_choices.GetCount() > 0" failed in PROPERTY_ENUM(): No enum choices defined
./kicad/include/properties/property.h(607): assert "m_choices.GetCount() > 0" failed in PROPERTY_ENUM(): No enum choices defined
./kicad/include/properties/property.h(607): assert "m_choices.GetCount() > 0" failed in PROPERTY_ENUM(): No enum choices defined
/usr/lib/python3/dist-packages/pcbnew.py:63: DeprecationWarning: The SWIG-based Python interface to the PCB editor is deprecated and will be removed in a future version of KiCad.  Please plan to move to the new IPC API and/or make use of the kicad-cli tool for your KiCad automation needs.
  warnings.warn("The SWIG-based Python interface to the PCB editor is deprecated and will be removed "
[32mok[0m
test_sectors_round_trip_clean (test_support_keepout.SupportKeepout.test_sectors_round_trip_clean) ... 02:28:44: Debug: Adding duplicate image handler for 'PNG file'
02:28:44: Debug: Adding duplicate image handler for 'JPEG file'
02:28:44: Debug: Adding duplicate image handler for 'TIFF file'
02:28:44: Debug: Adding duplicate image handler for 'GIF file'
02:28:44: Debug: Adding duplicate image handler for 'PNM file'
02:28:44: Debug: Adding duplicate image handler for 'PCX file'
02:28:44: Debug: Adding duplicate image handler for 'IFF file'
02:28:44: Debug: Adding duplicate image handler for 'Windows icon file'
02:28:44: Debug: Adding duplicate image handler for 'Windows cursor file'
02:28:44: Debug: Adding duplicate image handler for 'Windows animated cursor file'
02:28:44: Debug: Adding duplicate image handler for 'TGA file'
02:28:44: Debug: Adding duplicate image handler for 'XPM file'
[32mok[0m
test_seed_refuses_routed_top (test_support_keepout.SupportKeepout.test_seed_refuses_routed_top) ... [32mok[0m
test_committed_old_hardware_rejected (test_tps3808_pins.TPS3808PinIdentity.test_committed_old_hardware_rejected)
The real pre-fix native schematic, with its own circuit/CRIT tables restored. ... [32mok[0m
test_current_design_passes (test_tps3808_pins.TPS3808PinIdentity.test_current_design_passes) ... [32mok[0m
test_fixed_symbol_with_old_nets_rejected (test_tps3808_pins.TPS3808PinIdentity.test_fixed_symbol_with_old_nets_rejected) ... [32mok[0m
test_old_self_consistent_map_rejected (test_tps3808_pins.TPS3808PinIdentity.test_old_self_consistent_map_rejected) ... [32mok[0m
test_old_symbol_with_fixed_nets_rejected (test_tps3808_pins.TPS3808PinIdentity.test_old_symbol_with_fixed_nets_rejected) ... [32mok[0m
test_symbols_match_ti_table (test_tps3808_pins.TPS3808PinIdentity.test_symbols_match_ti_table) ... [32mok[0m

----------------------------------------------------------------------
Ran 9 tests in 1.844s

[32mOK[0m
```

### Native ERC/DRC and aggregate equivalence

```json
{
  "problems": [],
  "erc": {
    "root": 0,
    "base": 0,
    "top": 0
  },
  "drc": {
    "base": {
      "violations": {},
      "unconnected": 2,
      "parity": 0,
      "excluded": 0
    },
    "top": {
      "violations": {},
      "unconnected": 0,
      "parity": 0,
      "excluded": 0
    }
  },
  "interconnect_equivalence": {
    "root_refs": 216,
    "base_refs": 130,
    "top_refs": 86,
    "refs_on_both_boards": [],
    "refs_missing": [],
    "refs_extra": [],
    "value_footprint_field_mismatch": [],
    "root_nets_incl_NC": 145,
    "joined_nets_incl_NC": 145,
    "nets_only_in_root": 0,
    "nets_only_in_join": 0,
    "equal": true,
    "method": "union of the two native board netlists, XB1.n=XT1.n and XB2.n=XT2.n, header pins removed, compared as exact (ref, pin) partitions incl. single-pin no-connect nets"
  },
  "fixed_interfaces_same_as_accepted": {
    "J1": true,
    "J2": true,
    "SW1": true,
    "D8": true,
    "D16": true,
    "D17": true,
    "D18": true
  },
  "J3_absent": true
}
```

### Stack/mechanical results

```json
{
  "geometry": {
    "base": {
      "courtyard_edge_lt_1mm": [],
      "closest_courtyard_edge_mm": [
        [
          "D8",
          0.0
        ],
        [
          "SW1",
          0.0
        ],
        [
          "D17",
          0.0
        ],
        [
          "D16",
          0.0
        ],
        [
          "D18",
          0.0
        ],
        [
          "J1",
          0.0
        ]
      ],
      "approved_overhangs": [
        "D16",
        "D17",
        "D18",
        "D8",
        "J1",
        "SW1"
      ],
      "hand_solder_lt_2mm": [],
      "closest_hand_solder_mm": [
        [
          [
            "R49",
            "XB1"
          ],
          1.215
        ],
        [
          [
            "C48",
            "XB1"
          ],
          1.46
        ],
        [
          [
            "R91",
            "XB1"
          ],
          1.46
        ],
        [
          [
            "R69",
            "XB1"
          ],
          1.46
        ],
        [
          [
            "TP14",
            "XB1"
          ],
          1.53
        ],
        [
          [
            "TP10",
            "XB1"
          ],
          1.53
        ]
      ],
      "vias": 305,
      "vias_in_smd_pads": [],
      "tracks_on_In1": 0,
      "tracks": 1002,
      "planes": {
        "F.Cu:+5V": {
          "pieces": 1,
          "areas_mm2": [
            24.3
          ]
        },
        "F.Cu:/EF_IN": {
          "pieces": 1,
          "areas_mm2": [
            17.1
          ]
        },
        "F.Cu:VIN": {
          "pieces": 1,
          "areas_mm2": [
            6.5
          ]
        },
        "F.Cu:N12_RAW": {
          "pieces": 1,
          "areas_mm2": [
            20.9
          ]
        },
        "F.Cu:+12V": {
          "pieces": 1,
          "areas_mm2": [
            48.5
          ]
        },
        "F.Cu:-12V": {
          "pieces": 1,
          "areas_mm2": [
            56.3
          ]
        },
        "F.Cu:/VPD": {
          "pieces": 1,
          "areas_mm2": [
            51.6
          ]
        },
        "F.Cu:/N_SENSE": {
          "pieces": 1,
          "areas_mm2": [
            22.8
          ]
        },
        "B.Cu:/EF_IN": {
          "pieces": 1,
          "areas_mm2": [
            87.5
          ]
        },
        "B.Cu:/VBUS": {
          "pieces": 1,
          "areas_mm2": [
            12.5
          ]
        },
        "B.Cu:-12V": {
          "pieces": 1,
          "areas_mm2": [
            109.0
          ]
        },
        "B.Cu:/VPD": {
          "pieces": 1,
          "areas_mm2": [
            50.1
          ]
        },
        "In1.Cu:GND": {
          "pieces": 1,
          "areas_mm2": [
            2930.7
          ]
        },
        "In2.Cu:VIN": {
          "pieces": 1,
          "areas_mm2": [
            401.5
          ]
        },
        "In2.Cu:V3V3": {
          "pieces": 1,
          "areas_mm2": [
            2377.8
          ]
        }
      }
    },
    "top": {
      "courtyard_edge_lt_1mm": [],
      "closest_courtyard_edge_mm": [
        [
          "R11",
          1.0
        ],
        [
          "support@Y109.2",
          1.004
        ],
        [
          "support@Y20.5",
          1.004
        ],
        [
          "support@Y82.0",
          1.004
        ],
        [
          "support@Y89.0",
          1.004
        ],
        [
          "support@Y46.2",
          1.004
        ]
      ],
      "approved_overhangs": [],
      "hand_solder_lt_2mm": [],
      "closest_hand_solder_mm": [
        [
          [
            "D12",
            "XT1"
          ],
          2.0
        ],
        [
          [
            "C33",
            "XT2"
          ],
          2.02
        ],
        [
          [
            "C25",
            "XT1"
          ],
          2.04
        ],
        [
          [
            "R44",
            "XT2"
          ],
          2.085
        ],
        [
          [
            "R35",
            "XT2"
          ],
          2.085
        ],
        [
          [
            "U7",
            "XT1"
          ],
          2.1
        ]
      ],
      "vias": 121,
      "vias_in_smd_pads": [],
      "tracks_on_In1": 0,
      "tracks": 308,
      "planes": {
        "F.Cu:VIN": {
          "pieces": 1,
          "areas_mm2": [
            18.7
          ]
        },
        "F.Cu:Net-(U3-SW)": {
          "pieces": 1,
          "areas_mm2": [
            10.3
          ]
        },
        "F.Cu:GND": {
          "pieces": 1,
          "areas_mm2": [
            8.4
          ]
        },
        "F.Cu:+12V": {
          "pieces": 1,
          "areas_mm2": [
            7.5
          ]
        },
        "F.Cu:P12_RAW": {
          "pieces": 1,
          "areas_mm2": [
            85.3
          ]
        },
        "F.Cu:N12_RAW": {
          "pieces": 1,
          "areas_mm2": [
            106.3
          ]
        },
        "F.Cu:Net-(U2-SW)": {
          "pieces": 1,
          "areas_mm2": [
            4.8
          ]
        },
        "B.Cu:+12V": {
          "pieces": 1,
          "areas_mm2": [
            77.2
          ]
        },
        "B.Cu:P5_RAW": {
          "pieces": 1,
          "areas_mm2": [
            386.6
          ]
        },
        "B.Cu:GND": {
          "pieces": 1,
          "areas_mm2": [
            64.6
          ]
        },
        "B.Cu:P12_RAW": {
          "pieces": 2,
          "areas_mm2": [
            438.9,
            10.2
          ]
        },
        "B.Cu:N12_RAW": {
          "pieces": 1,
          "areas_mm2": [
            221.2
          ]
        },
        "B.Cu:+5V": {
          "pieces": 1,
          "areas_mm2": [
            63.3
          ]
        },
        "B.Cu:VIN": {
          "pieces": 1,
          "areas_mm2": [
            18.7
          ]
        },
        "In1.Cu:GND": {
          "pieces": 3,
          "areas_mm2": [
            2417.8,
            2.8,
            2.1
          ]
        },
        "In2.Cu:VIN": {
          "pieces": 4,
          "areas_mm2": [
            2360.2,
            2.6,
            2.3,
            2.0
          ]
        }
      }
    }
  },
  "stack": {
    "X_stack": {
      "panel_X": [
        0.0,
        20.0
      ],
      "base_B": 2.5,
      "base_F": 4.1,
      "thickness": 1.6,
      "gap": 5.0,
      "top_B": 9.1,
      "top_F": 10.7
    },
    "tolerances_assumed": {
      "bracket_web_X": 0.2,
      "base_thickness": 0.16,
      "spacer_length": 0.1,
      "top_thickness": 0.16,
      "solder_standoff": 0.1,
      "top_board_bow": 0.3
    },
    "linear_tolerance_sum": 1.02,
    "tallest_top_part": "C34",
    "top_X_max_nominal": 18.7,
    "width_margin_to_X20_nominal": 1.3,
    "width_margin_worst_linear": 0.28,
    "base_parts_under_top_lowest_clearance": [
      [
        "D8",
        3.9,
        1.1
      ],
      [
        "D17",
        3.9,
        1.1
      ],
      [
        "D16",
        3.9,
        1.1
      ],
      [
        "D18",
        3.9,
        1.1
      ],
      [
        "J1",
        3.36,
        1.64
      ],
      [
        "SW1",
        3.3,
        1.7
      ]
    ],
    "under_top_min_nominal": 1.1,
    "under_top_min_worst_linear": 0.44,
    "top_outline_to_J2_box_plug_ribbon_mm": {
      "J2": 1.5,
      "J2_plug": 2.93,
      "J2_ribbon": 5.19
    },
    "collisions_brackets_nuts_tools_panel_vs_top": [],
    "through_bolt": {
      "hardware_class": "ISO 7380 M3 x 12 button head under base B, plain 5.0 mm spacer (OD <= 6), DIN 934 M3 nut on top F",
      "head_X_min": 0.85,
      "grip_plus_nut_mm": 10.6,
      "thread_exposure_nominal_mm": 1.4,
      "thread_exposure_worst_mm": 0.63,
      "tip_X_nominal": 14.5,
      "tools": "hex key on the head from the open base-B side (module out of the rack); nut held by a thin-wall 5.5 AF socket, OD <= 8.5 (top tool courtyard r4.25) or flat pliers",
      "opposing_screw_collision": "not possible: one through bolt per support",
      "supports_YZ": [
        [
          20.5,
          36.7
        ],
        [
          46.2,
          36.7
        ],
        [
          89.0,
          36.7
        ],
        [
          82.0,
          7.3
        ],
        [
          109.2,
          36.7
        ]
      ]
    },
    "header_pins": {
      "part": "Samtec TSW-110-07-G-D / TSW-103-07-G-D (catalogue F-226 lead style -07)",
      "plastic_on_base_F": 2.54,
      "air_gap_above_plastic": 2.46,
      "tail_below_base_B": 0.94,
      "tail_below_base_B_max": 1.8,
      "post_end_X": 12.48,
      "post_above_top_F": 1.78,
      "post_above_top_F_min": 0.5,
      "note": "nominal catalogue lengths; soldered all-pins-loaded current is a prototype gate; pins are not supports"
    },
    "cabled_envelope": "bare boards end at Z42; the mated J2 plug + ribbon envelope reaches Z50 (proposal envelope) - 42 mm is NOT claimed with the cable fitted"
  }
}
```

### Current additional routing geometry and actual filled pieces

```json
{
  "vias": 305,
  "tracks": 1002,
  "vias_in_smd_pad_or_mask": [],
  "tracks_on_In1": 0,
  "zero_length": [],
  "duplicates": [],
  "dangling_ends": [],
  "off_grid_ends": 1655,
  "planes": {
    "F.Cu:+5V": [
      {
        "pieces": 1,
        "areas_mm2": [
          24.3
        ]
      }
    ],
    "F.Cu:/EF_IN": [
      {
        "pieces": 1,
        "areas_mm2": [
          28.03
        ]
      },
      {
        "pieces": 1,
        "areas_mm2": [
          17.11
        ]
      }
    ],
    "F.Cu:VIN": [
      {
        "pieces": 1,
        "areas_mm2": [
          6.52
        ]
      }
    ],
    "F.Cu:N12_RAW": [
      {
        "pieces": 1,
        "areas_mm2": [
          20.91
        ]
      }
    ],
    "F.Cu:+12V": [
      {
        "pieces": 1,
        "areas_mm2": [
          48.47
        ]
      }
    ],
    "F.Cu:-12V": [
      {
        "pieces": 1,
        "areas_mm2": [
          56.33
        ]
      }
    ],
    "F.Cu:/VPD": [
      {
        "pieces": 1,
        "areas_mm2": [
          51.58
        ]
      }
    ],
    "F.Cu:/N_SENSE": [
      {
        "pieces": 1,
        "areas_mm2": [
          22.76
        ]
      }
    ],
    "B.Cu:/EF_IN": [
      {
        "pieces": 1,
        "areas_mm2": [
          87.46
        ]
      }
    ],
    "B.Cu:/VBUS": [
      {
        "pieces": 1,
        "areas_mm2": [
          12.52
        ]
      }
    ],
    "B.Cu:-12V": [
      {
        "pieces": 1,
        "areas_mm2": [
          109.03
        ]
      }
    ],
    "B.Cu:/VPD": [
      {
        "pieces": 1,
        "areas_mm2": [
          50.12
        ]
      }
    ],
    "In1.Cu:GND": [
      {
        "pieces": 1,
        "areas_mm2": [
          2930.7
        ]
      }
    ],
    "In2.Cu:VIN": [
      {
        "pieces": 1,
        "areas_mm2": [
          401.49
        ]
      }
    ],
    "In2.Cu:V3V3": [
      {
        "pieces": 1,
        "areas_mm2": [
          2377.78
        ]
      }
    ]
  }
}
```

### Required after closing the final two

Rerun full native all-severity ERC root/base/top; DRC both boards including warnings/exclusions/opens/parity; check_stack aggregate 216 references /145 nets and exact fields/pins/geometry; both boards stored AND refilled support-copper checks; the strict nine regression tests; noVIP/mask/edge/THT-solder/annulus checks; In1 zero tracks; each VIN/V3V3/GND and power filled piece/current path; no zero/dangling/duplicate copper and no power-neck/return damage. No known false positive may be hidden or suppressed. Preserve TOP byte identity and compare protected power/Kelvin copper. Capture readable actual-filled whole BASE and critical-region views with URLs for independent review. This handoff is not that final sign-off.

## Import manifest

Only the following paths belong to this transfer. Board/helper hashes are explicit; the transfer Git object fixes every documentation byte. No TOP, rules, schematics, exports, vendor files or common files are included.

- `modules/usb-power-45w/hardware/base/usb-power-45w-base.kicad_pcb` — SHA256 `bfdbf749093d668a348bf25d2bd6a983e5bc00c260b2581398723021d6c8c899`
- `modules/usb-power-45w/tools/route_base_r3.py` — SHA256 `c7fcf013497c85da90aa9a3a546efa5880518862128babadcb6c013eac940ba2`
- `modules/usb-power-45w/tools/route_base_r3_batches.py` — SHA256 `6a1f78843f29dcbee941c72a7454af2f011d5bbd3e090f2747b2d66c8a31a664`
- `modules/usb-power-45w/tools/route_base_r3_final.py` — SHA256 `e724d4c3a7621b953d6c930004e29428d592fa34cbacbb661f8ee5f9098eff3b`
- `modules/usb-power-45w/tools/route_base_rescue.py` — SHA256 `475f5d08495ac72eb0ee780e7042103d2b2545f781eb93a33282409769310424`
- `modules/usb-power-45w/docs/r3-base/HANDOFF-25.md`
- `modules/usb-power-45w/docs/r3-base/HANDOFF.md`
- `modules/usb-power-45w/docs/r3-base/checkpoint.md`
- `modules/usb-power-45w/docs/r3-base/drc-handoff.json`
- `modules/usb-power-45w/docs/r3-base/drc-w2.json`
- `modules/usb-power-45w/docs/r3-base/final-ckpt2-u8.png`
- `modules/usb-power-45w/docs/r3-base/final-ckpt2-west-corridor.png`
- `modules/usb-power-45w/docs/r3-base/final-ckpt2-whole.png`
- `modules/usb-power-45w/docs/r3-base/final-ckpt3-u8.png`
- `modules/usb-power-45w/docs/r3-base/final-ckpt3-whole.png`
- `modules/usb-power-45w/docs/r3-base/final-ckpt4-corridor.png`
- `modules/usb-power-45w/docs/r3-base/final-ckpt4-hash.txt`
- `modules/usb-power-45w/docs/r3-base/final-ckpt4-leds.png`
- `modules/usb-power-45w/docs/r3-base/final-ckpt4-u8.png`
- `modules/usb-power-45w/docs/r3-base/final-ckpt4-whole.png`
- `modules/usb-power-45w/docs/r3-base/final-progress.md`
- `modules/usb-power-45w/docs/r3-base/input-heat-w2.png`
- `modules/usb-power-45w/docs/r3-base/neg-kelvin-w2.png`
- `modules/usb-power-45w/docs/r3-base/open-final-ckpt1.txt`
- `modules/usb-power-45w/docs/r3-base/open-final-ckpt2.txt`
- `modules/usb-power-45w/docs/r3-base/open-final-ckpt3.txt`
- `modules/usb-power-45w/docs/r3-base/open-final-ckpt4.txt`
- `modules/usb-power-45w/docs/r3-base/open-handoff.txt`
- `modules/usb-power-45w/docs/r3-base/open-w2.txt`
- `modules/usb-power-45w/docs/r3-base/whole-w2.png`
- `modules/usb-power-45w/docs/r3-base-rescue/corridor-plan.md`
- `modules/usb-power-45w/docs/r3-base-rescue/progress.md`
- `modules/usb-power-45w/docs/r3-base-rescue/HANDOFF-LAST.md`

## Local copper inventory for narrow inspection only

These are neighboring current own-control/power dogbones, **not same-net anchors for the open nets**. UUIDs/coordinates let Opus inspect individual native objects without replaying a helper. This is an inventory, not a routing plan.

```json
[
  {
    "uuid": "36f92225-e1cb-534d-a910-76a59b3e47ea",
    "net": "GND",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      72.65,
      73.41
    ],
    "end": [
      72.65,
      70.6
    ]
  },
  {
    "uuid": "50edd415-c4eb-5cd7-a741-7582a22ce753",
    "net": "GND",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      70.775,
      73.41
    ],
    "end": [
      72.65,
      73.41
    ]
  },
  {
    "uuid": "95055244-b385-5df9-9913-d247e43b1446",
    "net": "GND",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      102.6,
      90.5
    ],
    "end": [
      102.6,
      96.5
    ]
  },
  {
    "uuid": "958506b9-8cee-5300-943c-58dd85127683",
    "net": "GND",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      96.325,
      94.61
    ],
    "end": [
      96.3,
      95.65
    ]
  },
  {
    "uuid": "a5bf5827-845c-5491-8cd8-375ed53c16c6",
    "net": "GND",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      99.975,
      85.1
    ],
    "end": [
      101.1,
      85.1
    ]
  },
  {
    "uuid": "ae5376f0-e92d-5297-86ad-3decfecb3f87",
    "net": "GND",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      103.6125,
      94.05
    ],
    "end": [
      102.6,
      94.05
    ]
  },
  {
    "uuid": "b2af15ea-69ae-5956-92e4-ee04ed14a5b2",
    "net": "GND",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      103.6125,
      90.5
    ],
    "end": [
      102.6,
      90.5
    ]
  },
  {
    "uuid": "e2d35185-2aa9-5166-9c90-839b696f45d1",
    "net": "GND",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      68.61,
      71.675
    ],
    "end": [
      68.61,
      70.0
    ]
  },
  {
    "uuid": "5d425d15-4928-5777-b421-7938eaf68395",
    "net": "GND",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      68.61,
      70.0
    ],
    "end": [
      68.61,
      70.0
    ]
  },
  {
    "uuid": "ca08b07d-43c5-5b5a-a7c6-0400393b1743",
    "net": "GND",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      101.1,
      85.1
    ],
    "end": [
      101.1,
      85.1
    ]
  },
  {
    "uuid": "cdf15216-2db3-556a-916c-2228b2b58258",
    "net": "GND",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      72.65,
      70.6
    ],
    "end": [
      72.65,
      70.6
    ]
  },
  {
    "uuid": "e4dc5a44-de3a-582c-8ba3-48a0c5f0c6d0",
    "net": "GND",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      96.3,
      95.65
    ],
    "end": [
      96.3,
      95.65
    ]
  },
  {
    "uuid": "25520241-d918-5fd9-8f60-c869070d5adc",
    "net": "/RUN",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      70.775,
      68.33
    ],
    "end": [
      73.25,
      68.33
    ]
  },
  {
    "uuid": "4cd0d66f-8f71-524d-a786-a6d2ad7f345d",
    "net": "/RUN",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      73.25,
      72.14
    ],
    "end": [
      75.725,
      72.14
    ]
  },
  {
    "uuid": "5eddae7c-f26e-51f7-b5a8-8ad6c5ad7061",
    "net": "/RUN",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      72.0,
      68.33
    ],
    "end": [
      74.25,
      66.075
    ]
  },
  {
    "uuid": "9dabe7c8-f3a5-5b27-8091-5bd0e0cf169a",
    "net": "/RUN",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      73.25,
      68.33
    ],
    "end": [
      73.25,
      72.14
    ]
  },
  {
    "uuid": "40554843-db3b-5b24-9082-b7dfcd9cff5b",
    "net": "V3V3",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      96.325,
      88.26
    ],
    "end": [
      98.05,
      88.25
    ]
  },
  {
    "uuid": "48da1848-7439-5f4e-abe1-c96a25eab269",
    "net": "V3V3",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      101.275,
      86.99
    ],
    "end": [
      101.3,
      85.95
    ]
  },
  {
    "uuid": "49e52442-122f-5a11-95ea-300d7baadf08",
    "net": "V3V3",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      94.825,
      85.3
    ],
    "end": [
      93.65,
      85.3
    ]
  },
  {
    "uuid": "7e60fa52-d65b-586b-85cf-61bb9f06c8d4",
    "net": "V3V3",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      101.275,
      89.53
    ],
    "end": [
      99.55,
      89.55
    ]
  },
  {
    "uuid": "df12d987-0695-5e2d-aea7-2f001b580dbc",
    "net": "V3V3",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      94.2,
      91.475
    ],
    "end": [
      93.0,
      91.45
    ]
  },
  {
    "uuid": "eaa13682-edca-5fc8-966d-c64796846d6e",
    "net": "V3V3",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      101.275,
      92.07
    ],
    "end": [
      99.55,
      92.05
    ]
  },
  {
    "uuid": "ee359495-8057-56fc-863f-1533f9199cb8",
    "net": "V3V3",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      96.325,
      90.8
    ],
    "end": [
      98.05,
      90.8
    ]
  },
  {
    "uuid": "3827d45d-5ca0-5193-b008-ed1ea2c49e97",
    "net": "V3V3",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      98.05,
      88.25
    ],
    "end": [
      98.05,
      88.25
    ]
  },
  {
    "uuid": "768900f7-61b3-5638-83d0-433b4f519274",
    "net": "V3V3",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      99.55,
      92.05
    ],
    "end": [
      99.55,
      92.05
    ]
  },
  {
    "uuid": "87f22d4e-579b-52b0-affa-b89de8298521",
    "net": "V3V3",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      99.55,
      89.55
    ],
    "end": [
      99.55,
      89.55
    ]
  },
  {
    "uuid": "925bfa64-4510-5617-a45c-97acf010df9f",
    "net": "V3V3",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      101.3,
      85.95
    ],
    "end": [
      101.3,
      85.95
    ]
  },
  {
    "uuid": "955494dc-876b-5451-8358-2ba3f91485dd",
    "net": "V3V3",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      98.05,
      90.8
    ],
    "end": [
      98.05,
      90.8
    ]
  },
  {
    "uuid": "00e539c0-3520-5ea8-b7a2-0cc1da981fa8",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      100.5,
      87.6
    ],
    "end": [
      101.275,
      88.26
    ]
  },
  {
    "uuid": "04e2faff-bcee-54bc-97a5-2e985e8e9181",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      103.6125,
      93.1
    ],
    "end": [
      104.35,
      93.075
    ]
  },
  {
    "uuid": "2915b62a-56de-52a0-bac5-d7e5b7b925f7",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      94.95,
      86.625
    ],
    "end": [
      95.92,
      86.625
    ]
  },
  {
    "uuid": "3a466c11-218a-5db7-9f60-5f81459aa248",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      96.325,
      86.99
    ],
    "end": [
      97.7,
      86.99
    ]
  },
  {
    "uuid": "54a82d69-7320-5f22-9896-9f2127c77f75",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      104.35,
      93.075
    ],
    "end": [
      104.7,
      93.425
    ]
  },
  {
    "uuid": "8ff5bc55-f709-5583-a09c-137823f68cb6",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      96.475,
      85.3
    ],
    "end": [
      96.325,
      86.99
    ]
  },
  {
    "uuid": "92d18180-25b9-50ef-9fbc-cbede237f117",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      97.7,
      86.99
    ],
    "end": [
      98.3,
      87.6
    ]
  },
  {
    "uuid": "a7fd9586-49d8-5f05-b706-35676940b005",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      98.3,
      87.6
    ],
    "end": [
      100.5,
      87.6
    ]
  },
  {
    "uuid": "b8eaa91f-c5a8-54e7-b8fc-6a5b14c48bb9",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      103.6125,
      93.1
    ],
    "end": [
      103.6125,
      91.45
    ]
  },
  {
    "uuid": "ed26cf25-5436-57d4-a419-ffb3a1e99d88",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      95.92,
      86.625
    ],
    "end": [
      96.4,
      86.145
    ]
  },
  {
    "uuid": "25e5d5e3-bd96-5975-88c5-b145b787c69a",
    "net": "/RESET_N",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      99.9,
      87.6
    ],
    "end": [
      99.9,
      87.6
    ]
  },
  {
    "uuid": "4357c6d0-59e1-5ebd-ac63-afe8eba55566",
    "net": "/RESET_N",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      94.95,
      86.625
    ],
    "end": [
      94.95,
      86.625
    ]
  },
  {
    "uuid": "7b03cfb9-4115-52e7-903c-5d2e2dde3a70",
    "net": "/RESET_N",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      104.7,
      93.425
    ],
    "end": [
      104.7,
      93.425
    ]
  },
  {
    "uuid": "8425400d-26a2-5a96-b32b-c0f82d99cef9",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      104.7,
      93.425
    ],
    "end": [
      102.95,
      93.425
    ]
  },
  {
    "uuid": "d539dac1-c702-51ca-b86c-0a130ace643f",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      100.2,
      90.675
    ],
    "end": [
      100.2,
      87.9
    ]
  },
  {
    "uuid": "e3fc0f0a-a2e3-5f6c-a2e9-e0860804edd3",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      100.2,
      87.9
    ],
    "end": [
      99.9,
      87.6
    ]
  },
  {
    "uuid": "f4de8b3d-5b49-571a-89cc-eefa25cf69b5",
    "net": "/RESET_N",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      102.95,
      93.425
    ],
    "end": [
      100.2,
      90.675
    ]
  },
  {
    "uuid": "f0edece0-5540-5933-bc91-5e082e197dbf",
    "net": "/BAD_FILTERED",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      70.775,
      70.87
    ],
    "end": [
      69.4,
      70.87
    ]
  },
  {
    "uuid": "9af28353-df68-5cd6-a4b1-c37ba6863432",
    "net": "/BAD_FILTERED",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      69.4,
      70.87
    ],
    "end": [
      69.4,
      70.87
    ]
  },
  {
    "uuid": "13416485-b3e0-55c9-9d7e-0076432735f2",
    "net": "/BAD_FILTERED",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      69.4,
      70.87
    ],
    "end": [
      69.4,
      72.0
    ]
  },
  {
    "uuid": "de181008-2e6b-5b0d-9caa-ecbf1b1b29ab",
    "net": "/BAD_FILTERED",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      69.4,
      72.0
    ],
    "end": [
      97.15,
      72.0
    ]
  },
  {
    "uuid": "23d60062-4e6e-53f7-ba52-c4213c12bcd6",
    "net": "/FAULT_LATCH",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      101.275,
      93.34
    ],
    "end": [
      100.7,
      93.875
    ]
  },
  {
    "uuid": "310edc00-8c6a-57e1-9f46-afde3c80114a",
    "net": "/FAULT_LATCH",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      101.275,
      93.34
    ],
    "end": [
      99.55,
      93.325
    ]
  },
  {
    "uuid": "d395acc0-21b0-5933-b584-fb71065615e5",
    "net": "/FAULT_LATCH",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      99.55,
      93.325
    ],
    "end": [
      96.55,
      96.325
    ]
  },
  {
    "uuid": "f8656bdf-91be-5ee8-af12-62cd8becda15",
    "net": "/FAULT_LATCH",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      100.7,
      93.875
    ],
    "end": [
      99.95,
      93.875
    ]
  },
  {
    "uuid": "881f6c9e-82e0-5896-886c-5ce5fc8bb020",
    "net": "/FAULT_LATCH",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      99.95,
      93.875
    ],
    "end": [
      99.95,
      93.875
    ]
  },
  {
    "uuid": "13e35107-5f5f-557b-9b18-f1bd72de6608",
    "net": "/FAULT_LATCH",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      99.95,
      93.875
    ],
    "end": [
      100.75,
      94.675
    ]
  },
  {
    "uuid": "c41979a4-790a-58f9-8a5d-31796de8a28c",
    "net": "/FAULT_LATCH",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      100.75,
      94.675
    ],
    "end": [
      108.25,
      94.675
    ]
  },
  {
    "uuid": "3644c657-f166-5ccc-94c1-e60b649aaf3b",
    "net": "/START_READY",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      103.6125,
      89.55
    ],
    "end": [
      102.95,
      89.55
    ]
  },
  {
    "uuid": "485e666a-5813-5b05-9ec9-18bc598d94b2",
    "net": "/START_READY",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      98.6,
      88.895
    ],
    "end": [
      97.95,
      89.53
    ]
  },
  {
    "uuid": "54a7fca0-b90b-5439-ab77-4b198323719d",
    "net": "/START_READY",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      97.95,
      89.53
    ],
    "end": [
      96.325,
      89.53
    ]
  },
  {
    "uuid": "a0e677e8-ae5e-50e5-90f1-7023aaff51cc",
    "net": "/START_READY",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      102.95,
      89.55
    ],
    "end": [
      102.6,
      89.2
    ]
  },
  {
    "uuid": "b7a3ee12-427b-5dad-98d4-aebdf2bcf5e6",
    "net": "/START_READY",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      96.325,
      89.53
    ],
    "end": [
      94.2,
      89.825
    ]
  },
  {
    "uuid": "d6d27c40-6e8f-503a-9772-719351465327",
    "net": "/START_READY",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      102.6,
      89.2
    ],
    "end": [
      102.6,
      88.895
    ]
  },
  {
    "uuid": "d81d9ac6-ee22-5741-934a-0c4854e8ec03",
    "net": "/START_READY",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      102.6,
      88.895
    ],
    "end": [
      98.6,
      88.895
    ]
  },
  {
    "uuid": "0bec0fbc-5c7e-5e67-aad8-a7654afa25d4",
    "net": "/ARMED",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      95.55,
      85.975
    ],
    "end": [
      95.55,
      83.325
    ]
  },
  {
    "uuid": "0fe059f2-fa92-539b-a4d1-4f144927f193",
    "net": "/ARMED",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      70.775,
      69.6
    ],
    "end": [
      69.4,
      69.6
    ]
  },
  {
    "uuid": "38b00231-3eb2-53d5-9cd0-a0282401bc9b",
    "net": "/ARMED",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      96.95,
      91.475
    ],
    "end": [
      97.5,
      91.475
    ]
  },
  {
    "uuid": "5c7cfa2d-bd12-5073-8f55-dedee66f4d50",
    "net": "/ARMED",
    "kind": "PCB_TRACK",
    "layer": "F.Cu",
    "start": [
      96.325,
      92.07
    ],
    "end": [
      96.95,
      91.475
    ]
  },
  {
    "uuid": "14ef2f03-5121-54b9-bcc9-2b06a81bb52a",
    "net": "/ARMED",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      97.5,
      91.475
    ],
    "end": [
      97.5,
      91.475
    ]
  },
  {
    "uuid": "27bddf4c-468a-5e70-8cfa-d2b06c2c3dca",
    "net": "/ARMED",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      69.4,
      69.6
    ],
    "end": [
      69.4,
      69.6
    ]
  },
  {
    "uuid": "f47cd627-1796-5508-9fba-48264fd46477",
    "net": "/ARMED",
    "kind": "PCB_VIA",
    "layer": "F.Cu",
    "start": [
      95.55,
      85.975
    ],
    "end": [
      95.55,
      85.975
    ]
  },
  {
    "uuid": "7f7b9162-c546-51fd-b702-592df0317ab4",
    "net": "/ARMED",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      70.1,
      69.6
    ],
    "end": [
      70.1,
      71.4
    ]
  },
  {
    "uuid": "9dc4dcb5-10c1-5f06-b429-3ac4e15e0fe2",
    "net": "/ARMED",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      97.5,
      91.475
    ],
    "end": [
      95.55,
      89.525
    ]
  },
  {
    "uuid": "ad7eebff-b532-550e-92a5-e5fde43d1275",
    "net": "/ARMED",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      95.55,
      89.525
    ],
    "end": [
      95.55,
      85.975
    ]
  },
  {
    "uuid": "c6e50262-0d3e-5d90-b25a-ada61cc208e8",
    "net": "/ARMED",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      70.1,
      71.4
    ],
    "end": [
      92.525,
      71.4
    ]
  },
  {
    "uuid": "dff162fd-18f7-56cf-a2fe-2d2ca9109763",
    "net": "/ARMED",
    "kind": "PCB_TRACK",
    "layer": "B.Cu",
    "start": [
      69.4,
      69.6
    ],
    "end": [
      70.1,
      69.6
    ]
  }
]
```
