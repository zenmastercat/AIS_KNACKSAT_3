"""
KNACKSAT-3 AIS (162 MHz) / UHF (401 MHz) coexistence - shared parameters.

Every number used by the simulations lives here so it can be checked and
replaced in one place.  Tags:
    [STD]      taken from a standard (ITU-R M.1371) or physics
    [DATASHEET] typical value seen in commercial 162 MHz SAW datasheets
    [ASSUMED]  engineering placeholder - replace with the real KNACKSAT-3 value
    [CONFIRM]  value the team must confirm (the old sims disagree or it is unknown)
"""
import numpy as np

C0 = 299_792_458.0          # speed of light [m/s]
K_BOLTZ_DBM_HZ = -174.0     # kT at 290 K [dBm/Hz]                          [STD]

# ---------------------------------------------------------------------------
# Spacecraft and antenna geometry (1U CubeSat, 4-element deployable module)
# ---------------------------------------------------------------------------
SAT_X = 0.100               # 1U body [m]                                    [STD]
SAT_Y = 0.100
SAT_Z = 0.1135
ANT_MODULE_HEIGHT = 0.007   # feed plane height above +Z face [m]            [ASSUMED]
ANT_CROSS_OFFSET = 0.003    # vertical gap where the two feed lines cross [m] [ASSUMED]
TAPE_EQ_RADIUS = 0.00125    # 5 mm tape-spring element -> equivalent radius w/4 [ASSUMED]
GRID_DIV = 4                # wire-grid cells per face edge for the 1U body

# Two crossed dipoles = 4 elements, deployed from the edges of the +Z face:
#   AIS  dipole along X (2 x VHF elements), UHF dipole along Y (2 x UHF elements)
F_AIS_MHZ = 162.0           # AIS centre (161.975 / 162.025 MHz channels)    [STD]
F_UHF_MHZ = 401.0           # UHF TX                                         [CONFIRM]
# Element lengths are tuned automatically in antenna_coupling_nec.py to resonate
# with the 1U body present; the values found are written to results/coupling.json.

# Deployment tolerances used in the Monte Carlo (sets the real isolation of a
# crossed pair - a perfectly symmetric model has almost infinite isolation)
TOL_ELEMENT_ANGLE_DEG = 3.0 # 1-sigma pointing error of each deployed element [ASSUMED]
TOL_FEED_OFFSET_M = 0.001   # 1-sigma feed-point offset from body centre     [ASSUMED]
MC_RUNS = 200

# ---------------------------------------------------------------------------
# UHF transmitter (aggressor)
# ---------------------------------------------------------------------------
UHF_TX_POWER_DBM = 33.0     # 2 W  (old HTML used 1 W / 30 dBm)              [CONFIRM]
UHF_TX_FEED_LOSS_DB = 0.5   # cable + matching loss to antenna               [ASSUMED]
UHF_TX_NOISE_DBC_HZ = -150.0  # PA wideband noise at 162 MHz (239 MHz offset) [ASSUMED - measure]
UHF_TX_HPF_REJ_162_DB = 50.0  # optional TX-side filter rejection at 162 MHz [ASSUMED]
UHF_TX_HPF_IL_DB = 0.8        # its insertion loss at 401 MHz                 [ASSUMED]
UHF_BITRATE_BPS = 9600        #                                              [CONFIRM]
UHF_PACKET_BYTES = 300        # payload + framing + preamble                 [ASSUMED]
UHF_BEACON_PERIOD_S = 30.0    # beacon interval outside ground passes        [CONFIRM]
UHF_PASS_DOWNLINK_DUTY = 0.5  # TX duty during a ground-station pass         [ASSUMED]
UHF_PASSES_PER_DAY = 4        # usable Thailand GS passes                    [ASSUMED]
UHF_PASS_LENGTH_S = 480.0     # usable pass length                           [ASSUMED]

# ---------------------------------------------------------------------------
# AIS receiver (victim)
# ---------------------------------------------------------------------------
AIS_CHANNELS_MHZ = (161.975, 162.025)                                       # [STD]
AIS_BITRATE_BPS = 9600       # GMSK                                          [STD]
AIS_SLOT_S = 256 / 9600      # 26.67 ms slot                                 [STD]
AIS_SENS_DBM = -107.0        # M.1371 minimum sensitivity (20 % PER)         [STD]
AIS_NOISE_BW_HZ = 16e3       # receiver noise bandwidth                      [ASSUMED]
AIS_DOPPLER_KHZ = 4.05       # 162 MHz x 7.5 km/s / c                        [STD]
AIS_FEED_LOSS_DB = 0.3       # antenna -> first filter                       [ASSUMED]
LNA_NF_DB = 1.0              #                                               [ASSUMED]
LNA_GAIN_DB = 20.0           #                                               [ASSUMED]
LNA_IP1DB_DBM = -10.0        # input 1 dB compression                        [ASSUMED]
BACKEND_NF_DB = 6.0          # SDR / transceiver after the LNA               [ASSUMED]
BACKEND_IP1DB_DBM = -30.0    # SDR input compression                         [ASSUMED]
BLOCK_BACKOFF_DB = 10.0      # interferer must stay this far below IP1dB     [ASSUMED]
DESENSE_ALLOWED_DB = 1.0     # max allowed sensitivity loss                  [ASSUMED]
LNA_RECOVERY_S = 0.010       # blanking guard after TX off                   [ASSUMED]
TX_RAMP_GUARD_S = 0.005      # blanking guard before TX on                   [ASSUMED]

# 162 MHz SAW band-pass filter (pre- and/or post-LNA)
SAW_IL_DB = 2.5              # passband insertion loss                       [DATASHEET]
SAW_BW3_MHZ = 1.0            # 3 dB bandwidth (narrow AIS SAW)               [DATASHEET]
SAW_REJ_401_DB = 40.0        # stop-band rejection at 401 MHz                [DATASHEET ~38-42]
SAW_ORDER = 3                # passband-shape model order
PCB_BYPASS_LIMIT_DB = 65.0   # max total filter rejection a PCB can realise   [ASSUMED]
# Temperature coefficient: ST-quartz (parabolic) vs LiTaO3 (linear)
TCF_QUARTZ_PPM_C2 = -0.034   # turnover 25 C                                 [STD material]
TCF_LITAO3_PPM_C = -32.0     #                                               [STD material]
T_QUAL_RANGE_C = (-40.0, 85.0)  # qualification range
T_ORBIT_RANGE_C = (-10.0, 40.0) # internal board swing over one orbit         [ASSUMED]

# Board-level (conducted / leakage) path from UHF PA to AIS LNA input,
# a separate path in parallel with the antenna-to-antenna path
BOARD_ISO_NO_CAN_DB = 70.0   #                                               [ASSUMED]
BOARD_ISO_CAN_DB = 90.0      # with shielding cans + filtered power lines    [ASSUMED]

# Orbit
ORBIT_ALT_KM = 500.0                                                        # [ASSUMED]
ORBIT_PERIOD_S = 2 * np.pi * np.sqrt((6371e3 + ORBIT_ALT_KM * 1e3) ** 3 / 3.986004418e14)


def db2lin(x):
    return 10.0 ** (np.asarray(x) / 10.0)


def lin2db(x):
    return 10.0 * np.log10(np.asarray(x))


def dbm_sum(*levels_dbm):
    """Power-sum of several dBm levels (paths in parallel add in watts, not dB)."""
    return lin2db(sum(db2lin(l) for l in levels_dbm))
