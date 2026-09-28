# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and version numbers
follow [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-09-28

First release. Gives each data hall a ready / conditional / not-ready verdict, with reasons, for starting its next commissioning level, from NetBox assets, commissioning records, a punch list and a capacity figure. All sample data is synthetic.

### Included

- Commissioning levels (default L1 to L5) in `config/levels.yaml`, with strict sequencing: no level counts as closed while an earlier one on the same device is open, and IST (L5) can't start until every device's L4 is closed and signed.
- Gate rules: SEQUENCE, PREREQ, WAIVED (waivers off by default, never better than conditional), PUNCH_A/B/C, and a design-load vs provisioned power and cooling CAPACITY check from energisation onward.
- NetBox table export (CSV) as the default asset input, and an optional read-only pynetbox adapter that returns the same schema, tested against NetBox-shaped API responses.
- `assets/report.md` and `assets/readiness_matrix.png` outputs.
- Tests for each rule, the loaders and adapter, and a check that the README's Result block and the committed report match the code. ruff linting, CI on Python 3.11 and 3.12, LF line endings via `.gitattributes`.

[1.0.0]: https://github.com/alexc-hue/commissioning-readiness-gate/releases/tag/v1.0.0
