import numpy as np
import matplotlib.pyplot as plt

def simulate_interference():
    # 1. System Parameters
    tx_power_dBm = 33.0        # 2W UHF Transmitter (401/435 MHz)
    freq_tx_mhz = 401.0        # UHF Transmission Frequency
    freq_rx_mhz = 162.0        # AIS Reception Frequency
    lna_sat_limit_dBm = -20.0  # Threshold where AIS receiver saturates/fails
    
    # 2. Physical Antenna Placement (Pythagorean Theorem)
    # Calculating worst-case diagonal distance on a standard 3U CubeSat
    dx_meters = 0.1  # Horizontal separation
    dy_meters = 0.3  # Vertical separation
    d_meters = np.sqrt(dx_meters**2 + dy_meters**2)
    print(f"Diagonal Antenna Separation: {d_meters:.3f} meters")

    # Baseline Near-Field Coupling (Simplified Free Space Path Loss)
    # FSPL(dB) = 20*log10(d) + 20*log10(f) - 27.55
    baseline_isolation_dB = 20 * np.log10(d_meters) + 20 * np.log10(freq_tx_mhz) - 27.55
    
    # 3. Mitigations
    cross_pol_isolation_dB = 25.0  # Orthogonal 90-degree placement
    shielding_isolation_dB = 15.0  # Faraday cages preventing PCB leakage
    saw_rejection_dB = 90.0        # SAW filter out-of-band rejection
    
    # 4. Time Series Setup (Simulating a 10-second window)
    time_s = np.linspace(0, 10, 1000)
    
    # Non-ideal space factors: Structural reflections off solar panels & thermal drift
    # Modeled as random fading variance around the theoretical isolation
    space_variance_dB = np.random.normal(0, 3.5, len(time_s)) 
    
    # Time-Division Operation (TDO) / Blanking
    # Simulating telemetry packet bursts: UHF transmits 20% of the time
    uhf_tx_active = (np.sin(2 * np.pi * 0.5 * time_s) > 0.6).astype(int)
    
    # 5. Calculate Power at AIS LNA Input
    # Scenario A: Unmitigated (No filters, aligned antennas, no TDO)
    p_rx_unmitigated = tx_power_dBm - baseline_isolation_dB + space_variance_dB
    p_rx_unmitigated = np.where(uhf_tx_active, p_rx_unmitigated, -120) # -120 is noise floor
    
    # Scenario B: Fully Mitigated (Cross-pol + Shielding + SAW)
    total_isolation_dB = baseline_isolation_dB + cross_pol_isolation_dB + shielding_isolation_dB + saw_rejection_dB
    p_rx_mitigated = tx_power_dBm - total_isolation_dB + space_variance_dB
    
    # Apply Time-Division Operation: Mute AIS LNA during UHF TX
    # If UHF is transmitting, AIS is muted (effectively dropping interference to noise floor)
    p_rx_final = np.where(uhf_tx_active, -120, p_rx_mitigated) 
    # Note: When UHF is off, AIS receives normally (interference is -120 dBm background)
    
    # 6. Visualization
    plt.figure(figsize=(12, 6))
    
    plt.plot(time_s, p_rx_unmitigated, color='red', alpha=0.7, label='Unmitigated Interference')
    plt.plot(time_s, p_rx_final, color='green', linewidth=2, label='Mitigated (SAW + TDO + Orthogonal)')
    
    # Add LNA Saturation Threshold
    plt.axhline(y=lna_sat_limit_dBm, color='black', linestyle='--', linewidth=2, label='AIS LNA Saturation Limit')
    
    plt.title('CubeSat AIS vs UHF Interference Mitigation (Non-Ideal Space Model)')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Power at AIS Receiver Input (dBm)')
    plt.ylim(-130, 40)
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    simulate_interference()