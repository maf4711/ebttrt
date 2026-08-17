# ebttrl

Grok-native agent harness. Python 3.10+, stdlib only.

- Always-on rule stays under 30 lines (`rules/ebttrl-loop.md`).
- Skills load on demand. Do not grow the rule into a catalog.
- CLI: `ebttrl`, `ebttrl consult`, `ebttrl begin`, `ebttrl prove --record`, `ebttrl done`.
- Tests: `python3 tests/test_ebttrl.py`
- Validate: `grok plugin validate .`
- Never print secrets. Never run `security dump-keychain`.
- New Mac: copy `~/Developer/ebttrl`, then `python3 ~/Developer/ebttrl/scripts/ebttrl.py activate`.
- Thin re-link: `ebttrl install`. Full wiring (PATH, skill, Hoheit): `ebttrl activate`.
- Quality roadmap: `docs/ROADMAP.md`. Do not grow the skill catalog.
