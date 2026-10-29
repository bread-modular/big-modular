# CvRecorder (shared ATtiny1616 library)

MIDI-clock-synced 4-bar recorder for two knob/CV values, driven by one
button + LED. Bread Modular crash `CvRecorder.h` plus the loop offset
(knobs ignored for the first loop pass, then they shift the whole recorded
curve). Behaviour and API: comments at the top of `CvRecorder.h`.

Needs a `SimpleMIDI` with clock/Start callbacks (8bit crash/supersaw copy).

## Use in a sketch

arduino-cli only compiles files in the sketch folder, so symlink the header
there (relative, so it works in any checkout):

```sh
cd modules/<module>/firmware/<sketch>/<sketch>
ln -s "$(realpath --relative-to=. "$(git rev-parse --show-toplevel)/opt/attiny1616-tools/lib/CvRecorder/CvRecorder.h")" CvRecorder.h
```

Then `#include "CvRecorder.h"`. Edit the file here, never through a copy.

Users: `modules/8bit/firmware/supersaw`, `modules/8bit/firmware/crash`.

## Tests

```sh
opt/attiny1616-tools/lib/CvRecorder/sim.sh   # host tests, no hardware
```
