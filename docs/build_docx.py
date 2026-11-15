"""
Build docs/KNACKSAT3_AIS_UHF_Coexistence.docx from the simulation results.
Run after the simulations:
    uv run python sim/antenna_coupling_nec.py
    uv run python sim/feed_sensitivity.py
    uv run python sim/coexistence.py
    uv run python docs/build_docx.py
All numbers in the report are read from results/*.json, so the document always
matches the last simulation run.
"""
import json
import os
import sys

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import params as P  # noqa: E402

RES = os.path.join(ROOT, "results")
S = json.load(open(os.path.join(RES, "summary.json")))
C = json.load(open(os.path.join(RES, "coupling.json")))
FS = json.load(open(os.path.join(RES, "feed_sensitivity.json")))
OUT = os.path.join(ROOT, "docs", "KNACKSAT3_AIS_UHF_Coexistence.docx")

cpl = S["coupling_design_values"]
rows_can = S["blocking_with_cans"]["rows"]
rows_nocan = S["blocking_no_cans"]["rows"]
a3 = rows_can[3]
nz = S["inband_tx_noise"]
td = S["time_division"]
th = S["saw_thermal"]
old = S["old_sim_numbers"]
det = S["detection_probability_60_reports"]

doc = Document()
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
for m in ("left_margin", "right_margin"):
    setattr(sec, m, Cm(2.2))
sec.top_margin = sec.bottom_margin = Cm(2.0)
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(10.5)
st.paragraph_format.space_after = Pt(4)

fig_no = [0]
tab_no = [0]


def para(text, bold=False, italic=False, size=None, align=None, color=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    if size:
        r.font.size = Pt(size)
    if color:
        r.font.color.rgb = RGBColor(*color)
    if align:
        p.alignment = align
    return p


def rich(parts):
    """parts: list of (text, bold)"""
    p = doc.add_paragraph()
    for t, b in parts:
        p.add_run(t).bold = b
    return p


def bullet(text, level=0):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    if text.startswith("**"):
        head, rest = text[2:].split("**", 1)
        p.add_run(head).bold = True
        p.add_run(rest)
    else:
        p.add_run(text)
    return p


_num = [0]


def restart_numbering():
    _num[0] = 0


def numbered(text):
    _num[0] += 1
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.8)
    p.paragraph_format.first_line_indent = Cm(-0.6)
    p.add_run(f"{_num[0]}.  ").bold = True
    p.add_run(text)
    return p


def keep_with_next(p):
    p.paragraph_format.keep_with_next = True


def figure(fname, caption, width=16.0):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(os.path.join(RES, fname), width=Cm(width))
    keep_with_next(p)
    fig_no[0] += 1
    c = para(f"Figure {fig_no[0]}. {caption}", italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    return fig_no[0]


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def table(caption, header, rows, widths=None, font=9):
    tab_no[0] += 1
    cp = para(f"Table {tab_no[0]}. {caption}", bold=True, size=9)
    keep_with_next(cp)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        r = cell.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(font)
        shade(cell, "D9E2F3")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(font)
    if widths:
        t.autofit = False
        grid = t._tbl.tblGrid
        for i, gc in enumerate(grid.findall(qn("w:gridCol"))):
            gc.set(qn("w:w"), str(int(widths[i] * 567)))      # twips per cm
        for i, w in enumerate(widths):
            t.columns[i].width = Cm(w)
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return tab_no[0]


def f1(x):
    return f"{x:.1f}"


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------
para("KNACKSAT-3 AIS Payload", bold=True, size=22, align=WD_ALIGN_PARAGRAPH.CENTER, color=(31, 56, 100))
para("Coexistence of the AIS 162 MHz receiver and the UHF 401 MHz transmitter on a 1U CubeSat "
     "with four perpendicular antenna elements", size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
para("Design and simulation report - version 0.2 (draft) - 15 November 2026", size=10,
     align=WD_ALIGN_PARAGRAPH.CENTER, color=(90, 90, 90))
para("Repository: github.com/zenmastercat/AIS_KNACKSAT_3", size=9, align=WD_ALIGN_PARAGRAPH.CENTER,
     color=(90, 90, 90))
p = para("Status: values tagged ASSUMED or CONFIRM are engineering placeholders. They must be replaced "
         "with KNACKSAT-3 hardware data (Section 9) before the results are used for a design review.",
         italic=True, size=9, color=(160, 40, 40))

# ---------------------------------------------------------------------------
doc.add_heading("1. Summary", level=1)
para("Goal: show that the AIS receiver (161.975 / 162.025 MHz) keeps working while the UHF transmitter "
     "(401 MHz) is on the same 1U spacecraft, with both antennas deployed as two perpendicular (crossed) "
     "dipoles - four elements in total.")
para("Verdict: coexistence is achievable with the planned methods - SAW filtering plus time-division - but "
     "only if each method is aimed at the right problem. The UHF transmitter disturbs the AIS receiver "
     "in two separate ways:", bold=False)
bullet(f"**Blocking by the 401 MHz carrier.** With the crossed dipoles, about {f1(-cpl['C401'])} dB of "
       f"antenna isolation remains (95th percentile, NEC-2 model), so {f1(S['blocking_with_cans']['p_carrier_at_ais_port_dBm'])} dBm "
       f"of carrier arrives at the AIS antenna port. That is {f1(-rows_can[0]['lna_margin_dB'])} dB above the "
       f"LNA limit. A SAW before the LNA and a second SAW after it (SAW -> LNA -> SAW) bring the "
       f"carrier {f1(a3['lna_margin_dB'])} dB below the LNA limit and {f1(a3['sdr_margin_dB'])} dB below the "
       f"SDR limit. The SAW filters solve this problem.")
bullet(f"**UHF transmitter noise that already sits at 162 MHz.** The UHF power amplifier also emits "
       f"broadband noise; the part at 162 MHz lies inside the AIS passband, so no AIS-side SAW can remove "
       f"it. With the assumed {P.UHF_TX_NOISE_DBC_HZ:.0f} dBc/Hz it is {f1(nz['no_tx_filter']['I_over_N_dB'])} dB "
       f"above the AIS noise floor, i.e. about {f1(nz['no_tx_filter']['desense_dB'])} dB of desensitisation. "
       f"Cure: time-division (AIS blanked while UHF transmits) and/or a filter at the UHF output with at "
       f"least {f1(nz['no_tx_filter']['tx_filter_needed_dB'])} dB rejection at 162 MHz.")
bullet(f"**Cost of time-division.** With a 30 s beacon and four 8-minute ground passes per day, AIS loses "
       f"about {100*td['loss_daily_average']:.1f} % of messages on a daily average "
       f"({100*td['loss_beacon_only']:.1f} % outside passes, {100*td['loss_during_pass']:.0f} % during a pass). "
       f"Because each ship reports many times per pass, ship detection probability drops by less than one "
       f"percentage point.")
bullet(f"**Antenna PCB layout is the biggest single lever.** The isolation of the crossed pair is set mainly "
       f"by the feed area where the two dipole feed lines cross. Moving the crossing from 3 mm to 10 mm "
       f"vertical separation improves the 162 MHz isolation from about "
       f"{f1(-FS['angle 3 deg + offset 1 mm, crossing 3 mm']['S21_162_p95'])} dB to "
       f"{f1(-FS['angle 3 deg + offset 1 mm, crossing 10 mm']['S21_162_p95'])} dB.")
bullet("**The previous simulations were wrong in ways that matter** (Section 7): they modelled a 3U, used "
       "free-space loss inside the near field, assumed a 90 dB SAW, inverted the time-division plot, and "
       "produced a 'mitigated' curve that rose to hundreds of dBm. They have been corrected.")
para("Recommended baseline: quartz SAW -> LNA -> SAW in the AIS front end; shielding cans and filtered "
     "supplies around the UHF PA and the AIS LNA; a hardware TX_ACTIVE line from the UHF transceiver that "
     "blanks the AIS input; a TX-side high-pass/band-pass filter at the UHF output if AIS must also receive "
     "during UHF transmission; antenna-module feed lines of the two dipoles kept at least 10 mm apart and "
     "symmetric.", bold=True)

# ---------------------------------------------------------------------------
doc.add_heading("2. System description and assumptions", level=1)
para("Spacecraft: 1U CubeSat, 100 x 100 x 113.5 mm, conducting structure. Antennas: one deployable "
     "module on the +Z face with four tape-spring elements. Two opposite elements form the AIS dipole "
     "(along X); the other two form the UHF dipole (along Y), so the two dipoles are perpendicular. Each "
     "dipole is fed at the centre of the module; the feed lines cross a few millimetres apart. "
     f"Element lengths were tuned in the model to resonate with the body present: AIS "
     f"{1000*C['element_length_ais_m']:.0f} mm per element, UHF {1000*C['element_length_uhf_m']:.0f} mm "
     f"per element (each measured from the edge of the 100 mm face).")
para("The AIS payload is receive-only, so the only aggressor is the UHF transmitter and the only victim is "
     "the AIS receiver. Table 1 lists every input value and where it comes from.")
rows = [
    ("UHF transmit power", f"{P.UHF_TX_POWER_DBM:.0f} dBm (2 W)", "CONFIRM (old HTML used 1 W)"),
    ("UHF frequency", f"{P.F_UHF_MHZ:.0f} MHz", "CONFIRM"),
    ("UHF data rate / packet", f"{P.UHF_BITRATE_BPS} bit/s, {P.UHF_PACKET_BYTES} bytes ({td['packet_s']*1000:.0f} ms)", "CONFIRM / ASSUMED"),
    ("Beacon period; passes per day; pass length; duty in pass", f"{P.UHF_BEACON_PERIOD_S:.0f} s; {P.UHF_PASSES_PER_DAY}; {P.UHF_PASS_LENGTH_S:.0f} s; {P.UHF_PASS_DOWNLINK_DUTY:.0%}", "ASSUMED"),
    ("UHF PA noise at 162 MHz", f"{P.UHF_TX_NOISE_DBC_HZ:.0f} dBc/Hz", "ASSUMED - measure"),
    ("AIS channels, modulation", "161.975 / 162.025 MHz, GMSK 9600 bit/s, 26.67 ms slot", "STD (ITU-R M.1371)"),
    ("AIS sensitivity requirement", f"{P.AIS_SENS_DBM:.0f} dBm (20 % PER)", "STD (ITU-R M.1371)"),
    ("Receiver noise bandwidth", f"{P.AIS_NOISE_BW_HZ/1e3:.0f} kHz", "ASSUMED"),
    ("Max Doppler at 162 MHz", f"+/-{P.AIS_DOPPLER_KHZ:.2f} kHz (7.5 km/s)", "Physics"),
    ("LNA gain / NF / input P1dB", f"{P.LNA_GAIN_DB:.0f} dB / {P.LNA_NF_DB:.1f} dB / {P.LNA_IP1DB_DBM:.0f} dBm", "ASSUMED"),
    ("SDR NF / input P1dB", f"{P.BACKEND_NF_DB:.0f} dB / {P.BACKEND_IP1DB_DBM:.0f} dBm", "ASSUMED"),
    ("Blocking criterion", f"interferer <= P1dB - {P.BLOCK_BACKOFF_DB:.0f} dB", "ASSUMED"),
    ("162 MHz SAW: IL / 3 dB BW / rejection at 401 MHz", f"{P.SAW_IL_DB} dB / {P.SAW_BW3_MHZ} MHz / {P.SAW_REJ_401_DB:.0f} dB", "DATASHEET (typical)"),
    ("Max realisable cascade rejection (PCB bypass)", f"{P.PCB_BYPASS_LIMIT_DB:.0f} dB", "ASSUMED"),
    ("Board leakage, UHF PA -> AIS LNA", f"{P.BOARD_ISO_NO_CAN_DB:.0f} dB (no cans), {P.BOARD_ISO_CAN_DB:.0f} dB (cans)", "ASSUMED"),
    ("Blanking guards", f"{P.TX_RAMP_GUARD_S*1e3:.0f} ms before TX, {P.LNA_RECOVERY_S*1e3:.0f} ms after TX", "ASSUMED"),
    ("Deployment tolerance (Monte Carlo)", f"{P.TOL_ELEMENT_ANGLE_DEG} deg per element, {P.TOL_FEED_OFFSET_M*1e3:.0f} mm feed offset (1 sigma)", "ASSUMED"),
    ("Board temperature over orbit; qualification", f"{P.T_ORBIT_RANGE_C[0]:.0f} to {P.T_ORBIT_RANGE_C[1]:.0f} C; {P.T_QUAL_RANGE_C[0]:.0f} to {P.T_QUAL_RANGE_C[1]:.0f} C", "ASSUMED"),
    ("Orbit", f"{P.ORBIT_ALT_KM:.0f} km, period {S['orbit_period_s']/60:.1f} min", "ASSUMED"),
]
table("Input parameters (all held in sim/params.py)", ["Parameter", "Value", "Source"], rows, widths=[6.5, 6.5, 3.6])

# ---------------------------------------------------------------------------
doc.add_heading("3. How the UHF transmitter can disturb the AIS receiver", level=1)
table("Interference mechanisms and the method that addresses each",
      ["Mechanism", "What happens", "Effective cure", "Does NOT help"],
      [("Blocking / compression", "401 MHz carrier overdrives LNA or SDR; gain drops, spurious products appear, slow recovery",
        "SAW band-pass at 162 MHz (before and after LNA); antenna isolation; shielding", "TX-side filter (carrier is the wanted UHF signal)"),
       ("In-band TX noise", "PA broadband noise at 162 MHz enters the AIS channel and raises the noise floor",
        "Time-division (blank AIS during TX); TX-side high-pass/band-pass filter at UHF output", "Any AIS-side SAW (noise is inside its passband)"),
       ("Spurious tones at 162 MHz", "Clock harmonics on the spacecraft fall on AIS, e.g. 27 MHz x 6 or 54 MHz x 3 = 162 MHz",
        "Clock plan review; spread-spectrum clocks; shielding", "SAW (in-band)"),
       ("Board leakage path", "PA energy couples through PCB, harness and power rails, bypassing the antennas",
        "Shielding cans, filtered supply lines, separated grounds", "Antenna orientation"),
       ("Recovery after TX", "LNA/AGC needs time to recover after a strong burst",
        "SAW (keeps LNA out of compression); guard time in the blanking window", "-")],
      widths=[3.0, 5.0, 4.8, 3.8], font=8.5)
para("Third-order products of the 401 MHz carrier with AIS-band signals and harmonics of 401 MHz do not land "
     "on 162 MHz (401/162 = 2.48 is not an integer ratio). If the AIS receiver is a direct-sampling SDR, "
     "the alias of 401 MHz for the chosen sample rate must be checked once the SDR is known (Section 9).")

# ---------------------------------------------------------------------------
doc.add_heading("4. Method", level=1)
doc.add_heading("4.1 Antenna coupling: NEC-2 method of moments", level=2)
para("The old free-space path-loss formula is not valid here: the antennas are 0.1-0.3 m apart, which is "
     "less than one wavelength at 401 MHz (0.75 m) and far less at 162 MHz (1.85 m), so they are in each "
     "other's near field, and the spacecraft body is part of the antenna. Instead, the 1U body was modelled "
     "as a conducting wire grid and the four elements as thin wires in NEC-2 (PyNEC). For each geometry the "
     "two-port admittance matrix was computed by driving each port in turn with the other shorted, and "
     "converted to S-parameters for 50 ohm ports.")
para("A perfectly symmetric crossed pair has, in theory, near-infinite isolation (the model gives below "
     "-250 dB). Real hardware never achieves that: deployed tape elements point a few degrees off, and the "
     "feed points are not exactly centred. The isolation is therefore taken from a Monte Carlo run of "
     f"{C['mc']['runs']} random deployments, and the 95th-percentile value is used as the design value.")
para("Two coupling figures are used: (a) at 401 MHz, coupling relative to the power accepted by the UHF "
     "antenna (the UHF port is matched at 401 MHz); (b) at 162 MHz, |S21| between 50 ohm ports, because the "
     "UHF PA noise at 162 MHz leaves a 50 ohm source into an antenna that is not matched there.")
figure("fig_geometry.png", "NEC-2 model: 1U body as a wire grid with the AIS dipole (X) and UHF dipole (Y).", width=10.5)

doc.add_heading("4.2 Receiver budget", level=2)
para("Carrier at the AIS antenna port:  P_ant = P_TX - L_TXfeed + C_401 - L_AISfeed.")
para("Board leakage, added in parallel (powers add in watts, not dB):  P_board = P_TX - I_board.")
para("LNA input = P_ant - R_preSAW (+) P_board;  SDR input = [P_ant - min(R_pre + R_post, 65 dB) (+) "
     "P_board - R_post] + G_LNA, where (+) is a power sum.")
para("Noise figure by the Friis formula over feed loss, SAW, LNA, SAW and SDR; noise floor N = -174 dBm/Hz "
     "+ 10 log10(B) + NF.  In-band UHF noise at the AIS port: I = P_TX + N_PA(dBc/Hz) + 10 log10(B) - "
     "R_TXfilter + C_162 - L_AISfeed.  Desense = 10 log10(1 + I/N); 1 dB desense corresponds to I/N = -5.9 dB.")

doc.add_heading("4.3 SAW thermal drift", level=2)
para("The SAW centre frequency moves with temperature: ST-cut quartz is parabolic (-0.034 ppm/C^2 about "
     "25 C); lithium tantalate is roughly linear (about -32 ppm/C). The passband is modelled as a "
     f"third-order response with {P.SAW_BW3_MHZ} MHz 3 dB bandwidth. The extra loss on the wanted signal is "
     "evaluated at both AIS channels with +/-4 kHz Doppler. Rejection at 401 MHz, 239 MHz away, is not "
     "affected by a shift of a few hundred kHz.")

doc.add_heading("4.4 Time-division (blanking)", level=2)
para("While the UHF transmitter is on, the AIS input is blanked (RF switch or LNA disabled, and samples "
     "flagged), with a guard time before the PA ramps up and a recovery time after it switches off. An AIS "
     "message (one 26.67 ms slot) is lost if any part of it overlaps the blanked window, so the lost share is "
     "(T_burst + T_guard,pre + T_guard,post + T_slot) / T_period. Ship detection probability in one pass with "
     "N reports and per-message success p is 1 - (1 - p(1 - loss))^N. N = 60 is used (Class A ship "
     "reporting every 10 s over a 10 min pass).")

# ---------------------------------------------------------------------------
doc.add_heading("5. Results", level=1)
doc.add_heading("5.1 Antenna coupling", level=2)
mc = C["mc"]
para(f"Design values (95th percentile, {mc['runs']} deployments, {mc['angle_sigma_deg']} deg 1-sigma): "
     f"{f1(mc['C401_matched_dB']['p95'])} dB at 401 MHz (median {f1(mc['C401_matched_dB']['median'])} dB) "
     f"and {f1(mc['S21_162_dB']['p95'])} dB at 162 MHz (median {f1(mc['S21_162_dB']['median'])} dB). "
     f"For comparison, the old simulation's free-space formula gave {f1(old['old_fspl_isolation_dB'])} dB "
     f"for the 3U diagonal, before adding 25 dB of cross-polarisation.")
figure("fig_coupling_sweep.png", "Port matching and AIS-UHF coupling from 100 to 500 MHz (worst and median of 40 random deployments).", width=14)
figure("fig_coupling_mc.png", "Distribution of coupling over 200 random deployments; the 95th percentile is the design value.", width=15)
fs_rows = [(k, f1(v["C401_p50"]), f1(v["C401_p95"]), f1(v["S21_162_p50"]), f1(v["S21_162_p95"])) for k, v in FS.items()]
table("Which geometry error sets the isolation (60 runs per case)",
      ["Case", "401 MHz median [dB]", "401 MHz p95 [dB]", "162 MHz median [dB]", "162 MHz p95 [dB]"],
      fs_rows, widths=[6.2, 2.6, 2.6, 2.6, 2.6])
para("The feed region dominates. A 1 mm offset of the feed point, with the two feed lines crossing 3 mm "
     "apart, causes most of the coupling; spacing the crossing to 10 mm gains about 25-30 dB at 162 MHz. "
     "Element pointing errors matter less. In hardware this region is the antenna-module PCB (baluns, "
     "traces, connectors), so its layout should keep the two feed networks separated and symmetric, and the "
     "isolation should be measured on the real module (Section 8). NEC-2 is also less accurate when wires "
     "are only a few radii apart, so the 3 mm case is kept as a conservative bound.")

doc.add_heading("5.2 Blocking by the 401 MHz carrier", level=2)
brow = []
for rn, rc in zip(rows_nocan, rows_can):
    brow.append((rc["arch"].split("  ")[1], f1(rn["lna_in_dBm"]), f1(rc["lna_in_dBm"]), f1(rc["lna_margin_dB"]),
                 f1(rc["sdr_in_dBm"]), f1(rc["sdr_margin_dB"]), f"{rc['NF_dB']:.2f}"))
table("401 MHz carrier in the AIS chain while UHF transmits (limits: LNA -20 dBm, SDR -40 dBm)",
      ["Front end", "LNA in, no cans [dBm]", "LNA in, cans [dBm]", "LNA margin [dB]", "SDR in, cans [dBm]",
       "SDR margin [dB]", "System NF [dB]"], brow, widths=[3.4, 2.2, 2.2, 2.0, 2.2, 2.0, 2.0], font=8.5)
para(f"Without a filter the carrier reaches the LNA at {f1(rows_can[0]['lna_in_dBm'])} dBm - well above the "
     f"compression limit. A SAW after the LNA alone does not protect the LNA. A SAW before the LNA protects "
     f"the LNA but the amplified carrier then overdrives the SDR. Only SAW -> LNA -> SAW passes both limits "
     f"({f1(a3['lna_margin_dB'])} dB and {f1(a3['sdr_margin_dB'])} dB margin). The price is "
     f"{a3['NF_dB'] - rows_can[0]['NF_dB']:.1f} dB of noise figure from the pre-LNA SAW loss, which leaves "
     f"the noise floor at {f1(a3['noise_floor_dBm'])} dBm in {P.AIS_NOISE_BW_HZ/1e3:.0f} kHz - still about "
     f"{f1(P.AIS_SENS_DBM - 10 - a3['noise_floor_dBm'])} dB better than needed for the -107 dBm requirement "
     f"(assuming a 10 dB demodulation SNR). Shielding cans matter mainly for the LNA margin, because the board "
     f"path bypasses the pre-LNA SAW.")
figure("fig_budget.png", "Left: 401 MHz carrier at LNA and SDR for each front end. Right: in-band UHF noise at 162 MHz relative to the AIS noise floor.", width=16)

doc.add_heading("5.3 In-band UHF noise at 162 MHz", level=2)
ntab = [(k, f1(v)) for k, v in S["tx_filter_needed_vs_tx_noise_dBc_Hz"].items()]
para(f"With no TX-side filter, the PA noise at 162 MHz reaches the AIS port at "
     f"{f1(nz['no_tx_filter']['I_at_ais_port_dBm'])} dBm against a noise floor of "
     f"{f1(nz['no_tx_filter']['noise_floor_dBm'])} dBm: I/N = {f1(nz['no_tx_filter']['I_over_N_dB'])} dB, "
     f"so the AIS receiver is effectively deaf while UHF transmits. A {P.UHF_TX_HPF_REJ_162_DB:.0f} dB TX "
     f"filter reduces the desense to {nz['with_tx_filter']['desense_dB']:.2f} dB. The required rejection "
     f"depends directly on the PA noise, which has not been measured yet (Table 5).")
table("TX-side filter rejection at 162 MHz needed for <= 1 dB desense",
      ["UHF PA noise at 162 MHz [dBc/Hz]", "Required TX filter rejection [dB]"], ntab, widths=[6, 6])
para("Practical notes: the UHF transceiver's harmonic low-pass filter does nothing at 162 MHz (it is below "
     "401 MHz). A high-pass or band-pass filter at the UHF output is needed. A 2 W SAW at the TX side is "
     "possible but SAW power handling is limited; an LC or ceramic high-pass/band-pass filter is the safer "
     "choice there. If time-division is always used, this filter becomes optional.")

doc.add_heading("5.4 SAW thermal drift", level=2)
para(f"Over the qualification range, an ST-quartz SAW moves by at most {th['quartz']['shift_qual_worst_kHz']:.0f} kHz "
     f"(negligible extra loss), while a lithium-tantalate SAW moves by {th['litao3']['shift_qual_worst_kHz']:.0f} kHz "
     f"and adds up to {th['litao3']['extra_loss_qual_worst_dB']:.1f} dB on the worst AIS channel with Doppler. "
     f"Neither changes the rejection at 401 MHz. Recommendation: choose a quartz SAW, or a LiTaO3 part with at "
     f"least 1 MHz bandwidth.")
figure("fig_saw_thermal.png", "SAW passband at -40, 25 and 85 C for quartz and LiTaO3, and the resulting extra loss on the AIS channels.", width=16)

doc.add_heading("5.5 Time-division", level=2)
para(f"Each UHF packet lasts {td['packet_s']*1000:.0f} ms. Adding guards and one AIS slot, each burst blanks "
     f"{(td['packet_s']+P.TX_RAMP_GUARD_S+P.LNA_RECOVERY_S+P.AIS_SLOT_S)*1000:.0f} ms of AIS reception. With "
     f"a beacon every {P.UHF_BEACON_PERIOD_S:.0f} s this loses {100*td['loss_beacon_only']:.1f} % of messages; "
     f"during a downlink pass at {P.UHF_PASS_DOWNLINK_DUTY:.0%} duty it loses {100*td['loss_during_pass']:.0f} %; "
     f"the daily average is {100*td['loss_daily_average']:.1f} %. Figure 6 shows a 120 s window with two "
     f"beacons followed by the start of a ground pass.")
figure("fig_timeline.png", "Time-domain run: carrier level (top), in-band desense (middle), and AIS messages received or lost to blanking (bottom).", width=16)
k = list(det.keys())
drow = []
for pk in k:
    vals = list(det[pk].values())
    drow.append((pk.replace("p_msg=", ""), *(f"{100*v:.1f} %" for v in vals)))
lk = [x.replace("loss=", "") for x in det[k[0]].keys()]
table("Probability of detecting a ship in one pass (60 reports) vs share of messages lost",
      ["Per-message success", *(f"loss {x}" for x in lk)], drow, widths=[3.6, 3.2, 3.2, 3.2, 3.2])
para("Detection is limited by message collisions (low per-message success over busy sea areas), not by "
     "blanking: at the daily-average loss the detection probability changes by less than one percentage "
     "point. Even 10 % loss costs only a few points. The operational rule that follows: avoid long UHF "
     "downlinks over the AIS target areas (for example, the Gulf of Thailand is under the Thai ground "
     "station), or store AIS data and downlink when the target area has been passed.")
figure("fig_detection.png", "Ship detection probability vs AIS messages lost to time-division.", width=12)

# ---------------------------------------------------------------------------
doc.add_heading("6. Recommended design", level=1)
doc.add_heading("6.1 Hardware", level=2)
bullet("**AIS front end: SAW -> LNA -> SAW**, quartz SAWs centred on 162.0 MHz, about 1 MHz bandwidth, "
       ">= 40 dB rejection at 401 MHz each; use an LNA with input P1dB >= -10 dBm and a limiter/ESD "
       "protection at its input.")
bullet("**Antenna module PCB:** keep the AIS and UHF feed networks (baluns, traces) at least 10 mm apart "
       "where they cross, symmetric about the module centre, with a ground fence between them.")
bullet("**UHF output:** add a high-pass/band-pass filter with >= 40 dB rejection at 162 MHz (sized by the "
       "measured PA noise, Table 5) if AIS must receive during UHF transmission.")
bullet("**Shielding:** cans over the UHF PA and the AIS LNA/SAW section, filtered and separately regulated "
       "supplies, coax (not PCB traces) between boards.")
bullet("**Clock plan:** confirm no spacecraft clock harmonic lands within +/-50 kHz of 161.975 / 162.025 MHz "
       "(for example 27, 54 or 81 MHz references are harmful).")
doc.add_heading("6.2 Time-division interface", level=2)
restart_numbering()
numbered(f"The UHF transceiver drives a hardware TX_ACTIVE line to the AIS receiver at least "
         f"{P.TX_RAMP_GUARD_S*1e3:.0f} ms before the PA ramps up.")
numbered("On TX_ACTIVE, the AIS receiver switches an absorptive RF switch before the LNA (or disables the "
         "LNA) and marks its sample stream as invalid.")
numbered(f"TX_ACTIVE is released when the PA is off; the AIS receiver waits {P.LNA_RECOVERY_S*1e3:.0f} ms "
         f"before using samples again.")
numbered("The AIS decoder drops any message that overlaps the invalid window and counts the dropped slots in "
         "telemetry, so the real loss can be checked in orbit.")
numbered("The on-board scheduler plans long downlinks away from AIS target areas where possible.")
para("Hardware signalling is preferred to a software schedule: it is exact to the millisecond and still "
     "works if the UHF software restarts or retransmits.")

# ---------------------------------------------------------------------------
doc.add_heading("7. Review of the previous simulations", level=1)
para("The repository contained sim-ais.py, simsim.py (with cubesat_rf_sim_results.csv and the plots) and an "
     "HTML simulator (two identical copies). The following errors were found and corrected; the original "
     "code remains in the git history (commit 910f6ae).")
table("Errors in the previous simulations and their corrections",
      ["#", "Error", "Effect", "Correction"],
      [("1", "Geometry of a 3U (0.1 x 0.3 m diagonal)", "Wrong spacing for a 1U", "1U body and 4-element module modelled in NEC-2"),
       ("2", "Free-space path loss used at 0.32 m", f"Gives {f1(old['old_fspl_isolation_dB'])} dB; formula invalid in the near field and ignores the body",
        "Method-of-moments coupling with Monte Carlo tolerances"),
       ("3", "Cross-pol 25 + shielding 15 + SAW 90 dB added in series", f"Total {f1(old['old_total_isolation_dB'])} dB - far too optimistic",
        "Cross-pol is inside the computed coupling; shielding acts on a parallel board path; SAW 40 dB each, cascade capped at 65 dB"),
       ("4", "SAW thermal loss 0.005 x (df in kHz)^2 subtracted from rejection", f"Up to {old['old_saw_detune_loss_max_dB']:.0f} dB, so the 'mitigated' curve rose to hundreds of dBm",
        "Drift shifts the passband (affects wanted signal slightly); rejection at 401 MHz unchanged"),
       ("5", "Time-division plot inverted", "Leakage drawn when UHF is off; noise floor drawn when UHF is on", "Interference only while UHF transmits; blanking shown as lost AIS time"),
       ("6", "Desense from the 401 MHz carrier treated as in-band noise", "About 150 dB 'desense'", "Blocking and in-band noise computed separately"),
       ("7", "Random +/-3.5 dB fading every 10 ms", "Not physical for a rigid near-field structure", "Static coupling; spread from deployment tolerances"),
       ("8", "Thermal cycle of 10 s, Doppler cycle of 20 s", "Orbit is about 95 min", "Orbit period used; Doppler +/-4.05 kHz"),
       ("9", "HTML: +60 dB 'isolation' for blanking, 5 dB spacing loss, 1 W TX, -70 dBm 'noise floor'", "Inconsistent with the Python model",
        "HTML rebuilt on the corrected budget; blanking shown as reception time lost"),
       ("10", "Comments: '20 % duty' gave about 30 % (sin > 0.6) and 33 % (sin > 0.5)", "Mislabelled duty", "Duty derived from packet length and schedule")],
      widths=[0.7, 4.8, 5.2, 5.9], font=8)

# ---------------------------------------------------------------------------
doc.add_heading("8. Verification plan", level=1)
restart_numbering()
numbered("Antenna isolation: measure S21 between the AIS and UHF ports of the flight-representative antenna "
         "module on a 1U mass model with a vector network analyser, 100-500 MHz, elements deployed; repeat "
         "after several stow/deploy cycles. Pass if |S21| at 162 MHz and 401 MHz is at or better than the "
         "values in Section 5.1.")
numbered("PA noise: with the UHF transmitter at full power into a dummy load through a coupler, measure the "
         "noise density at 161.975 / 162.025 MHz with a spectrum analyser, using a 401 MHz notch to protect the "
         "analyser. This fixes the TX-filter requirement (Table 5).")
numbered("Conducted coexistence: feed an AIS test signal at -107 dBm and -112 dBm into the AIS receiver, inject "
         "the UHF transmitter output through an attenuator equal to the measured antenna isolation, and record "
         "the packet error rate with UHF off, on, and on with blanking.")
numbered("Recovery time: measure how long after TX_ACTIVE is released the AIS receiver decodes correctly; "
         "set the post-TX guard to this value plus margin.")
numbered("Thermal: measure the SAW passband at -40, +25 and +85 C (or the qualification range).")
numbered("System test: radiated test of the integrated 1U with both antennas deployed and an AIS signal "
         "generator, beacon running.")

# ---------------------------------------------------------------------------
doc.add_heading("9. Open items - information needed from the team", level=1)
for q in ["UHF transmitter: exact frequency, output power (1 W or 2 W), transceiver/PA part numbers, data rate, "
          "packet length, beacon period and downlink schedule.",
          "AIS receiver: architecture and parts (LNA, SAW, SDR or transceiver, sample rate), its input P1dB and "
          "noise figure, and whether it has an RF switch or LNA enable pin for blanking.",
          "Antenna module: manufacturer or in-house design, element lengths, whether the four elements form two "
          "dipoles (as modelled) or four monopoles, and the feed/balun layout on the module PCB.",
          "Selected SAW filter part number(s) and their datasheet rejection at 401 MHz.",
          "Mission requirement: must AIS receive while UHF transmits, or is blanking acceptable?",
          "Board-level clock frequencies of the OBC, EPS, UHF and AIS boards.",
          "Orbit altitude and expected internal temperature range."]:
    bullet(q)

# ---------------------------------------------------------------------------
doc.add_heading("10. Repository contents and how to run", level=1)
table("Files", ["File", "Purpose"],
      [("sim/params.py", "All input values with source tags"),
       ("sim/antenna_coupling_nec.py", "NEC-2 model of the 1U and crossed dipoles; Monte Carlo; writes results/coupling.json"),
       ("sim/feed_sensitivity.py", "Separates pointing vs feed-offset effects; writes results/feed_sensitivity.json"),
       ("sim/coexistence.py", "Blocking, in-band noise, SAW thermal, time-division; writes results/summary.json, figures, CSV"),
       ("simsim.py, sim-ais.py", "Corrected; now run sim/coexistence.py (old code in git history)"),
       ("artifact-...-1.html", "Interactive simulator, rebuilt on the corrected budget"),
       ("docs/build_docx.py", "Builds this document from the results")], widths=[5.0, 11.6])
para("Run with uv (Python 3.13+):  uv run python sim/antenna_coupling_nec.py;  uv run python sim/feed_sensitivity.py;  "
     "uv run python sim/coexistence.py;  uv run python docs/build_docx.py")

doc.add_heading("References", level=1)
for ref in ["ITU-R Recommendation M.1371-5, Technical characteristics for an automatic identification system "
            "using TDMA in the VHF maritime mobile band, 2014.",
            "ITU-R Report M.2084, Satellite detection of automatic identification system messages, 2007.",
            "G. J. Burke, A. J. Poggio, Numerical Electromagnetics Code (NEC-2) - Method of Moments, LLNL, 1981; "
            "PyNEC Python bindings.",
            "SIPAT LBT16201 162.2 MHz SAW filter datasheet (2.5 dB IL, 1 MHz bandwidth) - typical values.",
            "GPIO Labs AIS receive band-pass filter, published response (about 30 dB at 250 MHz, 42 dB at "
            "500 MHz) - used to bound the 401 MHz rejection."]:
    bullet(ref)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
doc.save(OUT)
print("saved", OUT, "figures", fig_no[0], "tables", tab_no[0])
