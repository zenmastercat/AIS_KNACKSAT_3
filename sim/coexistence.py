"""
KNACKSAT-3 AIS (162 MHz) / UHF (401 MHz) coexistence on a 1U CubeSat.

Uses the antenna coupling from antenna_coupling_nec.py (results/coupling.json)
and evaluates the three ways the UHF transmitter can disturb the AIS receiver:

  1. BLOCKING   - the 401 MHz carrier compresses the AIS LNA / SDR front end.
                  Cure: 162 MHz SAW band-pass filters (frequency domain).
  2. IN-BAND NOISE - PA wideband noise that already sits at 162 MHz.  An AIS-side
                  SAW cannot remove it (it is in the AIS passband).
                  Cure: TX-side filter at the UHF output, or time-division.
  3. TIME-DIVISION cost - if AIS is blanked while UHF transmits, the share of AIS
                  messages lost and the effect on ship detection probability.

Plus the SAW passband thermal drift with LEO Doppler.

Outputs (results/): summary.json, budget table, fig_budget.png, fig_saw_thermal.png,
fig_timeline.png, fig_detection.png, coexistence_timeseries.csv
Run:  uv run python sim/coexistence.py
"""
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as P  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results")
os.makedirs(OUT, exist_ok=True)


def load_coupling():
    path = os.path.join(OUT, "coupling.json")
    if not os.path.exists(path):
        sys.exit("results/coupling.json missing - run sim/antenna_coupling_nec.py first")
    with open(path) as fh:
        c = json.load(fh)
    return {"C401": c["mc"]["C401_matched_dB"]["p95"],          # design value = 95th percentile
            "C401_med": c["mc"]["C401_matched_dB"]["median"],
            "C162": c["mc"]["S21_162_dB"]["p95"],
            "C162_med": c["mc"]["S21_162_dB"]["median"]}


# ---------------------------------------------------------------------------
# Receiver chain
# ---------------------------------------------------------------------------
def friis_nf_db(stages):
    """stages: list of (gain_dB, nf_dB). Passive loss L -> (-L, L)."""
    f_tot, g_acc = 0.0, 1.0
    for i, (g, nf) in enumerate(stages):
        f = P.db2lin(nf)
        f_tot = f if i == 0 else f_tot + (f - 1) / g_acc
        g_acc *= P.db2lin(g)
    return float(P.lin2db(f_tot))


ARCHS = {
    # name: (pre-LNA SAW, post-LNA SAW)
    "A0  no filter":            (False, False),
    "A1  LNA -> SAW":           (False, True),
    "A2  SAW -> LNA":           (True, False),
    "A3  SAW -> LNA -> SAW":    (True, True),
}


def chain(pre, post):
    st = [(-P.AIS_FEED_LOSS_DB, P.AIS_FEED_LOSS_DB)]
    if pre:
        st.append((-P.SAW_IL_DB, P.SAW_IL_DB))
    st.append((P.LNA_GAIN_DB, P.LNA_NF_DB))
    if post:
        st.append((-P.SAW_IL_DB, P.SAW_IL_DB))
    st.append((0.0, P.BACKEND_NF_DB))
    return friis_nf_db(st)


def noise_floor_dbm(nf_db):
    """Receiver noise floor referred to the antenna port, in the AIS noise bandwidth."""
    return P.K_BOLTZ_DBM_HZ + 10 * np.log10(P.AIS_NOISE_BW_HZ) + nf_db


def blocking_budget(cpl, board_iso_db):
    """401 MHz carrier level at LNA input and at SDR input for each architecture."""
    p_ant = P.UHF_TX_POWER_DBM - P.UHF_TX_FEED_LOSS_DB + cpl["C401"] - P.AIS_FEED_LOSS_DB
    p_board = P.UHF_TX_POWER_DBM - board_iso_db          # leaks in at the LNA input
    rows = []
    for name, (pre, post) in ARCHS.items():
        rej_pre = P.SAW_REJ_401_DB if pre else 0.0
        rej_post = P.SAW_REJ_401_DB if post else 0.0
        # total filter rejection that a real PCB can deliver is capped (bypass coupling)
        rej_total = min(rej_pre + rej_post, P.PCB_BYPASS_LIMIT_DB)
        lna_in = float(P.dbm_sum(p_ant - rej_pre, p_board))
        sdr_in = float(P.dbm_sum(p_ant - rej_total, p_board - rej_post) + P.LNA_GAIN_DB)
        nf = chain(pre, post)
        rows.append({
            "arch": name, "lna_in_dBm": lna_in, "sdr_in_dBm": sdr_in,
            "lna_limit_dBm": P.LNA_IP1DB_DBM - P.BLOCK_BACKOFF_DB,
            "sdr_limit_dBm": P.BACKEND_IP1DB_DBM - P.BLOCK_BACKOFF_DB,
            "lna_margin_dB": P.LNA_IP1DB_DBM - P.BLOCK_BACKOFF_DB - lna_in,
            "sdr_margin_dB": P.BACKEND_IP1DB_DBM - P.BLOCK_BACKOFF_DB - sdr_in,
            "NF_dB": nf, "noise_floor_dBm": float(noise_floor_dbm(nf)),
        })
    return {"p_carrier_at_ais_port_dBm": p_ant, "p_board_dBm": p_board, "rows": rows}


def inband_noise(cpl, nf_db, tx_noise_dbc_hz=P.UHF_TX_NOISE_DBC_HZ, tx_filter_db=0.0, c162=None):
    """UHF PA noise that lands inside the AIS channel (cannot be removed by the AIS SAW)."""
    c162 = cpl["C162"] if c162 is None else c162
    n_tx = P.UHF_TX_POWER_DBM + tx_noise_dbc_hz + 10 * np.log10(P.AIS_NOISE_BW_HZ)   # at TX port
    i_ant = n_tx - tx_filter_db + c162 - P.AIS_FEED_LOSS_DB                           # at AIS port
    n_floor = noise_floor_dbm(nf_db) - P.AIS_FEED_LOSS_DB * 0  # floor already referred to antenna port
    i_over_n = i_ant - n_floor
    desense = 10 * np.log10(1 + P.db2lin(i_over_n))
    # TX-filter rejection needed for <= DESENSE_ALLOWED_DB
    i_n_allowed = P.lin2db(P.db2lin(P.DESENSE_ALLOWED_DB) - 1)
    need = max(0.0, float(i_ant + tx_filter_db - n_floor - i_n_allowed))
    return {"I_at_ais_port_dBm": float(i_ant), "noise_floor_dBm": float(n_floor),
            "I_over_N_dB": float(i_over_n), "desense_dB": float(desense),
            "tx_filter_needed_dB": need}


# ---------------------------------------------------------------------------
# SAW thermal drift vs AIS channels + Doppler
# ---------------------------------------------------------------------------
def saw_center_mhz(temp_c, material):
    if material == "quartz":
        ppm = P.TCF_QUARTZ_PPM_C2 * (np.asarray(temp_c) - 25.0) ** 2
    else:
        ppm = P.TCF_LITAO3_PPM_C * (np.asarray(temp_c) - 25.0)
    return P.F_AIS_MHZ * (1 + ppm * 1e-6)


def saw_loss_db(f_mhz, fc_mhz):
    x = (np.asarray(f_mhz) - fc_mhz) / (P.SAW_BW3_MHZ / 2)
    return P.SAW_IL_DB + 10 * np.log10(1 + x ** (2 * P.SAW_ORDER))


def saw_worst_extra_loss(temp_c, material):
    fc = saw_center_mhz(temp_c, material)
    worst = 0.0
    for ch in P.AIS_CHANNELS_MHZ:
        for dop in (-P.AIS_DOPPLER_KHZ, P.AIS_DOPPLER_KHZ):
            worst = np.maximum(worst, saw_loss_db(ch + dop / 1000, fc) - P.SAW_IL_DB)
    return worst


# ---------------------------------------------------------------------------
# Time-division (blanking) model
# ---------------------------------------------------------------------------
def packet_s():
    return P.UHF_PACKET_BYTES * 8 / P.UHF_BITRATE_BPS


def loss_fraction(burst_s, period_s):
    """Share of AIS messages lost when AIS is blanked during each UHF burst."""
    win = burst_s + P.TX_RAMP_GUARD_S + P.LNA_RECOVERY_S + P.AIS_SLOT_S
    return min(1.0, win / period_s)


def tdma_summary():
    tp = packet_s()
    beacon = loss_fraction(tp, P.UHF_BEACON_PERIOD_S)
    pass_period = tp / P.UHF_PASS_DOWNLINK_DUTY
    in_pass = loss_fraction(tp, pass_period)
    pass_time = P.UHF_PASSES_PER_DAY * P.UHF_PASS_LENGTH_S
    daily = (pass_time * in_pass + (86400 - pass_time) * beacon) / 86400
    return {"packet_s": tp, "loss_beacon_only": beacon, "loss_during_pass": in_pass,
            "loss_daily_average": daily, "uhf_tx_time_per_day_s": pass_time * P.UHF_PASS_DOWNLINK_DUTY
            + (86400 - pass_time) / P.UHF_BEACON_PERIOD_S * tp}


def detection_probability(loss, p_msg, n_reports):
    return 1 - (1 - p_msg * (1 - loss)) ** n_reports


def timeline(cpl, budget, window_s=120.0, dt=0.001, pass_start_s=60.0, seed=7):
    """Time-domain run: beacon, then a ground-station pass starts. AIS msgs are random."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, window_s, dt)
    tp = packet_s()
    tx = np.zeros_like(t, dtype=bool)
    starts = list(np.arange(5.0, pass_start_s, P.UHF_BEACON_PERIOD_S))
    starts += list(np.arange(pass_start_s, window_s, tp / P.UHF_PASS_DOWNLINK_DUTY))
    for s in starts:
        tx |= (t >= s) & (t < s + tp)
    blank = np.zeros_like(tx)
    for s in starts:
        blank |= (t >= s - P.TX_RAMP_GUARD_S) & (t < s + tp + P.LNA_RECOVERY_S)

    # orbit thermal swing (slow) for SAW drift
    temp = np.mean(P.T_ORBIT_RANGE_C) + np.ptp(P.T_ORBIT_RANGE_C) / 2 * np.sin(2 * np.pi * t / P.ORBIT_PERIOD_S)
    saw_extra = saw_worst_extra_loss(temp, "quartz")

    a3 = next(r for r in budget["rows"] if r["arch"].startswith("A3"))
    a0 = next(r for r in budget["rows"] if r["arch"].startswith("A0"))
    floor = a3["noise_floor_dBm"]
    i_nof = inband_noise(cpl, a3["NF_dB"])["I_at_ais_port_dBm"]
    i_filt = inband_noise(cpl, a3["NF_dB"], tx_filter_db=P.UHF_TX_HPF_REJ_162_DB)["I_at_ais_port_dBm"]
    carrier_unmit = np.where(tx, a0["lna_in_dBm"], np.nan)
    carrier_saw = np.where(tx, a3["sdr_in_dBm"], np.nan)
    desense_nofilter = np.where(tx, 10 * np.log10(1 + P.db2lin(i_nof - floor)), 0.0)
    desense_txfilter = np.where(tx, 10 * np.log10(1 + P.db2lin(i_filt - floor)), 0.0)

    # AIS messages: Poisson arrivals, each occupies one slot
    rate = 40.0
    n = rng.poisson(rate * window_s)
    m_t = np.sort(rng.uniform(0, window_s - P.AIS_SLOT_S, n))
    idx0 = (m_t / dt).astype(int)
    idx1 = ((m_t + P.AIS_SLOT_S) / dt).astype(int)
    cs = np.concatenate([[0], np.cumsum(blank)])
    hit = (cs[idx1] - cs[idx0]) > 0
    return {"t": t, "tx": tx, "blank": blank, "temp": temp, "saw_extra": saw_extra,
            "carrier_unmit": carrier_unmit, "carrier_saw_sdr": carrier_saw,
            "desense_nofilter": desense_nofilter, "desense_txfilter": desense_txfilter,
            "msg_t": m_t, "msg_lost": hit, "floor": floor}


# ---------------------------------------------------------------------------
def main():
    cpl = load_coupling()
    b_nocan = blocking_budget(cpl, P.BOARD_ISO_NO_CAN_DB)
    b_can = blocking_budget(cpl, P.BOARD_ISO_CAN_DB)
    a3 = next(r for r in b_can["rows"] if r["arch"].startswith("A3"))
    noise = {"no_tx_filter": inband_noise(cpl, a3["NF_dB"]),
             "with_tx_filter": inband_noise(cpl, a3["NF_dB"], tx_filter_db=P.UHF_TX_HPF_REJ_162_DB)}
    sweep_noise = {str(d): inband_noise(cpl, a3["NF_dB"], tx_noise_dbc_hz=d)["tx_filter_needed_dB"]
                   for d in (-130, -140, -150, -160, -170)}
    tdma = tdma_summary()
    thermal = {m: {"extra_loss_qual_worst_dB": float(max(saw_worst_extra_loss(T, m) for T in np.linspace(*P.T_QUAL_RANGE_C, 126))),
                   "shift_qual_worst_kHz": float(max(abs(saw_center_mhz(T, m) - P.F_AIS_MHZ) * 1e3 for T in P.T_QUAL_RANGE_C))}
               for m in ("quartz", "litao3")}
    det = {f"p_msg={p}": {f"loss={l:.2f}": detection_probability(l, p, 60) for l in (0.0, tdma["loss_daily_average"], 0.1, 0.5)}
           for p in (0.01, 0.05, 0.2)}
    old = {"old_fspl_isolation_dB": 20 * np.log10(np.hypot(0.1, 0.3)) + 20 * np.log10(401) - 27.55,
           "old_total_isolation_dB": 20 * np.log10(np.hypot(0.1, 0.3)) + 20 * np.log10(401) - 27.55 + 25 + 15 + 90,
           "old_saw_detune_loss_max_dB": 0.005 * (162e6 * -40e-6 * (-40 - 25) / 1000 + 3) ** 2}
    summary = {"coupling_design_values": cpl, "blocking_no_cans": b_nocan, "blocking_with_cans": b_can,
               "inband_tx_noise": noise, "tx_filter_needed_vs_tx_noise_dBc_Hz": sweep_noise,
               "time_division": tdma, "saw_thermal": thermal, "detection_probability_60_reports": det,
               "orbit_period_s": P.ORBIT_PERIOD_S, "old_sim_numbers": old}
    with open(os.path.join(OUT, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1, default=float)

    print(f"Design coupling (p95): 401 MHz {cpl['C401']:.1f} dB, 162 MHz {cpl['C162']:.1f} dB")
    print(f"401 MHz carrier at AIS antenna port: {b_can['p_carrier_at_ais_port_dBm']:.1f} dBm")
    for lbl, b in (("no shielding cans", b_nocan), ("with shielding cans", b_can)):
        print(f"-- blocking, {lbl}")
        for r in b["rows"]:
            print(f"  {r['arch']:<24} LNA in {r['lna_in_dBm']:6.1f} dBm (margin {r['lna_margin_dB']:6.1f})"
                  f" | SDR in {r['sdr_in_dBm']:6.1f} dBm (margin {r['sdr_margin_dB']:6.1f}) | NF {r['NF_dB']:.2f} dB")
    for k, v in noise.items():
        print(f"in-band TX noise, {k}: I={v['I_at_ais_port_dBm']:.1f} dBm, N={v['noise_floor_dBm']:.1f}, "
              f"I/N={v['I_over_N_dB']:.1f} dB, desense {v['desense_dB']:.1f} dB, TX filter needed {v['tx_filter_needed_dB']:.1f} dB")
    print("TX filter needed vs PA noise:", {k: round(v, 1) for k, v in sweep_noise.items()})
    print("time-division:", {k: round(v, 4) for k, v in tdma.items()})
    print("SAW thermal:", thermal)
    print("detection prob:", json.dumps(det, indent=0))
    print("old sim numbers:", old)

    tl = timeline(cpl, b_can)
    write_csv(tl)
    plots(b_nocan, b_can, noise, tl, tdma)
    lost = tl["msg_lost"]
    print(f"timeline: {lost.sum()} of {lost.size} AIS messages overlapped blanking ({100*lost.mean():.1f} %)")


def write_csv(tl):
    path = os.path.join(OUT, "coexistence_timeseries.csv")
    step = 10                                  # 10 ms rows
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time_s", "uhf_tx_active", "ais_blanked", "board_temp_C", "saw_extra_loss_dB",
                    "carrier_401_at_LNA_unfiltered_dBm", "carrier_401_at_SDR_SAW_LNA_SAW_dBm",
                    "inband_desense_no_txfilter_dB", "inband_desense_with_txfilter_dB"])
        for i in range(0, tl["t"].size, step):
            w.writerow([round(tl["t"][i], 3), int(tl["tx"][i]), int(tl["blank"][i]), round(tl["temp"][i], 2),
                        round(float(tl["saw_extra"][i]), 4),
                        "" if np.isnan(tl["carrier_unmit"][i]) else round(tl["carrier_unmit"][i], 2),
                        "" if np.isnan(tl["carrier_saw_sdr"][i]) else round(tl["carrier_saw_sdr"][i], 2),
                        round(tl["desense_nofilter"][i], 2), round(tl["desense_txfilter"][i], 2)])


def plots(b_nocan, b_can, noise, tl, tdma):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # --- budget -------------------------------------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.3))
    names = [r["arch"] for r in b_can["rows"]]
    x = np.arange(len(names))
    for off, b, lbl, col in ((-0.2, b_nocan, "no shielding cans", "0.65"), (0.2, b_can, "with shielding cans", "0.3")):
        axs[0].bar(x + off, [r["lna_in_dBm"] for r in b["rows"]], 0.38, color=col, label=f"LNA input, {lbl}", bottom=0)
    axs[0].axhline(b_can["rows"][0]["lna_limit_dBm"], color="tab:red", ls="--", label="LNA limit (IP1dB - 10 dB)")
    axs[0].scatter(x, [r["sdr_in_dBm"] for r in b_can["rows"]], color="tab:blue", zorder=3, label="SDR input (with cans)")
    axs[0].axhline(b_can["rows"][0]["sdr_limit_dBm"], color="tab:blue", ls=":", label="SDR limit (IP1dB - 10 dB)")
    axs[0].set_xticks(x, names, rotation=15, fontsize=8)
    axs[0].set_ylabel("401 MHz carrier level [dBm]"); axs[0].set_ylim(-80, 25)
    axs[0].set_title("Blocking: 401 MHz carrier in the AIS chain", fontsize=10)
    axs[0].legend(fontsize=7, loc="upper right"); axs[0].grid(ls=":", axis="y")

    labels = ["no TX filter", f"TX filter {P.UHF_TX_HPF_REJ_162_DB:.0f} dB", "time-division\n(AIS blanked)"]
    vals = [noise["no_tx_filter"]["I_over_N_dB"], noise["with_tx_filter"]["I_over_N_dB"], np.nan]
    axs[1].bar(range(3), [v if np.isfinite(v) else 0 for v in vals], color=["tab:red", "tab:green", "0.8"])
    axs[1].text(2, 2, "no reception\nduring TX:\nnothing to desense", ha="center", fontsize=8)
    axs[1].axhline(P.lin2db(P.db2lin(P.DESENSE_ALLOWED_DB) - 1), color="k", ls="--", label="I/N for 1 dB desense")
    for i, v in enumerate(vals[:2]):
        axs[1].text(i, v + 1, f"desense {10*np.log10(1+P.db2lin(v)):.1f} dB", ha="center", fontsize=8)
    axs[1].set_xticks(range(3), labels, fontsize=8)
    axs[1].set_ylabel("UHF PA noise / AIS noise floor, I/N [dB]")
    axs[1].set_title("In-band UHF noise at 162 MHz (SAW cannot remove)", fontsize=10)
    axs[1].legend(fontsize=8); axs[1].grid(ls=":", axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_budget.png"), dpi=200); plt.close(fig)

    # --- SAW thermal --------------------------------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    f = np.linspace(160.5, 163.5, 800)
    for T, ls in ((-40, ":"), (25, "-"), (85, "--")):
        axs[0].plot(f, -saw_loss_db(f, saw_center_mhz(T, "litao3")), color="tab:orange", ls=ls, label=f"LiTaO3 SAW {T} C")
        axs[0].plot(f, -saw_loss_db(f, saw_center_mhz(T, "quartz")), color="tab:blue", ls=ls, label=f"quartz SAW {T} C")
    for ch in P.AIS_CHANNELS_MHZ:
        axs[0].axvspan(ch - 0.0125 - P.AIS_DOPPLER_KHZ / 1e3, ch + 0.0125 + P.AIS_DOPPLER_KHZ / 1e3, color="tab:green", alpha=0.3)
    axs[0].set_xlabel("Frequency [MHz]"); axs[0].set_ylabel("|H| [dB]"); axs[0].set_ylim(-20, 0)
    axs[0].set_title("SAW passband drift (green = AIS 1/2 + Doppler)", fontsize=10)
    axs[0].legend(fontsize=7); axs[0].grid(ls=":")
    T = np.linspace(*P.T_QUAL_RANGE_C, 200)
    axs[1].plot(T, [saw_worst_extra_loss(x, "litao3") for x in T], color="tab:orange", label="LiTaO3 (-32 ppm/C)")
    axs[1].plot(T, [saw_worst_extra_loss(x, "quartz") for x in T], color="tab:blue", label="ST-quartz (parabolic)")
    axs[1].axvspan(*P.T_ORBIT_RANGE_C, color="0.9", label="assumed orbit range")
    axs[1].set_xlabel("SAW temperature [C]"); axs[1].set_ylabel("extra in-band loss, worst channel+Doppler [dB]")
    axs[1].set_title("Effect on wanted AIS signal (rejection at 401 MHz unchanged)", fontsize=10)
    axs[1].legend(fontsize=8); axs[1].grid(ls=":")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_saw_thermal.png"), dpi=200); plt.close(fig)

    # --- timeline -----------------------------------------------------------
    fig, axs = plt.subplots(3, 1, figsize=(11, 7.5), sharex=True)
    t = tl["t"]
    axs[0].plot(t, tl["carrier_unmit"], color="crimson", label="401 MHz carrier at LNA, no filter (A0)")
    axs[0].plot(t, tl["carrier_saw_sdr"], color="forestgreen", lw=2, label="401 MHz carrier at SDR, SAW->LNA->SAW (A3)")
    axs[0].axhline(P.LNA_IP1DB_DBM - P.BLOCK_BACKOFF_DB, color="crimson", ls="--", lw=1, label="LNA limit")
    axs[0].axhline(P.BACKEND_IP1DB_DBM - P.BLOCK_BACKOFF_DB, color="forestgreen", ls="--", lw=1, label="SDR limit")
    axs[0].set_ylabel("dBm"); axs[0].set_ylim(-70, 10); axs[0].legend(fontsize=7, loc="lower left", ncol=2)
    axs[0].set_title("Blocking: only present while UHF transmits (gaps = UHF off, no interference)", fontsize=10)
    axs[1].plot(t, tl["desense_nofilter"], color="crimson", label="in-band desense, no TX filter")
    axs[1].plot(t, tl["desense_txfilter"], color="forestgreen", lw=2, label=f"with {P.UHF_TX_HPF_REJ_162_DB:.0f} dB TX filter")
    axs[1].set_ylabel("desense [dB]"); axs[1].legend(fontsize=7, loc="upper left")
    axs[1].set_title("In-band UHF noise at 162 MHz (this is what time-division removes)", fontsize=10)
    axs[2].fill_between(t, 0, tl["blank"].astype(float), step="post", color="0.8", label="AIS blanked (TX + guards)")
    ok = ~tl["msg_lost"]
    axs[2].plot(tl["msg_t"][ok], np.full(ok.sum(), 0.5), "|", color="tab:blue", ms=10, label="AIS msg received")
    axs[2].plot(tl["msg_t"][~ok], np.full((~ok).sum(), 0.5), "x", color="tab:red", ms=6, label="AIS msg lost")
    axs[2].set_yticks([]); axs[2].set_xlabel("time [s]  (beacon every 30 s, ground pass from 60 s)")
    axs[2].legend(fontsize=7, loc="upper left", ncol=3)
    axs[2].set_title(f"Time-division: {100*tl['msg_lost'].mean():.1f} % of messages lost in this window "
                     f"(daily average {100*tdma['loss_daily_average']:.1f} %)", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_timeline.png"), dpi=200); plt.close(fig)

    # --- detection ----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 4))
    L = np.linspace(0, 0.8, 100)
    for p in (0.01, 0.05, 0.2):
        ax.plot(100 * L, 100 * detection_probability(L, p, 60), label=f"per-message success {p:.0%}")
    ax.axvline(100 * tdma["loss_daily_average"], color="k", ls="--", label="KNACKSAT-3 daily average loss")
    ax.axvline(100 * tdma["loss_during_pass"], color="0.5", ls=":", label="loss during a ground pass")
    ax.set_xlabel("AIS messages lost to blanking [%]"); ax.set_ylabel("P(ship detected in one pass) [%]")
    ax.set_title("Ship detection vs time-division loss (60 reports per pass)", fontsize=10)
    ax.grid(ls=":"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_detection.png"), dpi=200); plt.close(fig)


if __name__ == "__main__":
    main()
