# ebttrt

Grok-native agent harness. Python 3.10+, stdlib only.

- Always-on rule stays under 30 lines (`rules/ebttrt-loop.md`).
- Skills load on demand. Do not grow the rule into a catalog.
- CLI: `ebttrt`, `ebttrt consult`, `ebttrt begin`, `ebttrt prove --record`, `ebttrt done`.
- Tests: `python3 tests/test_ebttrt.py`
- Validate: `grok plugin validate .`
- Never print secrets. Never run `security dump-keychain`.
- New Mac: copy `~/Developer/ebttrt`, then `python3 ~/Developer/ebttrt/scripts/ebttrt.py activate`.
- Thin re-link: `ebttrt install`. Full wiring (PATH, skill, Hoheit): `ebttrt activate`.
- Quality roadmap: `docs/ROADMAP.md`. Do not grow the skill catalog.
