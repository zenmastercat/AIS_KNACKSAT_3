# AIS_KNACKSAT_3

Coexistence of the KNACKSAT-3 AIS receiver (162 MHz) and UHF transmitter (401 MHz)
on a 1U CubeSat with two perpendicular (crossed) dipoles - four deployable elements.

**Documentation:** [`docs/KNACKSAT3_AIS_UHF_Coexistence.docx`](docs/KNACKSAT3_AIS_UHF_Coexistence.docx)

## Run (uv, Python 3.13+)

```bash
uv run python sim/antenna_coupling_nec.py   # NEC-2 coupling model + Monte Carlo (~1-2 min)
uv run python sim/feed_sensitivity.py       # which geometry error sets the isolation
uv run python sim/coexistence.py            # blocking, in-band noise, SAW drift, time-division
uv run python docs/build_docx.py            # rebuild the report from results/
```

All inputs are in `sim/params.py`, tagged STD / DATASHEET / ASSUMED / CONFIRM.
`simsim.py` and `sim-ais.py` were corrected in v0.2 (see their headers and section 7 of the report);
the original code is in git history (commit 910f6ae). `simmFig.png` is an output of the old, incorrect model.
