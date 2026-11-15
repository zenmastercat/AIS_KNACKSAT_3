"""
Antenna-to-antenna coupling between the AIS (162 MHz) and UHF (401 MHz)
dipoles on a 1U CubeSat, computed with the NEC-2 method of moments (PyNEC).

Model
  * 1U body (100 x 100 x 113.5 mm) as a conducting wire grid.
  * 4 deployable tape elements on the +Z face, forming two crossed dipoles:
      AIS dipole along X, UHF dipole along Y (perpendicular).
    Each dipole is centre-fed across the top face; feed lines cross 3 mm apart.
  * Two-port Y-parameters (each port shorted in turn) -> S-parameters (50 ohm).
  * Element lengths tuned so each dipole is resonant (X = 0) with the body present.
  * Monte Carlo over deployment tolerances, because a perfectly symmetric
    crossed pair is (numerically) almost perfectly isolated, which real
    hardware never is.

Outputs: results/coupling.json, results/fig_coupling_sweep.png,
         results/fig_coupling_mc.png, results/fig_geometry.png
Run:  uv run python sim/antenna_coupling_nec.py
"""
import json
import os
import sys

import numpy as np
from PyNEC import nec_context

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as P  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
os.makedirs(OUT, exist_ok=True)

TAG_AIS_FEED, TAG_UHF_FEED = 1, 2
FEED_SEGS = 7                      # odd -> centre segment carries the port
FEED_SEG = FEED_SEGS // 2 + 1
GRID_TAG0 = 100


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def box_grid_wires():
    """Unique edges of an N x N x N lattice that lie on the 1U surface."""
    n = P.GRID_DIV
    xs = np.linspace(-P.SAT_X / 2, P.SAT_X / 2, n + 1)
    ys = np.linspace(-P.SAT_Y / 2, P.SAT_Y / 2, n + 1)
    zs = np.linspace(0.0, P.SAT_Z, n + 1)
    on_surf = lambda i, j, k: i in (0, n) or j in (0, n) or k in (0, n)
    wires = []
    for i in range(n + 1):
        for j in range(n + 1):
            for k in range(n + 1):
                if not on_surf(i, j, k):
                    continue
                for di, dj, dk in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
                    a, b, c = i + di, j + dj, k + dk
                    if a > n or b > n or c > n or not on_surf(a, b, c):
                        continue
                    # edge must lie in a face: a coordinate shared at a boundary
                    shared = [(i, a), (j, b), (k, c)]
                    ok = any(p == q and p in (0, n) for (p, q), d in zip(shared, (di, dj, dk)) if d == 0)
                    if ok:
                        wires.append(((xs[i], ys[j], zs[k]), (xs[a], ys[b], zs[c])))
    return wires


def unit(az_deg, el_deg):
    az, el = np.radians(az_deg), np.radians(el_deg)
    return np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])


def antenna_wires(L_ais, L_uhf, pert=None):
    """Return list of (tag, segs, p1, p2) for both dipoles.

    pert: dict with 'ang' (4x2 array of az/el errors, deg) and 'off' (2x2 feed
    offsets, m) for the Monte Carlo; None = ideal geometry.
    """
    ang = np.zeros((4, 2)) if pert is None else pert["ang"]
    off = np.zeros((2, 2)) if pert is None else pert["off"]
    z_ais = P.SAT_Z + P.ANT_MODULE_HEIGHT
    z_uhf = z_ais + P.ANT_CROSS_OFFSET
    hx, hy = P.SAT_X / 2, P.SAT_Y / 2
    w = []
    # AIS dipole along X
    ox, oy = off[0]
    a0, a1 = np.array([-hx, oy, z_ais]), np.array([hx, oy, z_ais])
    a0[0] += ox; a1[0] += ox
    w.append((TAG_AIS_FEED, FEED_SEGS, a0, a1))
    nseg = max(9, int(L_ais / 0.015))
    w.append((3, nseg, a1, a1 + L_ais * unit(0 + ang[0, 0], ang[0, 1])))
    w.append((4, nseg, a0, a0 + L_ais * unit(180 + ang[1, 0], ang[1, 1])))
    # UHF dipole along Y
    ox, oy = off[1]
    u0, u1 = np.array([ox, -hy, z_uhf]), np.array([ox, hy, z_uhf])
    u0[1] += oy; u1[1] += oy
    w.append((TAG_UHF_FEED, FEED_SEGS, u0, u1))
    nseg = max(7, int(L_uhf / 0.012))
    w.append((5, nseg, u1, u1 + L_uhf * unit(90 + ang[2, 0], ang[2, 1])))
    w.append((6, nseg, u0, u0 + L_uhf * unit(270 + ang[3, 0], ang[3, 1])))
    return w


def build(ctx, ant, with_body=True):
    g = ctx.get_geometry()
    for tag, segs, p1, p2 in ant:
        g.wire(tag, segs, *p1, *p2, P.TAPE_EQ_RADIUS, 1.0, 1.0)
    if with_body:
        for i, (p1, p2) in enumerate(box_grid_wires()):
            g.wire(GRID_TAG0 + i, 1, *p1, *p2, 0.001, 1.0, 1.0)
    ctx.geometry_complete(0)


def feed_currents(ctx):
    sc = ctx.get_structure_currents(0)
    cur, tags, segn = sc.get_current(), sc.get_current_segment_tag(), sc.get_current_segment_number()
    out, count = {}, {}
    for c, t in zip(cur, tags):           # segment numbers are global; count within each tag
        t = int(t)
        count[t] = count.get(t, 0) + 1
        if count[t] == FEED_SEG and t in (TAG_AIS_FEED, TAG_UHF_FEED):
            out[t] = complex(c)
    return out


def y_params(ant, f_mhz, with_body=True):
    """2x2 short-circuit admittance matrix, port 1 = AIS, port 2 = UHF."""
    Y = np.zeros((2, 2), complex)
    for col, tag in enumerate((TAG_AIS_FEED, TAG_UHF_FEED)):
        ctx = nec_context()
        build(ctx, ant, with_body)
        ctx.gn_card(-1, 0, 0, 0, 0, 0, 0, 0)               # free space
        ctx.ex_card(0, tag, FEED_SEG, 0, 1.0, 0, 0, 0, 0, 0)
        ctx.fr_card(0, 1, f_mhz, 0)
        ctx.xq_card(0)
        i = feed_currents(ctx)
        Y[0, col] = i[TAG_AIS_FEED]
        Y[1, col] = i[TAG_UHF_FEED]
    return Y


def s_params(Y, z0=50.0):
    I = np.eye(2)
    return (I - z0 * Y) @ np.linalg.inv(I + z0 * Y)


def coupling_metrics(ant, f_mhz):
    Y = y_params(ant, f_mhz)
    S = s_params(Y)
    Z = np.linalg.inv(Y)
    s21 = abs(S[0, 1]) ** 2                      # UHF port -> AIS port, both 50 ohm
    # UHF port matched by a lossless network at its own frequency -> coupling
    # relative to power accepted by the UHF antenna
    accepted = s21 / max(1e-30, 1 - abs(S[1, 1]) ** 2)
    return {"f_mhz": f_mhz, "S21_dB": 10 * np.log10(s21), "C_matched_dB": 10 * np.log10(accepted),
            "Z_ais": [Z[0, 0].real, Z[0, 0].imag], "Z_uhf": [Z[1, 1].real, Z[1, 1].imag]}


# ---------------------------------------------------------------------------
# Element tuning (resonance with body present)
# ---------------------------------------------------------------------------
def self_reactance(L_ais, L_uhf, f_mhz, port):
    Z = np.linalg.inv(y_params(antenna_wires(L_ais, L_uhf), f_mhz))
    return Z[port, port].imag


def tune():
    lam_a = P.C0 / (P.F_AIS_MHZ * 1e6)
    lam_u = P.C0 / (P.F_UHF_MHZ * 1e6)
    # start: half-wave total minus the 100 mm feed section
    La = 0.95 * lam_a / 2 / 2 - P.SAT_X / 2
    Lu = 0.95 * lam_u / 2 / 2 - P.SAT_Y / 2
    for _ in range(3):                                  # alternate (they interact slightly)
        La = secant(lambda L: self_reactance(L, Lu, P.F_AIS_MHZ, 0), La)
        Lu = secant(lambda L: self_reactance(La, L, P.F_UHF_MHZ, 1), Lu)
    return La, Lu


def secant(fun, x0, tol=1e-4):
    x1 = x0 * 1.03
    f0, f1 = fun(x0), fun(x1)
    for _ in range(25):
        if abs(f1 - f0) < 1e-12:
            break
        x2 = x1 - f1 * (x1 - x0) / (f1 - f0)
        x0, f0, x1 = x1, f1, x2
        f1 = fun(x1)
        if abs(x1 - x0) < tol:
            break
    return x1


# ---------------------------------------------------------------------------
def main():
    rng = np.random.default_rng(1)
    print("Tuning elements with the 1U body present ...")
    La, Lu = tune()
    ant0 = antenna_wires(La, Lu)
    nom = {f: coupling_metrics(ant0, f) for f in (P.F_AIS_MHZ, P.F_UHF_MHZ)}
    print(f"  AIS element {La*1000:.0f} mm, UHF element {Lu*1000:.0f} mm")
    for f, m in nom.items():
        print(f"  nominal @ {f} MHz: S21 {m['S21_dB']:.1f} dB, Z_ais {m['Z_ais']}, Z_uhf {m['Z_uhf']}")

    # Frequency sweep: nominal geometry + envelope over SWEEP_MC perturbed deployments
    SWEEP_MC = 40
    perts = [{"ang": rng.normal(0, P.TOL_ELEMENT_ANGLE_DEG, (4, 2)),
              "off": rng.normal(0, P.TOL_FEED_OFFSET_M, (2, 2))} for _ in range(SWEEP_MC)]
    pert_example = perts[0]
    ants = [antenna_wires(La, Lu, p) for p in perts]
    freqs = np.arange(100, 501, 10.0)
    sweep = {"f": freqs.tolist(), "S21_nom": [], "S21_med": [], "S21_max": [], "S11_ais": [], "S22_uhf": [],
             "mc_samples": SWEEP_MC}
    for f in freqs:
        S0 = s_params(y_params(ant0, f))
        s21 = [20 * np.log10(abs(s_params(y_params(a, f))[0, 1])) for a in ants]
        sweep["S21_nom"].append(20 * np.log10(max(abs(S0[0, 1]), 1e-15)))
        sweep["S21_med"].append(float(np.median(s21)))
        sweep["S21_max"].append(float(np.max(s21)))
        sweep["S11_ais"].append(20 * np.log10(abs(S0[0, 0])))
        sweep["S22_uhf"].append(20 * np.log10(abs(S0[1, 1])))

    # Monte Carlo of deployment tolerances
    print(f"Monte Carlo ({P.MC_RUNS} runs) ...")
    mc = {"C401_matched_dB": [], "S21_162_dB": []}
    for _ in range(P.MC_RUNS):
        pert = {"ang": rng.normal(0, P.TOL_ELEMENT_ANGLE_DEG, (4, 2)),
                "off": rng.normal(0, P.TOL_FEED_OFFSET_M, (2, 2))}
        ant = antenna_wires(La, Lu, pert)
        mc["C401_matched_dB"].append(coupling_metrics(ant, P.F_UHF_MHZ)["C_matched_dB"])
        mc["S21_162_dB"].append(coupling_metrics(ant, P.F_AIS_MHZ)["S21_dB"])
    c401 = np.array(mc["C401_matched_dB"]); c162 = np.array(mc["S21_162_dB"])

    # Sensitivity of the 95th-percentile coupling to the deployment tolerance
    sens = {}
    for sig in (1.0, 3.0, 6.0, 10.0):
        a, b = [], []
        for _ in range(60):
            pert = {"ang": rng.normal(0, sig, (4, 2)), "off": rng.normal(0, P.TOL_FEED_OFFSET_M, (2, 2))}
            ant = antenna_wires(La, Lu, pert)
            a.append(coupling_metrics(ant, P.F_UHF_MHZ)["C_matched_dB"])
            b.append(coupling_metrics(ant, P.F_AIS_MHZ)["S21_dB"])
        sens[str(sig)] = {"C401_p95": float(np.percentile(a, 95)), "S21_162_p95": float(np.percentile(b, 95))}
    print("tolerance sensitivity:", sens)
    summary = {
        "element_length_ais_m": La, "element_length_uhf_m": Lu,
        "nominal": {str(k): v for k, v in nom.items()},
        "mc": {"runs": P.MC_RUNS, "angle_sigma_deg": P.TOL_ELEMENT_ANGLE_DEG,
               "C401_matched_dB": {"median": float(np.median(c401)), "p95": float(np.percentile(c401, 95)),
                                   "max": float(c401.max())},
               "S21_162_dB": {"median": float(np.median(c162)), "p95": float(np.percentile(c162, 95)),
                              "max": float(c162.max())}},
        "tolerance_sensitivity": sens,
        "fspl_formula_old_sim_dB": float(20 * np.log10(np.hypot(0.1, 0.3)) + 20 * np.log10(401) - 27.55),
        "sweep": sweep, "mc_raw": mc,
    }
    with open(os.path.join(OUT, "coupling.json"), "w") as fh:
        json.dump(summary, fh, indent=1, default=float)
    print(json.dumps({k: summary[k] for k in ("element_length_ais_m", "element_length_uhf_m", "mc",
                                               "fspl_formula_old_sim_dB")}, indent=1))
    plots(summary, ant0, pert_example, La, Lu)


def plots(s, ant0, pert, La, Lu):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # geometry
    fig = plt.figure(figsize=(6, 5.5))
    ax = fig.add_subplot(projection="3d")
    for p1, p2 in box_grid_wires():
        ax.plot(*zip(p1, p2), color="0.6", lw=0.7)
    for tag, _, p1, p2 in ant0:
        col = "tab:blue" if tag in (1, 3, 4) else "tab:red"
        ax.plot(*zip(p1, p2), color=col, lw=2.5)
    ax.plot([], [], color="tab:blue", lw=2.5, label=f"AIS dipole, 162 MHz (2 x {La*1000:.0f} mm)")
    ax.plot([], [], color="tab:red", lw=2.5, label=f"UHF dipole, 401 MHz (2 x {Lu*1000:.0f} mm)")
    lim = La + 0.06
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_zlim(-0.1, 0.4)
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.set_zlabel("z [m]")
    ax.set_title("NEC-2 model: 1U body + crossed AIS/UHF dipoles")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_geometry.png"), dpi=200); plt.close(fig)

    sw = s["sweep"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(sw["f"], sw["S21_max"], color="k", label=f"|S21| AIS<->UHF, worst of {sw['mc_samples']} deployments")
    ax.plot(sw["f"], sw["S21_med"], color="0.5", ls="--", label="|S21| median deployment")
    ax.text(105, -86, "ideal (perfectly symmetric) geometry: |S21| < -150 dB, off scale", fontsize=8, color="0.4")
    ax.plot(sw["f"], sw["S11_ais"], color="tab:blue", label="|S11| AIS port (50 ohm, unmatched)")
    ax.plot(sw["f"], sw["S22_uhf"], color="tab:red", label="|S22| UHF port (50 ohm, unmatched)")
    for f in (P.F_AIS_MHZ, P.F_UHF_MHZ):
        ax.axvline(f, color="0.3", ls=":")
    ax.set_xlabel("Frequency [MHz]"); ax.set_ylabel("dB"); ax.set_ylim(-90, 2)
    ax.set_title("Antenna-port S-parameters on the 1U body (NEC-2)")
    ax.grid(ls=":"); ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_coupling_sweep.png"), dpi=200); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(9, 3.8))
    for ax, key, title in ((axs[0], "C401_matched_dB", "401 MHz carrier into AIS port\n(UHF port matched)"),
                           (axs[1], "S21_162_dB", "162 MHz (UHF TX noise) into AIS port\n|S21|, 50 ohm ports")):
        d = np.array(s["mc_raw"][key])
        ax.hist(d, bins=25, color="0.5")
        ax.axvline(np.percentile(d, 95), color="tab:red", label=f"95th pct {np.percentile(d,95):.1f} dB")
        ax.axvline(np.median(d), color="k", ls="--", label=f"median {np.median(d):.1f} dB")
        ax.set_title(title, fontsize=10); ax.set_xlabel("coupling [dB]"); ax.legend(fontsize=8)
    fig.suptitle(f"Monte Carlo, {s['mc']['runs']} deployments, element angle sigma {P.TOL_ELEMENT_ANGLE_DEG} deg",
                 fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_coupling_mc.png"), dpi=200); plt.close(fig)


if __name__ == "__main__":
    main()
