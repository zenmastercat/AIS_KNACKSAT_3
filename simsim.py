import os
import csv
import numpy as np
import matplotlib.pyplot as plt

def run_advanced_cubesat_simulation():
    # ---------------------------------------------------------
    # 1. Output Path Setup (Saves in the script's local directory)
    # ---------------------------------------------------------
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_csv = os.path.join(script_dir, "cubesat_rf_sim_results.csv")
    output_png = os.path.join(script_dir, "cubesat_rf_sim_plot.png")
    
    print(f"Executing simulation...")
    print(f"Data will be saved to: {output_csv}")
    
    # ---------------------------------------------------------
    # 2. System & Environment Constants
    # ---------------------------------------------------------
    np.random.seed(42)
    duration_sec = 10.0
    num_samples = 1000
    time_s = np.linspace(0, duration_sec, num_samples)
    
    freq_tx_mhz = 401.0             # UHF transmit frequency
    freq_rx_mhz = 162.0             # AIS receive frequency
    tx_power_dBm = 33.0             # 2W transmitter output
    lna_sat_limit_dBm = -20.0       # AIS LNA saturation threshold
    thermal_noise_floor_dBm = -133.0# Baseline thermal noise (25 kHz channel)
    
    # ---------------------------------------------------------
    # 3. Geometry & Near-Field Coupling (Pythagorean Theorem)
    # ---------------------------------------------------------
    dx_m, dy_m = 0.1, 0.3
    d_meters = np.sqrt(dx_m**2 + dy_m**2)
    
    # Baseline Free-Space / Chassis Coupling Isolation (dB)
    baseline_isolation_dB = 20 * np.log10(d_meters) + 20 * np.log10(freq_tx_mhz) - 27.55
    
    # ---------------------------------------------------------
    # 4. Multi-Physics Orbital Variables
    # ---------------------------------------------------------
    # Thermal swing across LEO eclipse/sun transition (-40°C to +85°C)
    temp_celsius = 22.5 + 62.5 * np.sin(2 * np.pi * 0.1 * time_s)
    
    # SAW filter temperature drift (TCF = -40 ppm/°C relative to 25°C)
    tcf_ppm = -40.0
    saw_freq_shift_khz = (freq_rx_mhz * 1e6 * tcf_ppm * (temp_celsius - 25.0) * 1e-6) / 1000.0
    
    # LEO Orbital Doppler Shift (+/- 3 kHz shift)
    doppler_shift_khz = 3.0 * np.cos(2 * np.pi * 0.05 * time_s)
    
    # Thermal insertion loss degradation (dB loss when passband detunes)
    saw_thermal_detune_loss_dB = 0.005 * (saw_freq_shift_khz - doppler_shift_khz)**2
    
    # Structural reflections & multipath fading (Gaussian variation)
    multipath_fading_dB = np.random.normal(0, 2.5, num_samples)
    
    # UHF Tx Burst Activity (Time-Division Operation) - active during high pulses
    uhf_tx_active = (np.sin(2 * np.pi * 0.5 * time_s) > 0.5).astype(int)
    
    # ---------------------------------------------------------
    # 5. Mitigation Parameters & Power Calculations
    # ---------------------------------------------------------
    cross_pol_isolation_dB = 25.0    # Orthogonal antenna placement (90 deg)
    shielding_isolation_dB = 15.0    # Faraday cage RF cans
    saw_rejection_dB = 90.0          # Nominal SAW out-of-band rejection
    
    # Unmitigated power entering AIS receiver front-end (dBm)
    p_rx_unmitigated = tx_power_dBm - baseline_isolation_dB + multipath_fading_dB
    p_rx_unmitigated = np.where(uhf_tx_active, p_rx_unmitigated, thermal_noise_floor_dBm)
    
    # Total Hardware Isolation
    effective_saw_rejection = saw_rejection_dB - saw_thermal_detune_loss_dB
    total_mitigation_dB = (baseline_isolation_dB + cross_pol_isolation_dB + 
                           shielding_isolation_dB + effective_saw_rejection)
    
    # Mitigated Power before TDO Blanking
    p_rx_mitigated_raw = tx_power_dBm - total_mitigation_dB + multipath_fading_dB
    
    # Mitigated Power with TDO Blanking applied (LNA muted during UHF transmission)
    p_rx_mitigated_final = np.where(uhf_tx_active, thermal_noise_floor_dBm, p_rx_mitigated_raw)
    
    # Receiver Desensitization Calculation (dB of sensitivity lost)
    tx_leakage_linear = 10**((p_rx_unmitigated - 30) / 10)
    noise_floor_linear = 10**((thermal_noise_floor_dBm - 30) / 10)
    desense_dB = 10 * np.log10(1.0 + (tx_leakage_linear / noise_floor_linear))
    
    # ---------------------------------------------------------
    # 6. Save Telemetry Data to CSV File
    # ---------------------------------------------------------
    fieldnames = [
        "time_s", "temp_celsius", "saw_freq_shift_khz", "doppler_shift_khz",
        "uhf_tx_active", "p_rx_unmitigated_dBm", "p_rx_mitigated_dBm", 
        "desense_dB", "lna_saturated"
    ]
    
    with open(output_csv, mode="w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(fieldnames)
        for i in range(num_samples):
            writer.writerow([
                round(time_s[i], 4),
                round(temp_celsius[i], 2),
                round(saw_freq_shift_khz[i], 3),
                round(doppler_shift_khz[i], 3),
                int(uhf_tx_active[i]),
                round(p_rx_unmitigated[i], 2),
                round(p_rx_mitigated_final[i], 2),
                round(desense_dB[i], 2),
                bool(p_rx_unmitigated[i] >= lna_sat_limit_dBm)
            ])
            
    print(f"SUCCESS: Telemetry data written to {output_csv}")
    
    # ---------------------------------------------------------
    # 7. Generate and Save Simulation Plot
    # ---------------------------------------------------------
    plt.figure(figsize=(12, 8))
    
    # Plot 1: Received Power Comparison
    plt.subplot(2, 1, 1)
    plt.plot(time_s, p_rx_unmitigated, color='crimson', alpha=0.7, label='Unmitigated Interference (Chassis Coupled)')
    plt.plot(time_s, p_rx_mitigated_final, color='forestgreen', linewidth=2, label='Fully Mitigated (SAW + TDO + Orthogonal)')
    plt.axhline(y=lna_sat_limit_dBm, color='black', linestyle='--', label='AIS LNA Saturation Limit (-20 dBm)')
    plt.axhline(y=thermal_noise_floor_dBm, color='blue', linestyle=':', label='Thermal Noise Floor (-133 dBm)')
    plt.title(f'CubeSat AIS/UHF RF Interference Simulation (Diagonal Separation: {d_meters:.3f}m)')
    plt.ylabel('Power at Receiver Port (dBm)')
    plt.ylim(-145, 40)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper right')
    
    # Plot 2: Thermal Drift & Receiver Desense
    plt.subplot(2, 1, 2)
    plt.plot(time_s, temp_celsius, color='darkorange', label='Chassis Temperature (°C)')
    plt.plot(time_s, desense_dB, color='purple', linestyle='--', label='Unmitigated Receiver Desense (dB)')
    plt.title('LEO Orbital Environment: Thermal Drift vs. Receiver Desensitization')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Temperature (°C) / Desense (dB)')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper right')
    
    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    print(f"SUCCESS: Simulation plot saved to {output_png}")
    plt.show()

if __name__ == "__main__":
    run_advanced_cubesat_simulation()