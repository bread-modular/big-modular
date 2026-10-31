# Coordinated corridor rework (proposal under native checking)

Do not accept a shortest path which consumes the next net's only crossing. The previous RS12 trial was rejected; only clean RS14 was promoted.

The next placement/routing refinement re-orients U14 horizontally and U13 vertically within the same west logic area, puts C53/C54 beside their actual ICs, and relocates the obstructing R27/TP5/R28 auxiliary parts. The aim is to free a **continuous south-MHB2 B corridor** plus a F crossing corridor, rather than thread more traces through the USB-PD body. Native fit, 2-mm assembly clearance, all five annuli and local decoupling must pass before promotion. Fixed hardware and main-input/U8 power/Kelvin remain unchanged.

Reserve the north F/B lanes for selected long links; arrange the south-MHB2 control crossings as parallel horizontal bands, with fanout transitions outside the narrow neck. Keep the P12_OK east/LED network already completed. The old RESET/ARMED/FAULT and rescue detour diagonals are explicitly removable low-current copper, not protected hand routing. Intermediate opens can rise during this authorized controlled rip; they are not completion.
