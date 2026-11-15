"""
Which geometry error sets the AIS/UHF isolation?  Separates element pointing
errors from feed-point offset, for two vertical spacings of the crossing feed
lines on the antenna-module PCB (3 mm and 10 mm).
Needs results/coupling.json (run antenna_coupling_nec.py first).
Output: results/feed_sensitivity.json
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as P              # noqa: E402
import antenna_coupling_nec as A  # noqa: E402

OUT = A.OUT
c = json.load(open(os.path.join(OUT, "coupling.json")))
La, Lu = c["element_length_ais_m"], c["element_length_uhf_m"]
rng = np.random.default_rng(5)
cases = [("angle 3 deg only, feed crossing 3 mm", 3, 0, 0.003),
         ("feed offset 1 mm only, crossing 3 mm", 0, 0.001, 0.003),
         ("angle 3 deg + offset 1 mm, crossing 3 mm", 3, 0.001, 0.003),
         ("feed offset 1 mm only, crossing 10 mm", 0, 0.001, 0.010),
         ("angle 3 deg + offset 1 mm, crossing 10 mm", 3, 0.001, 0.010)]
res = {}
for label, sa, so, cross in cases:
    P.ANT_CROSS_OFFSET = cross
    a, b = [], []
    for _ in range(60):
        ant = A.antenna_wires(La, Lu, {"ang": rng.normal(0, sa, (4, 2)), "off": rng.normal(0, so, (2, 2))})
        a.append(A.coupling_metrics(ant, P.F_UHF_MHZ)["C_matched_dB"])
        b.append(A.coupling_metrics(ant, P.F_AIS_MHZ)["S21_dB"])
    res[label] = {"C401_p50": float(np.median(a)), "C401_p95": float(np.percentile(a, 95)),
                  "S21_162_p50": float(np.median(b)), "S21_162_p95": float(np.percentile(b, 95))}
    print(f"{label:44s} 401: p50 {res[label]['C401_p50']:6.1f} p95 {res[label]['C401_p95']:6.1f} | "
          f"162: p50 {res[label]['S21_162_p50']:6.1f} p95 {res[label]['S21_162_p95']:6.1f}")
json.dump(res, open(os.path.join(OUT, "feed_sensitivity.json"), "w"), indent=1)
