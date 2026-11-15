"""
sim-ais.py - CORRECTED in v0.2.

The original simple model (git history, commit 910f6ae) shared errors 1-3, 5 and 7
listed in simsim.py (3U geometry, free-space loss in the near field, isolations
stacked in series with a 90 dB SAW, inverted time-division plot, per-sample
random fading).  This script now prints the corrected link budget and draws the
budget figure (results/fig_budget.png) from sim/coexistence.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim"))
import coexistence  # noqa: E402

if __name__ == "__main__":
    coexistence.main()
