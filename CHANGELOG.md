# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and version numbers
follow [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-09-28

Performance at larger sizes. Output is unchanged: the console report and report.md are byte-identical to the previous release on the sample data and on generated inputs, and every chart renders pixel-identical on the sample data, so no committed image changed. The only visible difference is on inputs larger than a chart's cap, where the chart now shows a subset and says so in its title.

### Added

- `benchmarks/size_test.py`, a hand-run size test: generates bigger inputs, runs the tool end to end
  and prints run time and peak memory. Not part of CI or the test suite.
- A Limitations section in the README, starting with the measured size-test numbers.
- Tests for the record index and the chart cap.

### Changed

- Commissioning record states are looked up from an index built once per hall instead of filtering
  the records for every device and level. Same states; a test checks every lookup against the direct
  filter.
- The readiness chart shows at most the 30 halls furthest from ready. 1,000 halls went from about 3
  minutes and 1.25 GB to about 20 seconds and 150 MB.

## [1.0.0] - 2026-09-28

First release. Gives each data hall a ready / conditional / not-ready verdict, with reasons, for starting its next commissioning level, from NetBox assets, commissioning records, a punch list and a capacity figure. All sample data is synthetic.

### Included

- Commissioning levels (default L1 to L5) in `config/levels.yaml`, with strict sequencing: no level counts as closed while an earlier one on the same device is open, and IST (L5) can't start until every device's L4 is closed and signed.
- Gate rules: SEQUENCE, PREREQ, WAIVED (waivers off by default, never better than conditional), PUNCH_A/B/C, and a design-load vs provisioned power and cooling CAPACITY check from energisation onward.
- NetBox table export (CSV) as the default asset input, and an optional read-only pynetbox adapter that returns the same schema, tested against NetBox-shaped API responses.
- `assets/report.md` and `assets/readiness_matrix.png` outputs.
- Tests for each rule, the loaders and adapter, and a check that the README's Result block and the committed report match the code. ruff linting, CI on Python 3.11 and 3.12, LF line endings via `.gitattributes`.

[1.1.0]: https://github.com/alexc-hue/commissioning-readiness-gate/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/alexc-hue/commissioning-readiness-gate/releases/tag/v1.0.0
