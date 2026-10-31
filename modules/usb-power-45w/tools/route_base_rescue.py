#!/usr/bin/env python3
"""Explicit manually reviewed BASE rescue batches. No replay; one-connection suggestion only.
Uses unchanged shared plan/apply and the existing native writeback/audit.
"""
import sys
from pathlib import Path
import route_base_r3 as R
import route_base_r3_final as F
R.RES = R.MOD / 'research/routing-rescue'
R.V6 = (0.5, 0.3)
F.MARGIN = 0.005  # search margin only; native 0.2 mm rules remain authoritative
F.PATH_BUDGET = 12_000_000  # still exactly one connection, print-only

# Free the south-facing U13 pins: RESET_N's previous F crossbar enclosed them.
# Shift only MAIN_OK's under-body B branch west; reserve south corridor for parallel exits.
F.FINAL['RS01-free-u13'] = {
 'delete_poly': ['M3-reset/trk/0','M3-reset/trk/1','W2-u13-local/trk/9'],
 'delete': [('via','via/m3-0')],
 'vias': {'rs-reset':('RESET_N',(69.85,72.1))},
 'tracks': [
 ('MAIN_OK','B.Cu',0.2,('via','w-mok'),[(71.5,68.1),(68.0,68.1)],('tuu','24cbe904-d322-5401-b69c-2c3c61962c8e',(68.0,74.2))),
 ('RESET_N','F.Cu',0.2,('pad','U13','1'),[],('via','rs-reset')),
 ('RESET_N','B.Cu',0.2,('via','rs-reset'),[(70.425,71.525)],('via','m3-1')),
 ]}

# RS02: inspected southern F corridors between D11 and PD_BASE/PD_SENSE, then under U1.
F.FINAL['RS02-bad'] = {
 'vias': {'rs-bad-0': ('BAD_FILTERED', (73.15, 74.775)), 'rs-bad-1': ('BAD_FILTERED', (72.25, 78.325)), 'rs-bad-2': ('BAD_FILTERED', (79.6, 79.325)), 'rs-bad-3': ('BAD_FILTERED', (82.2, 81.925)), 'rs-bad-4': ('BAD_FILTERED', (89.4, 84.275)), 'rs-bad-5': ('BAD_FILTERED', (91.6, 86.475))},
 'tracks': [
 ('BAD_FILTERED', 'F.Cu', 0.2, ('pad', 'U13', '5'), [(74.9, 71.825), (73.15, 73.575)], ('via', 'rs-bad-0')),
 ('BAD_FILTERED', 'B.Cu', 0.2, ('via', 'rs-bad-0'), [(73.0, 74.775), (72.25, 75.525)], ('via', 'rs-bad-1')),
 ('BAD_FILTERED', 'F.Cu', 0.2, ('via', 'rs-bad-1'), [(78.6, 78.325)], ('via', 'rs-bad-2')),
 ('BAD_FILTERED', 'B.Cu', 0.2, ('via', 'rs-bad-2'), [], ('via', 'rs-bad-3')),
 ('BAD_FILTERED', 'F.Cu', 0.2, ('via', 'rs-bad-3'), [(87.05, 81.925)], ('via', 'rs-bad-4')),
 ('BAD_FILTERED', 'B.Cu', 0.2, ('via', 'rs-bad-4'), [], ('via', 'rs-bad-5')),
 ('BAD_FILTERED', 'F.Cu', 0.2, ('via', 'rs-bad-5'), [(91.95, 86.825)], ('pad', 'U15', '4')),
 ]}

# RS03: MAIN_OK takes the free B northern lane; removes the diagonal partition south of MHB2.
F.FINAL['RS03-mainok-north'] = {
 'delete': [('track','35971d08-2501-5bc0-a335-1ec1243e0867'),('track','928949d7-16c9-50a0-ab42-ba1533d06b6a'),
 ('track','be366444-63ed-5339-a3cf-73e6697602cd'),('track','e8b019e0-5cf9-5b1e-ac73-24af1141759d'),('track','f40be95d-a1e9-52eb-bf80-5e465c88bc2a'),
 ('via','b615f792-0aeb-56ce-b0dc-d998ee30c906'),('track','6e416d03-7382-5964-a361-3dce341c8346')],
 'vias': {'rs-mok-0':('MAIN_OK',(84.45,70.975))},
 'tracks': [
 ('MAIN_OK','B.Cu',0.2,('via','w-mok'),[(75.8,67.4),(75.8,63.5),(86.8,63.5),(86.8,68.625)],('via','rs-mok-0')),
 ('MAIN_OK','F.Cu',0.2,('via','rs-mok-0'),[],('pad','R63','2')),
 ]}

# RS04: NOT_FAULT occupies the released B diagonal band, then F beside U1, B under U9/U12.
F.FINAL['RS04-notfault'] = {
 'vias': {'rs-nf-0': ('NOT_FAULT', (72.45, 72.375)), 'rs-nf-1': ('NOT_FAULT', (85.35, 77.225)), 'rs-nf-2': ('NOT_FAULT', (88.75, 82.825)), 'rs-nf-3': ('NOT_FAULT', (99.0, 94.675))},
 'tracks': [
 ('NOT_FAULT', 'F.Cu', 0.2, ('pad', 'U13', '2'), [(71.1, 71.025)], ('via', 'rs-nf-0')),
 ('NOT_FAULT', 'B.Cu', 0.2, ('via', 'rs-nf-0'), [(79.35, 72.375), (84.2, 77.225)], ('via', 'rs-nf-1')),
 ('NOT_FAULT', 'F.Cu', 0.2, ('via', 'rs-nf-1'), [(88.75, 80.625)], ('via', 'rs-nf-2')),
 ('NOT_FAULT', 'B.Cu', 0.2, ('via', 'rs-nf-2'), [(88.75, 87.375), (91.95, 90.575), (91.95, 92.525), (94.1, 94.675)], ('via', 'rs-nf-3')),
 ('NOT_FAULT', 'F.Cu', 0.2, ('via', 'rs-nf-3'), [(99.05, 94.625)], ('pad', 'U12', '8')),
 ]}

# RS05: RUN local F connection, west of U14's pin 8 and between the R4/R28 pads.
F.FINAL['RS05-run-local'] = {'tracks': [
 ('RUN', 'F.Cu', 0.2, ('pad', 'U14', '9'), [(67.3, 71.525), (66.35, 72.475), (66.35, 75.175), (67.3, 76.125), (67.3, 79.775)], ('pad', 'Q10', '1')),
]}

# RS06: ANY_BAD uses the open west/south B perimeter, outside the input heat spread.
F.FINAL['RS06-anybad'] = {
 'vias': {'rs-any-0': ('ANY_BAD', (58.85, 71.075)), 'rs-any-1': ('ANY_BAD', (87.1, 95.375))},
 'tracks': [
 ('ANY_BAD', 'F.Cu', 0.2, ('pad', 'U14', '6'), [(62.3, 71.075)], ('via', 'rs-any-0')),
 ('ANY_BAD', 'B.Cu', 0.2, ('via', 'rs-any-0'), [(54.55, 75.375), (54.55, 88.875), (58.8, 93.125), (63.7, 93.125), (65.1, 94.525), (65.1, 94.725), (65.5, 95.125), (86.85, 95.125)], ('via', 'rs-any-1')),
 ('ANY_BAD', 'F.Cu', 0.2, ('via', 'rs-any-1'), [(89.75, 95.375)], ('pad', 'R72', '1')),
 ]}

# RS07: move MAIN_OK's branch to F beneath U14, releasing its B-side enclosure around NOT_RUN.
F.FINAL['RS07-mainok-under-u14'] = {
 'delete_poly':['RS01-free-u13/trk/0'],
 'vias':{'rs-mok-u14a':('MAIN_OK',(65.2,74.2)), 'rs-mok-u14b':('MAIN_OK',(65.2,66.5))},
 'tracks':[
 ('MAIN_OK','F.Cu',.2,('via','rs-mok-u14a'),[],('via','rs-mok-u14b')),
 ('MAIN_OK','B.Cu',.2,('via','rs-mok-u14b'),[(71.5,66.5)],('via','w-mok')),
 ]}

# RS08: NOT_RUN uses a second northern F lane, y63.375 exactly 1 mm copper-edge.
# Optimistic raster proposal was corrected manually from y63.325 before native testing.
F.FINAL['RS08-notrun'] = {
 'vias': {'rs-nr-0': ('NOT_RUN', (68.9, 72.175)), 'rs-nr-1': ('NOT_RUN', (78.25, 64.075)), 'rs-nr-2': ('NOT_RUN', (92.75, 70.025)), 'rs-nr-3': ('NOT_RUN', (114.0, 97.925))},
 'tracks': [
 ('NOT_RUN', 'F.Cu', 0.2, ('pad', 'U14', '8'), [(68.35, 72.175)], ('via', 'rs-nr-0')),
 ('NOT_RUN', 'B.Cu', 0.2, ('via', 'rs-nr-0'), [(70.9, 70.175), (73.6, 70.175), (78.25, 65.525)], ('via', 'rs-nr-1')),
 ('NOT_RUN', 'F.Cu', 0.2, ('via', 'rs-nr-1'), [(78.95, 63.375), (86.10, 63.375)], ('via', 'rs-nr-2')),
 ('NOT_RUN', 'B.Cu', 0.2, ('via', 'rs-nr-2'), [(92.75, 71.275), (99.05, 77.575), (99.1, 77.575), (99.6, 78.075), (99.6, 78.875), (100.6, 79.875), (101.35, 79.875), (102.25, 80.775), (102.25, 82.475), (104.0, 84.225), (104.0, 84.475), (105.25, 85.725), (109.5, 85.725), (112.2, 88.425), (112.2, 96.025)], ('via', 'rs-nr-3')),
 ('NOT_RUN', 'F.Cu', 0.2, ('via', 'rs-nr-3'), [(114.0, 98.625), (116.15, 100.775), (119.85, 100.775), (121.65, 98.875), (124.2, 98.875)], ('pad', 'Q5', '1')),
 ]}

# RS09: P12_OK test point to XB2, B north of J2/MHB3, between XB2 columns.
F.FINAL['RS09-p12-east'] = {
 'vias': {'rs-p12e-0': ('P12_OK', (90.4, 70.075))},
 'tracks': [
 ('P12_OK', 'F.Cu', 0.2, ('pad', 'TP12', '1'), [(88.75, 71.725)], ('via', 'rs-p12e-0')),
 ('P12_OK', 'B.Cu', 0.2, ('via', 'rs-p12e-0'), [(96.7, 63.775), (129.65, 63.775), (132.3, 66.425), (132.3, 68.625)], ('pad', 'XB2', '4')),
 ]}

# RS10: shift AI-placed Q8 0.2 mm east to open a F crossover beside the VPD dogbone.
# Preserve its collector via and B LED trace; only its short F lead is replaced.
F.FINAL['RS10-q8-gap'] = {
 'moves':[('Q8',(83.9,89.5),180)],
 'delete_poly':['L2-d17-u11/trk/0'],
 'tracks': [('Net-(D17-K)','F.Cu',.2,('pad','Q8','3'),[(82.95,90.375)],('via','l2-k'))],
}

# RS11: move only U9's low-current VPD crossover via, not input/core power copper.
# Its original 0.6-mm via closed the F slot beside Q8; retain 0.25-mm supply lead.
F.FINAL['RS11-vpd-crossover'] = {
 'delete_poly':['M2-vpd-u9/trk/1','M2-vpd-u9/trk/2'],
 'delete':[('via','via/m2-1')],
 'vias':{'rs-vpd-low':('VPD',(81.05,89.525))},
 'tracks':[
 ('VPD','B.Cu',.25,('via','m2-0'),[(86.35,89.375),(81.2,89.375)],('via','rs-vpd-low')),
 ('VPD','F.Cu',.25,('via','rs-vpd-low'),[],('via','m2-2')),
 ]}

# RS13: temporary controlled rip of this rescue's NOT_FAULT diagonal only.
# It fences the single XB1-west crossing on F; prioritize the three multi-terminal status nets.
F.FINAL['RS13-release-nf'] = {
 'delete_poly':['RS04-notfault/trk/0','RS04-notfault/trk/1','RS04-notfault/trk/2','RS04-notfault/trk/3','RS04-notfault/trk/4'],
 'delete':[('via','via/rs-nf-0'),('via','via/rs-nf-1'),('via','via/rs-nf-2'),('via','via/rs-nf-3')],
}

# RS14: P12_OK through the Q8/U1 slots, then F just west of XB1 after releasing NF.
F.FINAL['RS14-p12-led'] = {
 'vias': {'rs-p12q-0': ('P12_OK', (84.05, 92.375)), 'rs-p12q-1': ('P12_OK', (81.85, 90.175)), 'rs-p12q-2': ('P12_OK', (82.05, 86.325)), 'rs-p12q-3': ('P12_OK', (82.85, 84.625)), 'rs-p12q-4': ('P12_OK', (87.35, 84.325)), 'rs-p12q-5': ('P12_OK', (88.6, 81.275))},
 'tracks': [
 ('P12_OK', 'F.Cu', 0.2, ('pad', 'Q7', '1'), [], ('via', 'rs-p12q-0')),
 ('P12_OK', 'B.Cu', 0.2, ('via', 'rs-p12q-0'), [], ('via', 'rs-p12q-1')),
 ('P12_OK', 'F.Cu', 0.2, ('via', 'rs-p12q-1'), [(81.85, 87.875), (82.05, 87.675)], ('via', 'rs-p12q-2')),
 ('P12_OK', 'B.Cu', 0.2, ('via', 'rs-p12q-2'), [(82.85, 85.525)], ('via', 'rs-p12q-3')),
 ('P12_OK', 'F.Cu', 0.2, ('via', 'rs-p12q-3'), [(82.95, 84.725), (86.95, 84.725)], ('via', 'rs-p12q-4')),
 ('P12_OK', 'B.Cu', 0.2, ('via', 'rs-p12q-4'), [(88.6, 83.075)], ('via', 'rs-p12q-5')),
 ('P12_OK', 'F.Cu', 0.2, ('via', 'rs-p12q-5'), [(88.6, 75.825)], ('pad', 'TP12', '1')),
 ]}

# RS15: coordinated west logic placement and explicitly bounded control rip.
F.FINAL['RS15-corridor-fit'] = {'moves': [('U14', (64.8, 69.2), 90),
           ('U13', (73.25, 69.6), 0),
           ('C53', (60.99, 64.1), 180),
           ('C54', (77.7, 64.1), 180),
           ('R63', (84.3, 71.9), 0),
           ('R27', (71.45, 76.9), 0),
           ('R28', (78.6, 73.2), 180),
           ('TP5', (87.05, 69.5), 90),
           ('TP8', (68.2, 74.1), 0),
           ('TP4', (66.0, 64.35), 0),
           ('R83', (86.75, 64.1), 0)],
 'delete': [('via', '0098a79c-15d7-5831-8337-717b15153419'),
            ('via', '013f5a8d-9fba-527c-8b1e-673453604f16'),
            ('track', '01fcca09-67dc-547d-b03e-b063bc582e60'),
            ('track', '0208d8a2-d26a-5e5f-bc34-d46e3fa8afbb'),
            ('track', '02b804c3-c565-5737-840f-85151de72d3b'),
            ('track', '02d57d03-e1d4-57b9-ad53-0bcfaba6d284'),
            ('track', '041b272e-71ca-563f-b7fb-de84ef812e1d'),
            ('track', '0498249b-d299-5f13-b7a5-3532ec2c88de'),
            ('track', '067fdc5e-26e8-5327-9288-6518f04f0396'),
            ('track', '0782526e-b102-5726-a1ea-a6329466e1f0'),
            ('track', '07ea8e05-9e93-54db-8092-9048ddc025ed'),
            ('via', '0b93e4e3-66c4-502d-a609-97a5e132f21a'),
            ('track', '0e5ce039-fe78-5ca1-9727-47e31b627d65'),
            ('track', '0ec4a592-e0b1-5bb9-9210-4aef73d45ae9'),
            ('track', '0f22a35a-1069-5b93-9491-be2284648943'),
            ('track', '0f59be83-73eb-5961-a1f2-d0cf8a71781b'),
            ('track', '0fb927e6-1534-5865-b35c-1b50fe8deb4b'),
            ('track', '1023827d-401c-5525-8473-0222c8bd0d00'),
            ('track', '1097242f-2731-5459-808d-1c107e1f0af8'),
            ('track', '13ea0d03-5a08-56b5-bf59-66c466435e58'),
            ('track', '148d9aa7-5b7c-53c8-962e-0ce0e5d8fcc9'),
            ('track', '149a085d-b505-5362-962b-bf044583f4fa'),
            ('via', '14dd97d9-87c0-5acc-98db-8be91a430ede'),
            ('track', '15019b51-bef1-5620-b8b1-438106f79c27'),
            ('track', '15d71715-6022-5d38-9d38-f1c563bcdf77'),
            ('track', '15f02199-0aa2-56ae-8555-1ac818dc5976'),
            ('track', '176a2ee7-9fae-5c4d-83d2-e2cbfe8c1245'),
            ('track', '1798800d-5637-5e47-9c66-a99ba47341ca'),
            ('track', '17ac957d-9a26-5c66-b856-2e91c1675fb5'),
            ('track', '186253b5-d944-54f8-8fc0-820d1a9d149e'),
            ('track', '18c25d36-4803-5d27-8f5f-683d0d2176cb'),
            ('track', '198fd2eb-23a4-5d9a-afc3-6404f01cf36a'),
            ('track', '1b05365b-8eba-562a-86db-5d863eabf995'),
            ('track', '1bc88e39-5281-55fd-8459-a2151001421f'),
            ('track', '1c4b2dd8-0536-56c3-99ea-dc19ea06289b'),
            ('track', '1cc374b5-1f0c-5a4a-8806-c4df0f9b9271'),
            ('track', '20fb9fea-1a14-54fe-9d8f-222828dcbe51'),
            ('track', '22447226-78e8-51fb-9165-f585df05f4a9'),
            ('track', '244669c0-6c32-50a8-8dc6-9df291e1a3fb'),
            ('track', '24cbe904-d322-5401-b69c-2c3c61962c8e'),
            ('via', '279f8369-f90d-5274-8f6b-d7d33521255c'),
            ('track', '292d538f-6f24-5007-b332-ae5902e7d994'),
            ('track', '296fb891-a08b-500a-8e9d-1fe06688a1ba'),
            ('track', '2b1e89bf-9e1b-566a-8de0-d06815b7b11a'),
            ('track', '2b665015-39e2-5b57-b6bb-8861b557c76a'),
            ('track', '2cd8de1f-2dcc-50a9-b1d6-f8ac1932a52f'),
            ('track', '2ecdb396-2cdd-56e7-b837-7987bfafab91'),
            ('track', '30794f5f-1be0-5fed-8f71-72762598801d'),
            ('track', '307c2544-8493-5339-8681-9cdcc6b522f7'),
            ('track', '324f7184-e536-5e2a-9100-e023605cc6de'),
            ('via', '382d95d1-c6d5-520f-8224-b9ec27e26f29'),
            ('track', '386f2755-b38e-5e0d-bd3f-9d661d145e03'),
            ('track', '3a077d7e-ea03-51ee-80fc-5b32cceee286'),
            ('track', '3aa0d569-5b78-54c9-ab4b-9b6734e45730'),
            ('track', '3ad892db-8d3f-54b3-9d63-b60de432000f'),
            ('track', '3baca1a3-3072-5201-9772-1fe4f1f5e7c3'),
            ('track', '3d506839-a557-5cd7-940d-a65af78bd299'),
            ('track', '3e38dee2-0b68-5b8b-9e4a-8bbd1764522c'),
            ('track', '3e4418f5-ea71-5a95-9961-0f1b967b71b6'),
            ('track', '40b2dcd4-7dc3-5c93-b64f-78f9b581f9d5'),
            ('via', '411bdc7d-322c-5cfb-8c32-d57ae3756703'),
            ('track', '42e193b0-def2-5b16-a61b-fcc67e977a4b'),
            ('track', '459acb46-6255-5e5f-a5ea-117ee95a4d6a'),
            ('track', '45e53109-a19a-55e8-bc23-9fa9ec3f8c9b'),
            ('via', '47c13065-2a52-5f26-8189-6710f779fe1b'),
            ('track', '49dfc7bf-2d5a-5175-ad85-4886c4b45b00'),
            ('track', '4ad0a3c5-2aad-5e08-8545-affd83a0870f'),
            ('track', '4ce46370-82a1-5578-99b2-b5dd778db4c3'),
            ('track', '50956281-8141-5329-8c79-6189925365e2'),
            ('track', '539006d8-2d98-5644-9579-653c8226250a'),
            ('track', '53e82135-4a34-5c5c-83d8-8cac6d754acb'),
            ('track', '55beb963-c5de-50bf-8469-45358612c6cb'),
            ('track', '561bee04-2224-595d-bc2b-582060319121'),
            ('track', '57ba1608-f391-5c6f-9abf-6e95a93a3db4'),
            ('track', '57e1310a-797c-5fc2-9324-a4b9997a112c'),
            ('track', '588305a2-80a6-5e57-917e-2d43a4829513'),
            ('track', '5a100674-7698-5b29-abe8-effac129caf6'),
            ('track', '5a7f6216-4df3-5d37-b49d-872fc0fbe5ec'),
            ('track', '5b50cdbe-2452-5fb8-a4e7-5234145eecfd'),
            ('via', '5cae2af8-3e1c-5961-b9bc-0d49c1d65cf0'),
            ('track', '5cb76bc2-13bd-5fcd-afdd-483d8941e1aa'),
            ('track', '5ceb3a72-9424-5356-975e-5e98305e6d72'),
            ('via', '5d80c7b8-029a-5809-82b8-888eb64a3d66'),
            ('track', '609b1e2b-249f-555f-993d-7640bfa56eed'),
            ('track', '61734349-1e54-5730-a774-dafdfdd4e91a'),
            ('track', '619003a8-7b0e-5d29-9f77-a0bb64fcad57'),
            ('via', '6482765e-ff17-5f9a-938a-96863e7dea3b'),
            ('track', '66330cd6-7573-5fbd-9c4d-1db65634cd5a'),
            ('track', '665ce8bc-544b-5f8b-af5a-e4ee3dc04836'),
            ('track', '6929bd85-f242-5cdb-a205-4bf180f83379'),
            ('track', '6e12e243-cfb6-54e9-a7a3-01abe32503e1'),
            ('track', '704c0365-a4fd-5463-9490-d50e53a65fcb'),
            ('track', '72352971-a7b2-59f2-bc8f-42aa5addb976'),
            ('via', '72c95f97-535d-54e1-8a5a-4b0db1bc8eef'),
            ('track', '7594c4ed-9122-5375-8d24-7946588bf310'),
            ('track', '79bf8a49-d417-5eeb-b7f3-3386ac4e858c'),
            ('track', '7e00b84c-0a72-514d-9553-ad097bbdb8dc'),
            ('track', '7e29c8b1-4a94-528d-8d4c-af04904c0677'),
            ('track', '7f415324-abff-5334-9d84-3ce817ae27a8'),
            ('track', '7f65dd7e-6fc0-52f4-b9cf-d508314d559d'),
            ('track', '80ebe4bc-bd39-5846-bf5f-88caa6688ff0'),
            ('track', '8122475f-a3ab-5c13-8b6c-0c4e79ddaca7'),
            ('track', '83f54efb-f0e9-5407-b63d-7af0ffcc5a7f'),
            ('track', '857bde0e-4996-5a3d-aa7d-7f74bfee8bc7'),
            ('track', '8667e8fd-9a2e-5de4-8191-229ddb549c22'),
            ('track', '8784daca-ae8a-5eeb-8a9f-e13a40a7b8bc'),
            ('track', '88dea614-5f5e-569a-9b49-bf687fdf64af'),
            ('track', '89a35725-bcc2-5ea8-a000-73808a9e76a7'),
            ('via', '89bae04a-9e64-5564-943c-75da1e052345'),
            ('track', '8ba37927-253a-57be-b45a-94cbe5901474'),
            ('track', '8bc36327-12b2-5722-ac0a-e2f540c20d4c'),
            ('via', '8c2ab285-a81b-5c5b-bb3f-67622989c75c'),
            ('track', '8d140e99-f480-5cb2-b9ef-1f354a5f7389'),
            ('via', '8ff58af4-72df-5e06-a863-e1125b70c1c3'),
            ('track', '904f7a4f-4128-589a-aa0a-4aa86171ec98'),
            ('track', '9054739a-40f1-51be-8806-a4ddd4307998'),
            ('track', '91d15e91-fee2-5c03-ba6e-ebfc4ecd71e3'),
            ('track', '91e2810c-92f4-59e6-b254-77c8f72d5745'),
            ('via', '92330946-732e-5399-8307-612fc1d0c7b5'),
            ('track', '927e41ae-3283-5b9d-9ce4-fcc886f75be0'),
            ('track', '952dfd11-07a1-5524-b9aa-6b948245ecfb'),
            ('via', '96c2a8e2-63ae-5f43-b6e7-7a1ce27535b6'),
            ('track', '9750ddd4-3ce7-56c0-8f01-49efbccdf7df'),
            ('track', '984eb092-6f89-5a23-8fc4-dbd7d8ba81d4'),
            ('track', '9adba1d6-b1a1-5afd-bad6-53c724b48581'),
            ('via', '9b9b627c-47a7-58b3-9741-6b5140a92492'),
            ('via', '9c008ae4-f726-5b55-8866-fc6cd079a238'),
            ('track', 'a0c4c4be-1163-5e66-a3e5-20af24b409a3'),
            ('track', 'a11748a2-8570-58de-a9ef-1c6492d169da'),
            ('track', 'a11ae0f6-1d7a-5952-ab7f-6f96689a46d6'),
            ('track', 'a1751855-8b3b-5941-99d8-d4e9a01f821a'),
            ('track', 'a483775f-23c9-5a02-8241-d20bcadd8077'),
            ('via', 'a4c4a817-ec3f-5115-a370-54407e127bb5'),
            ('track', 'a69247a3-259d-54f6-a519-2b177e615a58'),
            ('track', 'a6f36395-d6d6-592e-82ca-ae77113f1adc'),
            ('track', 'a7d373d6-8c72-51bf-8b96-65890c2f7fef'),
            ('track', 'a7e71496-1e92-5b7a-96b6-025385d0437d'),
            ('track', 'a8795ed1-221a-5c12-89d5-d4a5d61a47c1'),
            ('via', 'ab49fed5-e642-586d-a97e-03d4a57d2f3e'),
            ('via', 'ac00bf32-30ef-59fa-9a85-11650769f5a6'),
            ('track', 'acaf8da1-a6e0-5d1c-b3f4-acf4db9f5cb2'),
            ('track', 'aeb32509-a538-5297-8d9b-761bb0b0d01e'),
            ('via', 'b0c684f5-c42d-57d1-bbe6-f2d09d67f6bd'),
            ('track', 'b3655801-4fa1-5c2f-b472-3918261a4eec'),
            ('track', 'b3f2d191-4eec-5418-b918-92ac996fb4d7'),
            ('track', 'b5112635-3378-5569-b760-3b70ef874fbb'),
            ('via', 'b65ff0ae-84f1-5a79-a8f2-faaa46f36393'),
            ('track', 'b969a265-c2ea-5ad6-aad8-2d1328929e0d'),
            ('track', 'bab83f19-f862-5f98-88b2-a455e54f979b'),
            ('track', 'bc45aec4-6507-56ba-9e55-af6f5c437d9d'),
            ('track', 'bcc5807d-bf72-5d98-b81a-8ff99ca040bb'),
            ('track', 'bd91a8ad-2893-52ed-995b-fc83f9153d39'),
            ('track', 'beedbafc-7430-555a-8a0b-364c50eaff22'),
            ('via', 'bfd5765a-3a33-5974-a0d5-efd2098dc89a'),
            ('track', 'c09ca0c2-552a-5c09-b1c1-e2fdcec12480'),
            ('track', 'c118729d-3b4c-5c1c-98fe-a363405e8265'),
            ('track', 'c2b6174e-ea5e-5f92-b940-cc037db195d8'),
            ('track', 'c40d01f8-559e-5b8e-9930-1432d8bb2be1'),
            ('track', 'c5961d26-32ff-55b4-b1a8-3058a1e88ddd'),
            ('via', 'c63199ca-693f-585b-a65e-a7d3ca1c7e55'),
            ('track', 'c68312e2-d3ad-5ea4-aee1-aae9ce7aeda1'),
            ('track', 'c6bf0bdb-ddeb-55cc-a37a-745d6bc4937f'),
            ('via', 'c8e0a640-c5b0-5756-bfe8-a892c82eb716'),
            ('track', 'ca56868c-8397-55d5-8d5a-77fb9f2e7015'),
            ('track', 'cb23c350-a538-52e4-b3e2-f58c31979d1d'),
            ('track', 'cc21c1d3-d8e0-57ed-ba36-e3a6eacef5d7'),
            ('track', 'ccbb3337-f2ae-598c-8ac5-27441995d976'),
            ('track', 'cd3cfa58-485f-5bd6-b161-d7cbc6e349c4'),
            ('via', 'cfd994de-1dd3-5b3c-8314-20b15843c891'),
            ('track', 'd00ce775-a93d-5e55-80cb-19e71887367f'),
            ('track', 'd103cf3d-278c-5a03-b5ed-4032623b7c31'),
            ('track', 'd1869f0b-0393-5e7d-a1b6-b35b00c402e2'),
            ('track', 'd1b23141-c955-5d77-bcbd-8a311ce25e80'),
            ('track', 'd24a0ec1-db88-59ac-bbac-fade7b9bb975'),
            ('track', 'd24e6336-4f7e-554e-b2ec-a3e4fa837cab'),
            ('via', 'd4a5b9e6-a9cb-5a48-9efb-4436eea3164c'),
            ('via', 'd4e1c8f2-5ba8-57c1-b3aa-8f95390bce17'),
            ('track', 'd50c4c02-caab-5934-aacc-09dbde1c8c1c'),
            ('track', 'd53c7c86-bf9b-5082-9e3c-15ce6782e834'),
            ('track', 'd5900c17-2fee-5fbf-b918-33473be3181c'),
            ('track', 'd5e59fc2-565b-54ef-a1f3-537baa00679a'),
            ('track', 'd642bf3b-b5fa-5f4c-84eb-fb2a6f49543c'),
            ('track', 'd6719fc6-e7c6-5f1e-8b25-09578f28c0e9'),
            ('via', 'd694e144-6d81-580d-b0fe-ab637e011896'),
            ('track', 'daa84e2f-3ad6-5553-9649-3c624a311a40'),
            ('track', 'dca04cea-cbb3-5cfa-a6c9-c335623c4da3'),
            ('via', 'dd71d1b6-bdd2-58bc-8397-e0e11745cc87'),
            ('via', 'e1b45d38-17f1-5ecb-aa49-60eace471b3d'),
            ('via', 'e2efc25f-55d0-5774-af4b-0ff8343390df'),
            ('track', 'e2ff2410-b668-5e92-a981-650b35581721'),
            ('track', 'e36b824a-999d-53c8-ad77-f02061792294'),
            ('track', 'e3746eac-5ccf-5d58-8955-f9b86c43c58c'),
            ('via', 'e4f557db-4bf6-5f7a-be9d-a759292b626a'),
            ('track', 'e7f1b58d-9e60-53b2-8d76-e25921664cf1'),
            ('track', 'e8079bb8-54f0-56dc-b35f-92dec124ec46'),
            ('track', 'e8866b4b-fd6f-5a8c-b744-5614736cce2f'),
            ('via', 'e8b9521d-74c4-598c-b93c-53a46ce0f47a'),
            ('via', 'ef0cc9a3-a422-5f17-9592-4d346c68619b'),
            ('via', 'ef673659-90dc-5453-befd-a0792b36e49b'),
            ('track', 'ef7a8b77-be10-5868-bad9-b2d7f33d650a'),
            ('via', 'ef846aeb-4680-5a83-8260-1c20a088dbe8'),
            ('track', 'f0a7caec-dc37-5972-a62a-8f3b606b16de'),
            ('track', 'f0bfebf6-dbf9-5e27-91de-7f65a455fed8'),
            ('via', 'f15c5a73-211c-5b8d-9315-e2d0de8730e9'),
            ('via', 'f4d028c9-c134-5103-809b-3462c9422eef'),
            ('track', 'f5fbb17a-b454-5881-b1a7-702caaf2519e'),
            ('track', 'f7e9fd10-9eb2-5913-877e-ec6229dfea14'),
            ('track', 'fae15f7d-fac1-540d-af5e-6cdff69957ea'),
            ('via', 'fbccdfcd-38f1-55b5-822d-fcffcf94c183'),
            ('via', 'fc4cb83e-050d-52aa-b14a-242857d62f3d'),
            ('track', 'ffd6cd52-0579-5908-8d52-b21531b04735')],
 'vias': {'rs15-c53g': ('GND', (59.4, 64.1)),
          'rs15-c53v': ('V3V3', (62.6, 64.1)),
          'rs15-c54g': ('GND', (75.8, 64.1)),
          'rs15-c54v': ('V3V3', (79.2, 64.1)),
          'rs15-u14g': ('GND', (69.0, 73.0)),
          'rs15-u13g': ('GND', (70.775, 74.3)),
          'rs15-r63v': ('V3V3', (85.4, 70.6)),
          'rs15-r27g': ('GND', (72.9, 75.6)),
          'rs15-r27b': ('PD_BASE', (69.4, 78.2)),
          'rs15-tp8g': ('GND', (68.2, 75.2))},
 'tracks': [('GND', 'F.Cu', 0.25, ('pad', 'C53', '2'), [], ('via', 'rs15-c53g')),
            ('V3V3', 'F.Cu', 0.25, ('pad', 'C53', '1'), [], ('via', 'rs15-c53v')),
            ('V3V3', 'F.Cu', 0.25, ('pad', 'U14', '14'), [], ('pad', 'C53', '1')),
            ('GND', 'F.Cu', 0.25, ('pad', 'C54', '2'), [], ('via', 'rs15-c54g')),
            ('V3V3', 'F.Cu', 0.25, ('pad', 'C54', '1'), [], ('via', 'rs15-c54v')),
            ('V3V3', 'F.Cu', 0.25, ('pad', 'U13', '14'), [(76.3, 65.2), (78.475, 65.2)], ('pad', 'C54', '1')),
            ('GND', 'F.Cu', 0.25, ('pad', 'U14', '7'), [], ('via', 'rs15-u14g')),
            ('GND', 'F.Cu', 0.25, ('pad', 'U13', '7'), [], ('via', 'rs15-u13g')),
            ('V3V3', 'F.Cu', 0.25, ('pad', 'R63', '1'), [(83.475, 71.1), (85.4, 71.1)], ('via', 'rs15-r63v')),
            ('GND', 'F.Cu', 0.25, ('pad', 'R27', '2'), [], ('via', 'rs15-r27g')),
            ('PD_BASE', 'F.Cu', 0.2, ('pad', 'R27', '1'), [], ('via', 'rs15-r27b')),
            ('PD_BASE', 'B.Cu', 0.2, ('via', 'rs15-r27b'), [], ('tuu', '19f350e0-401f-5a43-8d81-1b228de7d20f', (72.9, 78.2))),
            ('GND', 'F.Cu', 0.25, ('pad', 'TP8', '1'), [], ('via', 'rs15-tp8g'))]}

# Fit correction: preserve unchanged angles, shift only adjacent R4/TP7 to retain courtyards.
_rs15 = F.FINAL['RS15-corridor-fit']
_rs15['moves'] = [(ref, (70.95,76.9) if ref=='R27' else at, None if ref in ('R63','R27','R28','TP5','TP4','TP8') else rot) for ref,at,rot in _rs15['moves']]
_rs15['moves'] += [('R4',(67.0,76.65),None),('TP7',(59.0,73.2),None)]
_rs15['delete'] += [('track','52906da5-482a-5629-899b-e0201b60b17a'),('track','9824d325-129c-5fb2-8cf6-2958201cf246')]
_rs15['vias']['rs15-r27g'] = ('GND',(72.1,75.6))
_rs15['tracks'] += [
 ('EF_OV','F.Cu',.25,('pad','R4','2'),[],('tuu','dc01f248-9575-5002-bcbc-94a3c7e5cf2a',(66.575,76.65))),
 ('EF_IMON','F.Cu',.25,('pad','TP7','1'),[],('tuu','533b03d6-cdfc-5a88-917e-cf4ad511730e',(60.5,73.4))),
]

# TP3 moves north out of the R4 courtyard. Defer R27 PD_BASE reconnection to its own small batch.
_rs15['moves'] += [('TP3',(64.75,74.8),None)]
_rs15['vias'].pop('rs15-r27b')
_rs15['tracks'] = [t for t in _rs15['tracks'] if t[0]!='PD_BASE']
_rs15['tracks'] += [('EF_IN','F.Cu',.25,('pad','TP3','1'),[],('tuu','35ebccbb-9700-5000-ac75-a0049a7920b0',(64.75,76.4)))]

# RS16: local RUN chains under the logic bodies, local PD_BASE, and C54 via mask clearance.
F.FINAL['RS16-locals'] = {
 'delete_poly':['RS15-corridor-fit/trk/4'], 'delete':[('via','via/rs15-c54v')],
 'vias':{'rs16-c54v':('V3V3',(79.4,64.1)), 'rs16-run':('RUN',(61.9,68.2)), 'rs16-pdb':('PD_BASE',(69.4,78.2))},
 'tracks':[
 ('V3V3','F.Cu',.25,('pad','C54','1'),[],('via','rs16-c54v')),
 ('MAIN_OK','F.Cu',.2,('pad','U5','15'),[],('pad','U5','16')),
 ('RUN','F.Cu',.2,('pad','U14','13'),[],('pad','U14','12')),
 ('RUN','F.Cu',.2,('pad','U14','10'),[],('pad','U14','9')),
 ('RUN','F.Cu',.2,('pad','U14','12'),[(63.53,68.2),(66.07,68.2)],('pad','U14','10')),
 ('RUN','F.Cu',.2,('pad','U14','9'),[(67.34,68.33)],('pad','U13','3')),
 ('RUN','F.Cu',.2,('pad','U13','3'),[(73.25,68.33),(73.25,72.14)],('pad','U13','9')),
 ('RUN','F.Cu',.2,('pad','U14','13'),[],('via','rs16-run')),
 ('RUN','B.Cu',.2,('via','rs16-run'),[],('vuu','de48054f-616b-557d-a865-073dfe75f0d3')),
 ('PD_BASE','F.Cu',.2,('pad','R27','1'),[],('via','rs16-pdb')),
 ('PD_BASE','B.Cu',.2,('via','rs16-pdb'),[],('tuu','19f350e0-401f-5a43-8d81-1b228de7d20f',(72.9,78.2))),
 ]}

# RS17: coherent corridor clearance. Move logic GND vias under their IC bodies;
# move PD_BASE/VPD_U1 auxiliary crossovers BELOW the control bus. Retain 0.3-mm VPD_U1 feed.
F.FINAL['RS17-clear-bus'] = {
 'delete_poly':['RS15-corridor-fit/trk/6','RS15-corridor-fit/trk/7'],
 'delete':[('via','via/rs15-u14g'),('via','via/rs15-u13g'),
 ('via','1d6917a2-2a11-55fa-bf41-c24c78ec7cf1'),('track','adf7ea1c-43b6-5d00-b05e-93b01aeb7c47'),('track','bc143d5b-308b-510a-afed-33e80b2ea2fe'),('track','b7bb66ad-2bae-5670-9e3b-3776c1758ea4'),
 ('via','e70af8e1-9afd-590e-8ff8-080fe45f0896'),('track','19f350e0-401f-5a43-8d81-1b228de7d20f'),('track','22a7b159-d11d-5242-9c9d-3fbff72a1850'),('track','e13d87a6-e891-5131-b357-3e18f6b74ffa'),('track','735456e5-63c3-520f-b77d-5f843fe82432')],
 'vias':{'rs17-u14g':('GND',(68.61,70.0)), 'rs17-u13g':('GND',(72.2,71.0)), 'rs17-pdb':('PD_BASE',(76.85,78.05))},
 'tracks':[
 ('GND','F.Cu',.25,('pad','U14','7'),[],('via','rs17-u14g')),
 ('GND','F.Cu',.25,('pad','U13','7'),[(72.2,73.41)],('via','rs17-u13g')),
 ('VPD_U1','B.Cu',.3,('vuu','1d81bbd8-877f-5378-867a-6d22e99ae346'),[(78.2,81.5)],('tuu','dbe83848-37ec-5bce-8118-b7f276d99135',(85.4,81.5))),
 ('PD_BASE','B.Cu',.25,('vuu','783c3e4d-7a2a-5025-880b-cdb5a6129a90'),[(72.9,78.05)],('via','rs17-pdb')),
 ('PD_BASE','F.Cu',.2,('via','rs17-pdb'),[],('tuu','4c893b3e-b8a9-5787-aa99-6a5388e39115',(76.85,77.6))),
 ]}

# RS18: restore local aux power/divider and local logic without occupying B bus bands.
# One 5.14-mm In2 POWER-only VPD hop crosses the PD_BASE/PD_SENSE auxiliary leads.
F.FINAL['RS18-local-restore'] = {
 'delete_poly':['RS17-clear-bus/trk/3','RS17-clear-bus/trk/4'], 'delete':[('via','via/rs17-pdb')],
 'vias':{'rs18-pdb':('PD_BASE',(76.85,77.6)), 'rs18-vpd-a':('VPD',(74.85,78.2)), 'rs18-vpd-b':('VPD',(71.5,82.1)),
 'rs18-ml-a':('MAIN_LED_OK',(65.0,69.0)), 'rs18-ml-b':('MAIN_LED_OK',(77.1,69.6))},
 'tracks':[
 ('PD_BASE','B.Cu',.25,('vuu','783c3e4d-7a2a-5025-880b-cdb5a6129a90'),[(72.9,77.6)],('via','rs18-pdb')),
 ('Net-(R28-Pad2)','F.Cu',.2,('pad','R4','1'),[(69.7,74.65),(76.1,74.65)],('pad','R28','2')),
 ('VPD','F.Cu',.25,('pad','D11','1'),[(74.85,75.2),(77.4,75.2)],('pad','R28','1')),
 ('VPD','F.Cu',.25,('pad','D11','1'),[],('via','rs18-vpd-a')),
 ('VPD','In2.Cu',.25,('via','rs18-vpd-a'),[],('via','rs18-vpd-b')),
 ('VPD','F.Cu',.25,('via','rs18-vpd-b'),[],('pad','R23','1')),
 ('MAIN_OK','F.Cu',.2,('pad','R63','2'),[(86.2,71.9),(87.05,71.05)],('pad','TP5','1')),
 ('V20_OK','F.Cu',.2,('pad','U13','13'),[(74.1,67.06),(74.1,70.87)],('pad','U13','10')),
 ('MAIN_LED_OK','F.Cu',.2,('pad','U14','1'),[(60.99,69.0)],('via','rs18-ml-a')),
 ('MAIN_LED_OK','B.Cu',.2,('via','rs18-ml-a'),[(76.5,69.0)],('via','rs18-ml-b')),
 ('MAIN_LED_OK','F.Cu',.2,('via','rs18-ml-b'),[],('pad','U13','11')),
 ]}

# RS19: first reserved B bus lane, P12_OK y73.8. End transition is east of D9.
F.FINAL['RS19-p12-bus'] = {
 'vias':{'rs19-a':('P12_OK',(62.55,73.8)), 'rs19-b':('P12_OK',(87.8,73.8))},
 'tracks':[
 ('P12_OK','F.Cu',.2,('pad','U14','2'),[],('via','rs19-a')),
 ('P12_OK','B.Cu',.2,('via','rs19-a'),[],('via','rs19-b')),
 ('P12_OK','F.Cu',.2,('via','rs19-b'),[(87.8,74.7)],('pad','TP12','1')),
 ]}

# RS20: two more explicitly reserved parallel B bands: P5_OK y73.2 and N12_OK y72.6.
F.FINAL['RS20-status-bus'] = {
 'vias':{'rs20-p5a':('P5_OK',(64.8,73.2)), 'rs20-p5b':('P5_OK',(90.95,73.2)),
 'rs20-n12a':('N12_OK',(66.07,70.0)), 'rs20-n12b':('N12_OK',(100.65,72.6))},
 'tracks':[
 ('P5_OK','F.Cu',.2,('pad','U14','4'),[],('via','rs20-p5a')),
 ('P5_OK','B.Cu',.2,('via','rs20-p5a'),[],('via','rs20-p5b')),
 ('P5_OK','F.Cu',.2,('via','rs20-p5b'),[],('pad','TP13','1')),
 ('N12_OK','F.Cu',.2,('pad','U14','5'),[],('via','rs20-n12a')),
 ('N12_OK','B.Cu',.2,('via','rs20-n12a'),[(66.07,72.6)],('via','rs20-n12b')),
 ('N12_OK','F.Cu',.2,('via','rs20-n12b'),[],('pad','TP14','1')),
 ]}

# RS21: fourth reserved B bus lane MAIN_LED_OK y74.4, F x87.6 reserves x88.1 for the next signal.
F.FINAL['RS21-mainled-bus'] = {
 'vias':{'rs21-a':('MAIN_LED_OK',(63.15,74.35)), 'rs21-b':('MAIN_LED_OK',(87.6,77.0))},
 'tracks':[
 ('MAIN_LED_OK','F.Cu',.2,('pad','U14','1'),[(60.99,69.6),(62.9,69.6),(62.9,72.95),(63.15,73.2)],('via','rs21-a')),
 ('MAIN_LED_OK','B.Cu',.2,('via','rs21-a'),[(86.95,74.35),(87.6,75.0)],('via','rs21-b')),
 ('MAIN_LED_OK','F.Cu',.2,('via','rs21-b'),[(87.6,81.775),(87.45,81.925),(83.1,81.925),(81.95,83.075),(81.95,83.425),(81.35,84.025),(78.9,84.025),(78.45,84.475)],('pad','Q6','1')),
 ]}
# RS22: keep U1's local supply connection off the newly reserved B signal corridor.
# VPD_U1 is power (not a signal); a local 8.46-mm In2 hop spans the CH224A body.
F.FINAL['RS22-u1-power-hop'] = {
 'delete_poly':['RS17-clear-bus/trk/2'],
 'delete':[('track','d815fa77-fd07-500b-aeaf-9a7a88bb8ae6'),('track','dbe83848-37ec-5bce-8118-b7f276d99135'),('track','2e4c27ee-a95c-5243-8a8b-7f531d5a0491')],
 'tracks':[
 ('VPD_U1','B.Cu',.3,('vuu','1d81bbd8-877f-5378-867a-6d22e99ae346'),[(78.2,81.5),(85.0,81.5),(86.3,80.2)],('vuu','aa165ef7-4268-5ed4-9d8d-fbffe50f9454')),
 ('VPD_U1','In2.Cu',.3,('vuu','aa165ef7-4268-5ed4-9d8d-fbffe50f9454'),[],('vuu','756bf817-5411-5e3f-a7d0-2fdc590c62fb')),
 ]}

# RS23: P5 LED branch enters through the free XB1 column gap x91.95; leaves west bus lanes untouched.
F.FINAL['RS23-p5-led'] = {
 'vias': {'rs23-p5-0': ('P5_OK', (84.85, 91.125)), 'rs23-p5-1': ('P5_OK', (88.65, 94.275)), 'rs23-p5-2': ('P5_OK', (90.25, 94.275)), 'rs23-p5-3': ('P5_OK', (91.95, 83.575))},
 'tracks':[
 ('P5_OK', 'F.Cu', 0.2, ('pad', 'Q8', '1'), [], ('via', 'rs23-p5-0')),
 ('P5_OK', 'B.Cu', 0.2, ('via', 'rs23-p5-0'), [(84.85, 91.575), (87.55, 94.275)], ('via', 'rs23-p5-1')),
 ('P5_OK', 'F.Cu', 0.2, ('via', 'rs23-p5-1'), [], ('via', 'rs23-p5-2')),
 ('P5_OK', 'B.Cu', 0.2, ('via', 'rs23-p5-2'), [(90.25, 92.875), (92.1, 91.025), (92.1, 83.725)], ('via', 'rs23-p5-3')),
 ('P5_OK', 'F.Cu', 0.2, ('via', 'rs23-p5-3'), [(91.95, 76.675)], ('pad', 'TP13', '1')),
 ]}

# RS24: P5_OK east link uses B north of J2 pads, then south of MHB3.
F.FINAL['RS24-p5-east'] = {
 'vias': {'rs24-p5e-0': ('P5_OK', (95.25, 71.375)), 'rs24-p5e-1': ('P5_OK', (129.1, 72.425))},
 'tracks':[
 ('P5_OK', 'F.Cu', 0.2, ('pad', 'TP13', '1'), [], ('via', 'rs24-p5e-0')),
 ('P5_OK', 'B.Cu', 0.2, ('via', 'rs24-p5e-0'), [(95.25, 70.325), (96.1, 69.475), (99.5, 69.475), (100.35, 68.625), (100.35, 67.775), (101.25, 66.875), (117.75, 66.875), (123.3, 72.425)], ('via', 'rs24-p5e-1')),
 ('P5_OK', 'F.Cu', 0.2, ('via', 'rs24-p5e-1'), [], ('pad', 'XB2', '5')),
 ]}

# RS25: N12_OK to existing Q9/U19 net, B below XB1 and F outside the MHB4 annulus.
F.FINAL['RS25-n12-east'] = {
 'vias': {'rs25-n12e-0': ('N12_OK', (100.65, 76.575)), 'rs25-n12e-1': ('N12_OK', (113.2, 97.725)), 'rs25-n12e-2': ('N12_OK', (121.15, 99.325))},
 'tracks':[
 ('N12_OK', 'F.Cu', 0.2, ('pad', 'TP14', '1'), [], ('via', 'rs25-n12e-0')),
 ('N12_OK', 'B.Cu', 0.2, ('via', 'rs25-n12e-0'), [(102.2, 78.125), (102.2, 82.375), (103.95, 84.125), (103.95, 84.425), (105.2, 85.675), (109.5, 85.675), (112.15, 88.325), (112.15, 89.775), (113.2, 90.825)], ('via', 'rs25-n12e-1')),
 ('N12_OK', 'F.Cu', 0.2, ('via', 'rs25-n12e-1'), [(116.2, 100.725), (119.75, 100.725)], ('via', 'rs25-n12e-2')),
 ('N12_OK', 'B.Cu', 0.2, ('via', 'rs25-n12e-2'), [(128.9, 99.325), (131.2, 97.025)], ('via', 'e-n12-0')),
 ]}

# RS26: BAD_FILTERED uses its reserved B y72.0 band and free XB1 gap x97.2.
# Raise U13's local GND via to keep the final ARMED y71.4 band clear as well.
F.FINAL['RS26-bad-bus'] = {
 'delete_poly':['RS17-clear-bus/trk/1'], 'delete':[('via','via/rs17-u13g')],
 'vias':{'rs26-g':('GND',(72.2,70.6)), 'rs26-a':('BAD_FILTERED',(69.4,70.87)),
 'rs26-b':('BAD_FILTERED',(97.2,71.95)), 'rs26-c':('BAD_FILTERED',(97.95,84.125)), 'rs26-d':('BAD_FILTERED',(93.0,87.525))},
 'tracks':[
 ('GND','F.Cu',.25,('pad','U13','7'),[(72.2,73.41)],('via','rs26-g')),
 ('BAD_FILTERED','F.Cu',.2,('pad','U13','5'),[],('via','rs26-a')),
 ('BAD_FILTERED','B.Cu',.2,('via','rs26-a'),[(69.4,72.0),(97.15,72.0)],('via','rs26-b')),
 ('BAD_FILTERED','F.Cu',.2,('via','rs26-b'),[(97.2,72.25),(97.2,83.375)],('via','rs26-c')),
 ('BAD_FILTERED','B.Cu',.2,('via','rs26-c'),[(96.4,84.125)],('via','rs26-d')),
 ('BAD_FILTERED','F.Cu',.2,('via','rs26-d'),[(92.65,87.175)],('pad','U15','4')),
 ]}

# RS27: final reserved parallel B band, ARMED y71.4; short F crossing beyond the bus endpoints.
F.FINAL['RS27-armed-bus'] = {
 'vias':{'rs27-a':('ARMED',(72.1,69.6)), 'rs27-b':('ARMED',(92.55,71.375)), 'rs27-c':('ARMED',(92.55,73.175)), 'rs27-d':('ARMED',(95.3,75.675))},
 'tracks':[
 ('ARMED','F.Cu',.2,('pad','U13','4'),[],('via','rs27-a')),
 ('ARMED','B.Cu',.2,('via','rs27-a'),[(73.0,69.6),(73.0,71.4),(92.525,71.4)],('via','rs27-b')),
 ('ARMED','F.Cu',.2,('via','rs27-b'),[],('via','rs27-c')),
 ('ARMED','B.Cu',.2,('via','rs27-c'),[(95.05,75.675)],('via','rs27-d')),
 ('ARMED','F.Cu',.2,('via','rs27-d'),[],('pad','TP10','1')),
 ]}

# RS28: ARMED latch branch uses B gap x94.6 and a F bridge between R67's pads.
F.FINAL['RS28-armed-latch'] = {
 'vias': {'rs28-arm-0': ('ARMED', (97.5, 91.475)), 'rs28-arm-1': ('ARMED', (95.55, 85.975)), 'rs28-arm-2': ('ARMED', (94.6, 82.375)), 'rs28-arm-3': ('ARMED', (95.65, 76.275))},
 'tracks':[
 ('ARMED', 'F.Cu', 0.2, ('pad', 'U12', '5'), [(96.95, 91.475)], ('via', 'rs28-arm-0')),
 ('ARMED', 'B.Cu', 0.2, ('via', 'rs28-arm-0'), [(95.55, 89.525)], ('via', 'rs28-arm-1')),
 ('ARMED', 'F.Cu', 0.2, ('via', 'rs28-arm-1'), [(95.55, 83.325)], ('via', 'rs28-arm-2')),
 ('ARMED', 'B.Cu', 0.2, ('via', 'rs28-arm-2'), [(94.6, 77.325)], ('via', 'rs28-arm-3')),
 ('ARMED', 'F.Cu', 0.2, ('via', 'rs28-arm-3'), [], ('pad', 'TP10', '1')),
 ]}

# RS29: MAIN_OK west tap goes around the west ends of the bus, then B y67.575 under the logic.
F.FINAL['RS29-mainok-west'] = {
 'vias': {'rs29-mok-0': ('MAIN_OK', (60.15, 76.225)), 'rs29-mok-1': ('MAIN_OK', (77.05, 67.725))},
 'tracks':[
 ('MAIN_OK', 'F.Cu', 0.2, ('pad', 'U5', '15'), [(60.15, 77.225)], ('via', 'rs29-mok-0')),
 ('MAIN_OK', 'B.Cu', 0.2, ('via', 'rs29-mok-0'), [(60.15, 69.075), (61.65, 67.575), (76.75, 67.575)], ('via', 'rs29-mok-1')),
 ('MAIN_OK', 'F.Cu', 0.2, ('via', 'rs29-mok-1'), [(76.3, 68.325)], ('pad', 'U13', '12')),
 ]}

# RS30: MAIN_OK uses F around the lower-left arc of MHB2 and the slot below R63.
F.FINAL['RS30-mainok-cross'] = {'tracks':[
 ('MAIN_OK','F.Cu',.2,('pad','U13','12'),[(77.4,68.325),(81.8,72.725),(84.4,72.725),(87.05,70.075)],('pad','TP5','1')),
]}

# RS31: MAIN_OK east link, reviewed F/B bridges keep J2 supply trunks and the MHB3 annulus intact.
F.FINAL['RS31-mainok-east'] = {
 'vias': {'rs31-mok-0': ('MAIN_OK', (97.9, 66.225)), 'rs31-mok-1': ('MAIN_OK', (114.55, 66.225)), 'rs31-mok-2': ('MAIN_OK', (114.55, 68.425)), 'rs31-mok-3': ('MAIN_OK', (122.3, 74.125)), 'rs31-mok-4': ('MAIN_OK', (130.4, 74.525)), 'rs31-mok-5': ('MAIN_OK', (136.75, 74.525)), 'rs31-mok-6': ('MAIN_OK', (138.35, 74.525))},
 'tracks':[
 ('MAIN_OK', 'F.Cu', 0.2, ('pad', 'TP5', '1'), [(90.35, 66.225)], ('via', 'rs31-mok-0')),
 ('MAIN_OK', 'B.Cu', 0.2, ('via', 'rs31-mok-0'), [], ('via', 'rs31-mok-1')),
 ('MAIN_OK', 'F.Cu', 0.2, ('via', 'rs31-mok-1'), [], ('via', 'rs31-mok-2')),
 ('MAIN_OK', 'B.Cu', 0.2, ('via', 'rs31-mok-2'), [(120.25, 74.125)], ('via', 'rs31-mok-3')),
 ('MAIN_OK', 'F.Cu', 0.2, ('via', 'rs31-mok-3'), [(122.25, 74.025), (123.55, 72.725), (128.6, 72.725)], ('via', 'rs31-mok-4')),
 ('MAIN_OK', 'B.Cu', 0.2, ('via', 'rs31-mok-4'), [], ('via', 'rs31-mok-5')),
 ('MAIN_OK', 'F.Cu', 0.2, ('via', 'rs31-mok-5'), [], ('via', 'rs31-mok-6')),
 ('MAIN_OK', 'B.Cu', 0.2, ('via', 'rs31-mok-6'), [(138.35, 72.125)], ('pad', 'XB2', '2')),
 ]}

# RS32: R83 VPD tap follows east of MHB2, then F y73.225 parallel to MAIN_OK.
F.FINAL['RS32-vpd-tap'] = {
 'vias': {'rs32-vpd-0': ('VPD', (85.9, 69.025)), 'rs32-vpd-1': ('VPD', (87.65, 70.775))},
 'tracks':[
 ('VPD', 'F.Cu', 0.25, ('pad', 'R83', '1'), [], ('via', 'rs32-vpd-0')),
 ('VPD', 'B.Cu', 0.25, ('via', 'rs32-vpd-0'), [], ('via', 'rs32-vpd-1')),
 ('VPD', 'F.Cu', 0.25, ('via', 'rs32-vpd-1'), [(87.65, 71.075), (85.5, 73.225)], ('pad', 'R28', '1')),
 ]}

# RS33: VIN test-point tap only; accepted broad U5/VIN output copper remains unchanged.
F.FINAL['RS33-vin-tp'] = {
 'vias': {'rs33-vin-0': ('VIN', (64.05, 64.325)), 'rs33-vin-1': ('VIN', (60.05, 68.375))},
 'tracks':[
 ('VIN', 'F.Cu', 0.25, ('pad', 'TP4', '1'), [], ('via', 'rs33-vin-0')),
 ('VIN', 'B.Cu', 0.25, ('via', 'rs33-vin-0'), [], ('via', 'rs33-vin-1')),
 ('VIN', 'F.Cu', 0.25, ('via', 'rs33-vin-1'), [(59.9, 71.025), (58.1, 72.825), (58.1, 77.125)], ('pad', 'U5', '18')),
 ]}

# RS34: coordinated LED pin fanout. Q8 moves 0.1 mm west, making a legal 0.2-mm F return
# between Q8 and R87. Move its collector/P5 vias left; do NOT cut the VPD feed to gain this slot.
F.FINAL['RS34-led-local'] = {
 'moves':[('Q8',(83.8,89.5),None)],
 'delete_poly':['RS10-q8-gap/trk/0','L2-d17-u11/trk/1','RS23-p5-led/trk/0','RS23-p5-led/trk/1'],
 'delete':[('via','via/l2-k'),('via','via/rs23-p5-0')],
 'vias':{'rs34-k':('Net-(D17-K)',(82.86,90.4)), 'rs34-p5':('P5_OK',(83.65,90.35)),
 'rs34-l6':('LED_RETURN',(76.53,91.15)), 'rs34-l7':('LED_RETURN',(82.2,92.3825))},
 'tracks':[
 ('Net-(D17-K)','F.Cu',.2,('pad','Q8','3'),[],('via','rs34-k')),
 ('Net-(D17-K)','B.Cu',.2,('via','rs34-k'),[],('pad','D17','1')),
 ('P5_OK','F.Cu',.2,('pad','Q8','1'),[],('via','rs34-p5')),
 ('P5_OK','B.Cu',.2,('via','rs34-p5'),[(84.85,91.575),(87.55,94.275)],('via','rs23-p5-1')),
 ('LED_RETURN','F.Cu',.2,('pad','Q8','2'),[(85.8,89.0),(85.8,91.1),(83.03,91.1)],('pad','Q7','2')),
 ('LED_RETURN','F.Cu',.2,('pad','Q6','2'),[],('via','rs34-l6')),
 ('LED_RETURN','B.Cu',.2,('via','rs34-l6'),[],('via','rs34-l7')),
 ('LED_RETURN','F.Cu',.2,('via','rs34-l7'),[],('pad','Q7','2')),
 ]}

# Preserve 0.2 mm to the existing P12 F lane; the Q6 branch is a separate next connection.
F.FINAL['RS34-led-local']['moves']=[('Q8',(83.825,89.5),None)]
F.FINAL['RS34-led-local']['vias'].pop('rs34-l6')
F.FINAL['RS34-led-local']['vias'].pop('rs34-l7')
F.FINAL['RS34-led-local']['tracks']=F.FINAL['RS34-led-local']['tracks'][:5]

# RS35: short B LED-return link behind Q6/Q7, clear of the R22 power via and EF_UV.
F.FINAL['RS35-led-67'] = {
 'vias': {'rs35-l67-0': ('LED_RETURN', (77.6, 92.375)), 'rs35-l67-1': ('LED_RETURN', (82.3, 92.375))},
 'tracks':[
 ('LED_RETURN', 'F.Cu', 0.2, ('pad', 'Q6', '2'), [], ('via', 'rs35-l67-0')),
 ('LED_RETURN', 'B.Cu', 0.2, ('via', 'rs35-l67-0'), [], ('via', 'rs35-l67-1')),
 ('LED_RETURN', 'F.Cu', 0.2, ('via', 'rs35-l67-1'), [], ('pad', 'Q7', '2')),
 ]}

# RS36: switched LED return goes around (not through) the unchanged input heat copper and USB feed.
F.FINAL['RS36-led-return-source'] = {
 'vias': {'rs36-l10-0': ('LED_RETURN', (68.0, 80.525)), 'rs36-l10-1': ('LED_RETURN', (75.75, 93.175))},
 'tracks':[
 ('LED_RETURN', 'F.Cu', 0.2, ('pad', 'Q10', '3'), [(68.0, 80.575)], ('via', 'rs36-l10-0')),
 ('LED_RETURN', 'B.Cu', 0.2, ('via', 'rs36-l10-0'), [(67.2, 80.525), (65.4, 78.725), (65.4, 77.275), (65.0, 76.875), (64.45, 76.875), (64.05, 77.275), (64.05, 77.725), (63.5, 78.275), (57.0, 78.275), (54.55, 80.725), (54.55, 88.875), (58.8, 93.125), (63.7, 93.125), (65.1, 94.525), (65.1, 94.725), (65.45, 95.075), (73.85, 95.075)], ('via', 'rs36-l10-1')),
 ('LED_RETURN', 'F.Cu', 0.2, ('via', 'rs36-l10-1'), [], ('pad', 'Q6', '2')),
 ]}

# RS37: reserve front-edge F/B lanes by moving only LED resistor and logic-supply dogbones.
F.FINAL['RS37-south-corridor'] = {'moves': [('R88', (133.4, 90.55), None)],
 'delete': [('track', '0a0fdc8c-05ea-5a43-a982-fe6b8d7f9006'),
            ('track', '1f2fcbe3-700e-5685-a74b-c8d5d1aa9f62'),
            ('via', '249d4e08-8c50-51e5-b340-8d2cb4313c00'),
            ('track', '319cd01d-8e2d-5e2f-9f40-ae1b00467b47'),
            ('track', '5655cc44-3caf-59f0-a528-c78815660bf5'),
            ('via', '67ebb3a4-c1e1-525e-919a-d11cc4e89f4b'),
            ('track', '721bf848-3e0c-5deb-816e-d0e17dfab334'),
            ('via', '73385011-5ab0-55d9-b15d-d56d948ee131'),
            ('via', '74f394fb-a39b-54e9-a813-cb5e4bc2e84b'),
            ('track', '7c7905b4-a40d-5bcb-8f0e-fe5a6afdee99'),
            ('track', '8ee096cc-bcc5-591b-9442-bfbf0666fe71'),
            ('track', 'a30b7405-9ff4-565a-b0b3-3cae855e66cb'),
            ('track', 'b2e6e2c8-4cfc-5c66-ab10-823ae22b8d8c'),
            ('track', 'c11df13d-3597-543c-bd87-bbb2d3424551'),
            ('track', 'c27eeb75-0bbb-58c8-924e-eb83605c0fb1'),
            ('via', 'c46ca31e-23ef-5c9f-bad7-8913e0a8e107'),
            ('track', 'c4c5da06-ad9d-5a4a-888b-de55e3a622f6'),
            ('track', 'cf28acc2-3a48-565e-8bb4-fdf8153f7e43'),
            ('track', 'dc914867-cf20-5897-a21f-778a5c123e7e'),
            ('track', 'e711e27f-32dc-56f0-a711-935d9c4c9b05'),
            ('track', 'eeb8e64e-8e3a-513a-93ae-a813e31b3996'),
            ('track', 'f28480a4-f5d9-5736-a609-7b17802c849b')],
 'vias': {'rs37-r68': ('V3V3', (109.3, 99.525)),
          'rs37-c50': ('V3V3', (113.0, 99.475)),
          'rs37-c52': ('V3V3', (121.15, 100.125)),
          'rs37-r88': ('V3V3', (131.7, 90.55)),
          'rs37-c57': ('V3V3', (130.7, 99.8)),
          'rs37-d18a': ('Net-(D18-A)', (135.3, 100.75))},
 'tracks': [('V3V3', 'F.Cu', 0.25, ('pad', 'R68', '1'), [], ('via', 'rs37-r68')),
            ('V3V3', 'F.Cu', 0.25, ('pad', 'C50', '1'), [], ('via', 'rs37-c50')),
            ('V3V3', 'F.Cu', 0.25, ('pad', 'C52', '1'), [], ('via', 'rs37-c52')),
            ('V3V3', 'F.Cu', 0.25, ('pad', 'R88', '1'), [], ('via', 'rs37-r88')),
            ('V3V3', 'F.Cu', 0.25, ('pad', 'C57', '1'), [], ('via', 'rs37-c57')),
            ('Net-(D18-A)', 'F.Cu', 0.2, ('pad', 'R88', '2'), [(135.3, 91.625)], ('via', 'rs37-d18a')),
            ('Net-(D18-A)', 'B.Cu', 0.2, ('via', 'rs37-d18a'), [(113.075, 100.75), (110.25, 97.925)], ('pad', 'D18', '2'))]}

# R88 fit correction: clear D15 and the monitor dividers; remain >=1 mm above the front cutout.
_rs37=F.FINAL['RS37-south-corridor']
_rs37['moves']=[('R88',(138.85,92.2),None)]
_rs37['vias']['rs37-r88']=('V3V3',(137.25,91.55))
_rs37['tracks'][5]=('Net-(D18-A)','F.Cu',.2,('pad','R88','2'),[(139.675,93.05),(135.3,93.05)],('via','rs37-d18a'))


_rs37['moves']=[('R88',(139.3,92.2),None)]
_rs37['vias'].pop('rs37-r88')
_rs37['tracks'][3]=('V3V3','F.Cu',.25,('pad','R88','1'),[],('vuu','182115dd-6051-5511-89a5-afda85ddcdaf'))
_rs37['tracks'][5]=('Net-(D18-A)','F.Cu',.2,('pad','R88','2'),[(140.125,93.05),(135.3,93.05)],('via','rs37-d18a'))

# RS38: LED_RETURN takes the reserved front F lane y101.125 (1.05 mm edge clearance).
# Print-only raster margin reduced for discovery; exact native clearances remain unchanged.
F.FINAL['RS38-led-return-east'] = {
 'vias': {'rs38-l9-0': ('LED_RETURN', (83.7, 93.025)), 'rs38-l9-1': ('LED_RETURN', (112.5, 101.025))},
 'tracks':[
 ('LED_RETURN', 'F.Cu', 0.2, ('pad', 'Q7', '2'), [], ('via', 'rs38-l9-0')),
 ('LED_RETURN', 'B.Cu', 0.2, ('via', 'rs38-l9-0'), [(83.7, 93.375), (91.35, 101.025)], ('via', 'rs38-l9-1')),
 ('LED_RETURN', 'F.Cu', 0.2, ('via', 'rs38-l9-1'), [(112.6, 101.125), (128.5, 101.125), (130.7, 98.925), (132.05, 98.925)], ('pad', 'Q9', '2')),
 ]}

# RS39: finish both front LED crossings in separate F/B bands; relocate only C57 and local V3 dogbone.
F.FINAL['RS39-front-led-pair'] = {'moves': [('C57', (129.4, 100.0), None)],
 'delete_poly': ['RS38-led-return-east/trk/0',
                 'RS38-led-return-east/trk/1',
                 'RS38-led-return-east/trk/2',
                 'RS37-south-corridor/trk/1',
                 'RS37-south-corridor/trk/4',
                 'RS37-south-corridor/trk/6'],
 'delete': [('track', '86e6c060-5c76-56d6-8e7a-ca1c9235c327'),
            ('via', '0454a904-b1fd-5365-9670-3197e60f35f9'),
            ('via', 'via/rs38-l9-0'),
            ('via', 'via/rs38-l9-1'),
            ('via', 'via/rs37-c50'),
            ('via', 'via/rs37-c57')],
 'vias': {'rs39-c50': ('V3V3', (112.0, 100.4)),
          'rs39-c57v': ('V3V3', (127.5, 100.0)),
          'rs39-c57g': ('GND', (130.175, 98.9)),
          'rs39-ret-a': ('LED_RETURN', (83.05, 93.475)),
          'rs39-ret-b': ('LED_RETURN', (113.2, 99.0)),
          'rs39-k': ('Net-(D18-K)', (132.0, 100.5))},
 'tracks': [('V3V3', 'F.Cu', 0.25, ('pad', 'C50', '1'), [], ('via', 'rs39-c50')),
            ('V3V3', 'F.Cu', 0.25, ('pad', 'C57', '1'), [], ('via', 'rs39-c57v')),
            ('GND', 'F.Cu', 0.25, ('pad', 'C57', '2'), [], ('via', 'rs39-c57g')),
            ('LED_RETURN', 'F.Cu', 0.2, ('pad', 'Q7', '2'), [], ('via', 'rs39-ret-a')),
            ('LED_RETURN',
             'B.Cu',
             0.2,
             ('via', 'rs39-ret-a'),
             [(83.85, 93.475),
              (89.2, 98.825),
              (89.2, 98.925),
              (89.4, 99.125),
              (93.5, 99.125),
              (95.75, 96.875),
              (95.75, 96.825),
              (95.95, 96.625),
              (100.1, 96.625),
              (100.9, 97.425),
              (111.65, 97.425)],
             ('via', 'rs39-ret-b')),
            ('LED_RETURN', 'F.Cu', 0.2, ('via', 'rs39-ret-b'), [(115.325, 101.125), (133.1, 101.125)], ('pad', 'Q9', '2')),
            ('Net-(D18-A)',
             'B.Cu',
             0.2,
             ('via', 'rs37-d18a'),
             [(134.45, 99.9), (131.0, 99.9), (130.15, 100.75), (113.075, 100.75), (110.25, 97.925)],
             ('pad', 'D18', '2')),
            ('Net-(D18-K)', 'B.Cu', 0.2, ('pad', 'D18', '1'), [(96.98, 101.15), (130.9, 101.15), (131.55, 100.5)], ('via', 'rs39-k')),
            ('Net-(D18-K)', 'F.Cu', 0.2, ('via', 'rs39-k'), [(132.0, 97.0)], ('pad', 'Q9', '3'))]}

F.FINAL['RS39-front-led-pair']['moves']=[('C57',(129.4,100.25),None)]
F.FINAL['RS39-front-led-pair']['vias']['rs39-c50']=('V3V3',(112.0,100.5))

# RS40: TIMER_GO takes the reserved north B corridor, leaving the parallel south bus intact.
F.FINAL['RS40-timer-north'] = {
 'vias': {'rs40-timer-0': ('TIMER_GO', (77.8, 69.725)), 'rs40-timer-1': ('TIMER_GO', (90.5, 70.775)), 'rs40-timer-2': ('TIMER_GO', (91.85, 73.875)), 'rs40-timer-3': ('TIMER_GO', (92.8, 74.825))},
 'tracks':[
 ('TIMER_GO', 'F.Cu', 0.2, ('pad', 'U13', '8'), [(76.1, 73.425), (77.8, 71.675)], ('via', 'rs40-timer-0')),
 ('TIMER_GO', 'B.Cu', 0.2, ('via', 'rs40-timer-0'), [(77.8, 66.375), (79.55, 64.635), (79.65, 64.635), (80.51, 63.775), (83.45, 63.775), (89.75, 70.075), (89.75, 70.225), (90.3, 70.775)], ('via', 'rs40-timer-1')),
 ('TIMER_GO', 'F.Cu', 0.2, ('via', 'rs40-timer-1'), [(91.85, 72.125)], ('via', 'rs40-timer-2')),
 ('TIMER_GO', 'B.Cu', 0.2, ('via', 'rs40-timer-2'), [], ('via', 'rs40-timer-3')),
 ('TIMER_GO', 'F.Cu', 0.2, ('via', 'rs40-timer-3'), [], ('pad', 'R69', '1')),
 ]}

# RS41: RUN crosses the north F/B corridors. Branch on the existing local RUN segment,
# rather than overlaying a nearly identical pad lead from the printed suggestion.
F.FINAL['RS41-run-east'] = {
 'vias': {'rs41-run-0': ('RUN', (74.25, 66.075)), 'rs41-run-1': ('RUN', (79.9, 63.525)), 'rs41-run-2': ('RUN', (85.05, 63.525)), 'rs41-run-3': ('RUN', (96.1, 63.525)), 'rs41-run-4': ('RUN', (113.7, 64.575)), 'rs41-run-5': ('RUN', (115.35, 66.225))},
 'tracks':[
 ('RUN', 'F.Cu', 0.2, ('trk','RS16-locals/trk/6',(72.0,68.33)), [], ('via', 'rs41-run-0')),
 ('RUN', 'B.Cu', 0.2, ('via', 'rs41-run-0'), [(76.55, 66.075), (79.15, 63.475), (79.85, 63.475)], ('via', 'rs41-run-1')),
 ('RUN', 'F.Cu', 0.2, ('via', 'rs41-run-1'), [], ('via', 'rs41-run-2')),
 ('RUN', 'B.Cu', 0.2, ('via', 'rs41-run-2'), [], ('via', 'rs41-run-3')),
 ('RUN', 'F.Cu', 0.2, ('via', 'rs41-run-3'), [(112.65, 63.525)], ('via', 'rs41-run-4')),
 ('RUN', 'B.Cu', 0.2, ('via', 'rs41-run-4'), [], ('via', 'rs41-run-5')),
 ('RUN', 'F.Cu', 0.2, ('via', 'rs41-run-5'), [(115.35, 68.875), (117.75, 71.275)], ('pad', 'R64', '1')),
 ]}

# RS42: V20_OK uses the released B lane below D11, not another diagonal through the south-MHB2 bus.
F.FINAL['RS42-v20-west'] = {
 'vias': {'rs42-v20-0': ('V20_OK', (73.85, 68.375)), 'rs42-v20-1': ('V20_OK', (66.7, 68.375)), 'rs42-v20-2': ('V20_OK', (67.3, 75.125)), 'rs42-v20-3': ('V20_OK', (93.6, 75.125)), 'rs42-v20-4': ('V20_OK', (95.55, 74.875)), 'rs42-v20-5': ('V20_OK', (97.8, 75.025))},
 'tracks':[
 ('V20_OK', 'F.Cu', 0.2, ('trk','RS18-local-restore/trk/7',(74.1,68.375),1), [], ('via', 'rs42-v20-0')),
 ('V20_OK', 'B.Cu', 0.2, ('via', 'rs42-v20-0'), [], ('via', 'rs42-v20-1')),
 ('V20_OK', 'F.Cu', 0.2, ('via', 'rs42-v20-1'), [(67.95, 69.625), (67.95, 73.075), (67.3, 73.725)], ('via', 'rs42-v20-2')),
 ('V20_OK', 'B.Cu', 0.2, ('via', 'rs42-v20-2'), [(69.15, 76.975), (86.75, 76.975), (87.35, 77.575), (90.0, 77.575), (91.55, 76.025), (92.7, 76.025)], ('via', 'rs42-v20-3')),
 ('V20_OK', 'F.Cu', 0.2, ('via', 'rs42-v20-3'), [(93.85, 74.875)], ('via', 'rs42-v20-4')),
 ('V20_OK', 'B.Cu', 0.2, ('via', 'rs42-v20-4'), [(95.7, 75.025)], ('via', 'rs42-v20-5')),
 ('V20_OK', 'F.Cu', 0.2, ('via', 'rs42-v20-5'), [], ('pad', 'TP15', '1')),
 ]}

# RS43: V20_OK east link through XB1's available gaps; join the existing R85 via, no overlaid pad lead.
F.FINAL['RS43-v20-east'] = {
 'vias': {'rs43-v20-0': ('V20_OK', (99.6, 76.825)), 'rs43-v20-1': ('V20_OK', (100.7, 82.575)), 'rs43-v20-2': ('V20_OK', (106.15, 82.575)), 'rs43-v20-3': ('V20_OK', (117.65, 77.075)), 'rs43-v20-4': ('V20_OK', (121.1, 72.275)), 'rs43-v20-5': ('V20_OK', (119.05, 70.225))},
 'tracks':[
 ('V20_OK', 'F.Cu', 0.2, ('pad', 'TP15', '1'), [], ('via', 'rs43-v20-0')),
 ('V20_OK', 'B.Cu', 0.2, ('via', 'rs43-v20-0'), [(99.6, 81.475)], ('via', 'rs43-v20-1')),
 ('V20_OK', 'F.Cu', 0.2, ('via', 'rs43-v20-1'), [], ('via', 'rs43-v20-2')),
 ('V20_OK', 'B.Cu', 0.2, ('via', 'rs43-v20-2'), [(107.3, 81.425), (107.3, 80.525), (108.1, 79.725), (115.0, 79.725)], ('via', 'rs43-v20-3')),
 ('V20_OK', 'F.Cu', 0.2, ('via', 'rs43-v20-3'), [(121.1, 73.625)], ('via', 'rs43-v20-4')),
 ('V20_OK', 'B.Cu', 0.2, ('via', 'rs43-v20-4'), [], ('via', 'rs43-v20-5')),
 ('V20_OK', 'F.Cu', 0.2, ('via', 'rs43-v20-5'), [(119.05, 67.275)], ('via','e-v20-1')),
 ]}

# RS44: re-lay MAIN_OK below J2's pad rows, removing its north B fence and three vias.
# This opens the MON_20 crossing without touching +5V or any other high-current copper.
F.FINAL['RS44-mainok-j2-gap'] = {
 'delete_poly':['RS31-mainok-east/trk/0','RS31-mainok-east/trk/1','RS31-mainok-east/trk/2','RS31-mainok-east/trk/3'],
 'delete':[('via','via/rs31-mok-0'),('via','via/rs31-mok-1'),('via','via/rs31-mok-2')],
 'vias':{'rs44-mok':('MAIN_OK',(97.9,72.025))},
 'tracks':[
 ('MAIN_OK','F.Cu',.2,('pad','TP5','1'),[(90.35,66.225),(97.9,66.225)],('via','rs44-mok')),
 ('MAIN_OK','B.Cu',.2,('via','rs44-mok'),[(118.15,72.025),(120.25,74.125)],('via','rs31-mok-3')),
 ]}

# RS45: MON_20 uses J2's between-row F gap, then F below XB1 and above Q4.
# No -12V B pour crossing and no inner-layer signal track; original MAIN_OK retained after RS44 rollback.
F.FINAL['RS45-mon20'] = {
 'vias': {'rs45-mon-0': ('MON_20', (88.4, 64.925)), 'rs45-mon-1': ('MON_20', (91.55, 68.075)), 'rs45-mon-2': ('MON_20', (97.85, 74.275)), 'rs45-mon-3': ('MON_20', (98.45, 82.825)), 'rs45-mon-4': ('MON_20', (112.0, 83.125)), 'rs45-mon-5': ('MON_20', (117.0, 79.025)), 'rs45-mon-6': ('MON_20', (134.0, 79.175))},
 'tracks':[
 ('MON_20', 'F.Cu', 0.2, ('pad', 'R83', '2'), [], ('via', 'rs45-mon-0')),
 ('MON_20', 'B.Cu', 0.2, ('via', 'rs45-mon-0'), [], ('via', 'rs45-mon-1')),
 ('MON_20', 'F.Cu', 0.2, ('via', 'rs45-mon-1'), [(93.1, 69.625), (96.95, 69.625), (97.85, 70.525)], ('via', 'rs45-mon-2')),
 ('MON_20', 'B.Cu', 0.2, ('via', 'rs45-mon-2'), [(98.35, 74.775), (98.35, 75.275), (97.15, 76.475), (97.15, 81.525)], ('via', 'rs45-mon-3')),
 ('MON_20', 'F.Cu', 0.2, ('via', 'rs45-mon-3'), [(98.75, 83.125)], ('via', 'rs45-mon-4')),
 ('MON_20', 'B.Cu', 0.2, ('via', 'rs45-mon-4'), [(113.25, 83.125), (117.0, 79.375)], ('via', 'rs45-mon-5')),
 ('MON_20', 'F.Cu', 0.2, ('via', 'rs45-mon-5'), [(118.2, 77.825), (119.55, 77.825), (120.3, 77.075), (127.8, 77.075), (129.95, 79.175)], ('via', 'rs45-mon-6')),
 ('MON_20', 'B.Cu', 0.2, ('via', 'rs45-mon-6'), [], ('via','e-m20-1')),
 ]}

# RS46: ANY_BAD uses the F pin gap in U14/R4 and short F crossing at Q3, then B to its RC resistor.
F.FINAL['RS46-anybad'] = {
 'vias': {'rs46-any-0': ('ANY_BAD', (73.5, 78.275)), 'rs46-any-1': ('ANY_BAD', (79.5, 80.825)), 'rs46-any-2': ('ANY_BAD', (80.5, 82.125)), 'rs46-any-3': ('ANY_BAD', (91.2, 90.775))},
 'tracks':[
 ('ANY_BAD', 'F.Cu', 0.2, ('pad', 'U14', '6'), [(66.7, 72.325), (66.7, 75.875), (67.05, 76.225), (67.05, 77.075), (68.75, 78.775), (72.15, 78.775), (72.65, 78.275)], ('via', 'rs46-any-0')),
 ('ANY_BAD', 'B.Cu', 0.2, ('via', 'rs46-any-0'), [(76.05, 80.825)], ('via', 'rs46-any-1')),
 ('ANY_BAD', 'F.Cu', 0.2, ('via', 'rs46-any-1'), [(80.5, 81.825)], ('via', 'rs46-any-2')),
 ('ANY_BAD', 'B.Cu', 0.2, ('via', 'rs46-any-2'), [(83.45, 82.125), (91.2, 89.875)], ('via', 'rs46-any-3')),
 ('ANY_BAD', 'F.Cu', 0.2, ('via', 'rs46-any-3'), [(91.05, 90.925), (91.05, 92.375)], ('pad', 'R72', '1')),
 ]}

# RS47: RESET_N uses the west F escape and the B lane below the status bus, with explicit local bridges.
# Endpoint joins existing RESET_N copper rather than overlaying the R67 pad lead.
F.FINAL['RS47-reset'] = {
 'vias': {'rs47-reset-0': ('RESET_N', (62.3, 65.225)), 'rs47-reset-1': ('RESET_N', (60.2, 67.325)), 'rs47-reset-2': ('RESET_N', (66.1, 74.925)), 'rs47-reset-3': ('RESET_N', (70.5, 77.525)), 'rs47-reset-4': ('RESET_N', (71.35, 76.375)), 'rs47-reset-5': ('RESET_N', (85.25, 76.375)), 'rs47-reset-6': ('RESET_N', (87.0, 78.125)), 'rs47-reset-7': ('RESET_N', (90.9, 88.525)), 'rs47-reset-8': ('RESET_N', (93.05, 88.525)), 'rs47-reset-9': ('RESET_N', (94.95, 86.625))},
 'tracks':[
 ('RESET_N', 'F.Cu', 0.2, ('pad', 'U13', '1'), [(70.25, 65.225)], ('via', 'rs47-reset-0')),
 ('RESET_N', 'B.Cu', 0.2, ('via', 'rs47-reset-0'), [], ('via', 'rs47-reset-1')),
 ('RESET_N', 'F.Cu', 0.2, ('via', 'rs47-reset-1'), [(60.2, 67.725), (60.6, 68.125), (60.6, 68.775), (60.45, 68.925), (60.45, 70.575), (60.35, 70.675), (60.35, 72.675), (60.65, 72.975), (60.9, 72.975), (62.85, 74.925), (63.4, 74.925), (64.4, 73.925), (65.1, 73.925)], ('via', 'rs47-reset-2')),
 ('RESET_N', 'B.Cu', 0.2, ('via', 'rs47-reset-2'), [(68.7, 77.525)], ('via', 'rs47-reset-3')),
 ('RESET_N', 'F.Cu', 0.2, ('via', 'rs47-reset-3'), [(71.35, 76.675)], ('via', 'rs47-reset-4')),
 ('RESET_N', 'B.Cu', 0.2, ('via', 'rs47-reset-4'), [(83.4, 76.375), (84.1, 75.675), (84.55, 75.675)], ('via', 'rs47-reset-5')),
 ('RESET_N', 'F.Cu', 0.2, ('via', 'rs47-reset-5'), [], ('via', 'rs47-reset-6')),
 ('RESET_N', 'B.Cu', 0.2, ('via', 'rs47-reset-6'), [(89.55, 80.675), (89.55, 87.175)], ('via', 'rs47-reset-7')),
 ('RESET_N', 'F.Cu', 0.2, ('via', 'rs47-reset-7'), [(90.9, 88.725), (91.325, 89.15), (91.5, 89.25), (92.45, 89.25)], ('via', 'rs47-reset-8')),
 ('RESET_N', 'B.Cu', 0.2, ('via', 'rs47-reset-8'), [], ('via', 'rs47-reset-9')),
 ('RESET_N', 'F.Cu', 0.2, ('via', 'rs47-reset-9'), [(95.92,86.625)], ('tuu','8ff5bc55-f709-5583-a09c-137823f68cb6',(96.4,86.145))),
 ]}

# RS48: user-authorized LED LOAD RETURN power hops, not a logic signal on In2.
# Two bounded local hops (2.4 mm across CC wiring, ~5.0 mm across F1) replace the long perimeter detour.
# Q10 remains the switching return; no GND/N12/LED_RETURN net tie or high-current input copper edit.
F.FINAL['RS48-return-local-hops'] = {
 'delete_poly':['RS36-led-return-source/trk/0','RS36-led-return-source/trk/1','RS36-led-return-source/trk/2'],
 'delete':[('via','via/rs36-l10-0'),('via','via/rs36-l10-1')],
 'vias':{'rs48-a':('LED_RETURN',(68.9,82.0)), 'rs48-b':('LED_RETURN',(68.9,84.4)), 'rs48-c':('LED_RETURN',(69.0,90.4)), 'rs48-d':('LED_RETURN',(74.0,93.2))},
 'tracks':[
 ('LED_RETURN','F.Cu',.2,('pad','Q10','3'),[],('via','rs48-a')),
 ('LED_RETURN','In2.Cu',.2,('via','rs48-a'),[],('via','rs48-b')),
 ('LED_RETURN','B.Cu',.2,('via','rs48-b'),[(68.9,89.9),(69.0,90.0)],('via','rs48-c')),
 ('LED_RETURN','In2.Cu',.2,('via','rs48-c'),[],('via','rs48-d')),
 ('LED_RETURN','F.Cu',.2,('via','rs48-d'),[],('pad','Q6','2')),
 ]}

# Route the second local return hop around the actual CC1/CC2 through-vias, not through their barrels.
_rs48=F.FINAL['RS48-return-local-hops']
_rs48['vias']['rs48-c']=('LED_RETURN',(68.55,90.2))
_rs48['tracks'][2]=('LED_RETURN','B.Cu',.2,('via','rs48-b'),[(68.9,89.8)],('via','rs48-c'))
_rs48['tracks'][3]=('LED_RETURN','In2.Cu',.2,('via','rs48-c'),[(68.25,90.5),(68.25,91.9),(69.0,92.65)],('via','rs48-d'))

# RS49: NOT_FAULT uses the B perimeter freed by the local LED-return power hops,
# then the F lane below the panel LED pads. No new corridor through the power stages.
F.FINAL['RS49-notfault'] = {
 'vias': {'rs49-nf-0': ('NOT_FAULT', (69.375, 66.975)), 'rs49-nf-1': ('NOT_FAULT', (69.5, 99.125))},
 'tracks':[
 ('NOT_FAULT', 'F.Cu', 0.2, ('pad', 'U13', '2'), [(70.7, 66.975)], ('via', 'rs49-nf-0')),
 ('NOT_FAULT', 'B.Cu', 0.2, ('via', 'rs49-nf-0'), [(65.85, 63.475), (55.0, 63.475), (52.5, 65.975), (52.5, 75.525), (54.6, 77.625), (54.6, 88.925), (58.8, 93.125), (63.7, 93.125), (65.15, 94.575), (65.15, 94.775)], ('via', 'rs49-nf-1')),
 ('NOT_FAULT', 'F.Cu', 0.2, ('via', 'rs49-nf-1'), [(98.0, 99.125), (98.3, 98.825), (98.3, 97.375), (101.0, 94.625)], ('pad', 'U12', '8')),
 ]}

# RS50: remove the F ground/ARMED enclosure around U13's remaining FAULT_CLK pin.
# Only local true-GND and ARMED dogbones move; the proven parallel bus stays intact.
F.FINAL['RS50-clock-escape-space'] = {
 'delete_poly':['RS26-bad-bus/trk/0','RS27-armed-bus/trk/0','RS27-armed-bus/trk/1'],
 'delete':[('via','via/rs26-g'),('via','via/rs27-a')],
 'vias':{'rs50-g':('GND',(72.65,70.6)), 'rs50-ar':('ARMED',(69.4,69.6))},
 'tracks':[
 ('GND','F.Cu',.25,('pad','U13','7'),[(72.65,73.41)],('via','rs50-g')),
 ('ARMED','F.Cu',.2,('pad','U13','4'),[],('via','rs50-ar')),
 ('ARMED','B.Cu',.2,('via','rs50-ar'),[(70.1,69.6),(70.1,71.4),(92.525,71.4)],('via','rs27-b')),
 ]}

if __name__ == '__main__':
 cmd=sys.argv[1]
 if cmd=='apply':
  rc=R.apply(sys.argv[2])
  if not rc:
   import check_support_copper as C
   import json
   ck=C.check(R.BOARD,refill=True)
   (R.RES/(sys.argv[2]+'-supports.json')).write_text(json.dumps(ck,indent=1))
   print('SUPPORT problems',ck['problems'])
   rc=bool(ck['problems'])
  sys.exit(rc)
 elif cmd=='path':
  tag,n,L,a,b=sys.argv[2:7]
  F.suggest(tag,n,L,a,b,float(sys.argv[7]) if len(sys.argv)>7 else .2)
 elif cmd=='render':
  R.render(sys.argv[2],tuple(map(float,sys.argv[3:7])) if len(sys.argv)>3 else None)
 elif cmd=='audit': R.audit()
