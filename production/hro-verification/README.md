Final exact-hardware evidence:81 tests pass, carrier all-severity ERC/DRC/parity/opens0, passive-panel DRC/opens0, no ignored rules/exclusions. Common tool raw report and source-only geometry/electrical reports retained.

The historical `fabrication_ready:false` fields in source-only verifiers mean those individual checks do not grant a manufacturing approval; they do not inspect artwork. The scoped bare-PCB release decision is production/hro-r1/release-validation.json, which additionally checks stack/process/CAM/archives. No assembled-product qualification is granted.

Two independent complete release generations match all62 files byte-for-byte. Known pcbnew SWIG/property diagnostic messages and Gerbonara Excellon G90 notices are retained; native ERC/DRC reports themselves contain zero findings.
