"""
simsim.py - CORRECTED in v0.2 (KNACKSAT-3 AIS 162 MHz / UHF 401 MHz coexistence)

The original version of this script (see git history, commit 910f6ae) had these
errors; all are fixed in sim/coexistence.py, which this file now runs:
  1. Geometry was a 3U (0.1 x 0.3 m); KNACKSAT-3 is a 1U.
  2. Free-space path loss was used at 0.32 m, which is inside the near field at
     401 MHz (lambda = 0.75 m) and gives 14.5 dB "isolation"; it also ignored
     antenna gain and the satellite body.  -> replaced by a NEC-2 MoM model.
  3. Cross-pol (25 dB) + shielding (15 dB) + SAW (90 dB) were added in series.
     Cross-pol is part of the antenna coupling (now computed); shielding cans act
     on a separate board-leakage path (added in parallel, in watts); 90 dB is not
     realistic for one SAW (datasheets: ~38-42 dB at 400 MHz, PCB bypass caps it).
  4. SAW thermal "detune loss" 0.005*(df)^2 reached ~900 dB at -40 C and was
     subtracted from the stop-band rejection, which made the "mitigated" curve
     shoot to +700 dBm.  Thermal drift (~0.02-0.4 MHz) moves the passband, it does
     not change rejection 239 MHz away; it only adds a little in-band loss.
  5. Time-division was inverted: during UHF TX the plot showed the noise floor,
     and during UHF OFF it showed TX leakage.  With UHF off there is no leakage.
  6. Desense used the out-of-band 401 MHz carrier as if it were in-band noise
     (150 dB "desense").  Blocking and in-band noise are separate mechanisms.
  7. Gaussian "space fading" every 10 ms: near-field coupling on a rigid
     structure is quasi-static; variation now comes from deployment tolerances.
  8. Thermal cycle of 10 s and Doppler of 20 s; LEO orbit is ~95 min.

Outputs kept under their old names: cubesat_rf_sim_results.csv, cubesat_rf_sim_plot.png
Run:  uv run python sim/antenna_coupling_nec.py   (once, ~1-2 min)
      uv run python simsim.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sim"))
import coexistence  # noqa: E402

if __name__ == "__main__":
    coexistence.main()
    shutil.copy(os.path.join(HERE, "results", "coexistence_timeseries.csv"),
                os.path.join(HERE, "cubesat_rf_sim_results.csv"))
    shutil.copy(os.path.join(HERE, "results", "fig_timeline.png"),
                os.path.join(HERE, "cubesat_rf_sim_plot.png"))
    print("Wrote cubesat_rf_sim_results.csv and cubesat_rf_sim_plot.png")
