"""
main.py
-------
Implements beat-synced DROP and STROBE detection with exponential smoothing.

- DROP detection: triggered on beats using the global (full-spectrum) energy.
- STROBE detection (beat-synced), exclusively uses NUM_STROBE_BEATS:
    * Start on beat if smoothed lowcut energy > STROBE_ENERGY_THRESHOLD
      and cooldown has passed.
    * End on beat if:
        (1) the number of strobe beats >= NUM_STROBE_BEATS (and then start cooldown), OR
        (2) the lowcut energy < STROBE_ENERGY_MINIMUM (end strobe, no cooldown).
    * No time-based strobe limit.

Sends OSC messages to:
    - /beat
    - /strobe

Prints:
    - "Strobe ON!" / "Strobe OFF!"
    - Beat info ("Beat detected!") with global/lowcut energies and a [DROP] tag if DROP is active
"""

import time
import numpy as np
import pyaudio
import aubio
from pythonosc import udp_client
from scipy.signal import butter, filtfilt

import config  # user settings from config.py

# ----------------------------------
# OSC SETUP
# ----------------------------------
OSC_IP = "127.0.0.1"
OSC_PORT = 7700
OSC_BEAT = "/beat"
OSC_STROBE = "/strobe"
OSC_STROBE_OFF = "/strobeoff"

# ----------------------------------
# GLOBAL STATE
# ----------------------------------
drop_active = False
drop_start_time = 0

# Smoothed energies
smoothed_global_energy = 0.0  # For DROP detection
smoothed_strobe_energy = 0.0  # For STROBE detection

# STROBE logic
strobe_active = False
strobe_start_beat_count = 0
strobe_last_end_time = time.time()  # for cooldown

# We'll keep track of total beats counted
beat_count = 0


def smooth_value(new_val, old_val, alpha):
    """
    Exponential moving average:
      new_val: latest raw measurement
      old_val: previous smoothed measurement
      alpha:   smoothing factor (0 < alpha <= 1)
    """
    return old_val + alpha * (new_val - old_val)


def low_pass_filter(samples):
    """
    Low-pass Butterworth filter to emphasize bass frequencies.
    """
    nyquist = 0.5 * config.SAMPLE_RATE
    normal_cutoff = config.LOW_PASS_CUTOFF / nyquist

    b, a = butter(config.LOW_PASS_ORDER, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, samples)


def compute_global_energy(samples):
    """
    Compute summed absolute FFT values across the full frequency range.
    """
    fft_result = np.abs(np.fft.rfft(samples))
    return np.sum(fft_result)


def compute_filtered_energy(samples):
    """
    Compute summed absolute FFT values after applying a low-pass filter.
    """
    filtered = low_pass_filter(samples)
    fft_result = np.abs(np.fft.rfft(filtered))
    return np.sum(fft_result)


def detect_drop_on_beat(smoothed_energy):
    """
    DROP detection on a beat using the smoothed global (full-spectrum) energy.

    - If energy > DROP_ENERGY_START and not active => start DROP.
    - If energy < DROP_ENERGY_END and active for at least DROP_MIN_DURATION => end DROP.
    """
    global drop_active, drop_start_time

    current_time = time.time()

    # Start DROP
    if (smoothed_energy > config.DROP_ENERGY_START) and (not drop_active):
        drop_active = True
        drop_start_time = current_time

    # End DROP
    if drop_active and (smoothed_energy < config.DROP_ENERGY_END):
        if (current_time - drop_start_time) >= config.DROP_MIN_DURATION:
            drop_active = False


def strobe_logic_on_beat(osc_client, strobe_energy):
    """
    Beat-synced strobe logic using only NUM_STROBE_BEATS:

    * Start strobe if:
        - strobe is off
        - strobe_energy > STROBE_ENERGY_THRESHOLD
        - cooldown has passed since last strobe end
    * End strobe if:
        - we've hit/exceeded NUM_STROBE_BEATS (start cooldown)
        - strobe_energy < STROBE_ENERGY_MINIMUM (end strobe, no cooldown)
    """
    global strobe_active, strobe_start_beat_count, strobe_last_end_time
    global beat_count

    current_time = time.time()

    if not strobe_active:
        # Possibly turn strobe ON
        if strobe_energy > config.STROBE_ENERGY_THRESHOLD:
            # Check if cooldown has passed
            if (current_time - strobe_last_end_time) > config.STROBE_COOLDOWN:
                strobe_active = True
                strobe_start_beat_count = beat_count

                print("Strobe ON!")
                osc_client.send_message(OSC_STROBE, 1)
    else:
        # Strobe is ON, decide if we should turn it OFF
        strobe_beats_elapsed = beat_count - strobe_start_beat_count

        # Condition A: # of strobe beats used up => end strobe + start cooldown
        if config.NUM_STROBE_BEATS != None:
            if strobe_beats_elapsed >= config.NUM_STROBE_BEATS:
                print("Strobe OFF!")
                osc_client.send_message(OSC_STROBE_OFF, 1)
                strobe_active = False
                strobe_last_end_time = current_time  # begin cooldown
                return  # we already ended strobe, so stop here

        # Condition B: strobe energy fell below min => end strobe, NO cooldown
        if strobe_energy < config.STROBE_ENERGY_MINIMUM:
            print("Strobe OFF!")
            osc_client.send_message(OSC_STROBE_OFF, 1)
            strobe_active = False
            # no cooldown started in this scenario


def get_input_device_index():
    """
    Finds the PyAudio input device index for 'pulse' or other suitable device.
    Adjust to suit your environment if needed.
    """
    p = pyaudio.PyAudio()
    device_index = None

    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if "pulse" in info["name"].lower():
            device_index = i
            break

    p.terminate()

    if device_index is None:
        raise ValueError("Could not find a suitable input device (e.g., 'pulse').")
    return device_index


def main():
    # Create OSC client
    osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

    # Prepare PyAudio
    p = pyaudio.PyAudio()
    device_index = get_input_device_index()

    monitor_device = next(
        (
            i for i in range(p.get_device_count())
            if "monitor" in p.get_device_info_by_index(i)["name"].lower()
            and p.get_device_info_by_index(i)["max_input_channels"] > 0
        ),
        None
    )

    if monitor_device is not None:
        dev_info = p.get_device_info_by_index(monitor_device)
        print(f"Found monitor device: index={monitor_device}, name={dev_info['name']}")
        chosen_device_index = monitor_device
    else:
        print("No monitor device found; using default device index from get_input_device_index().")
        dev_info = p.get_device_info_by_index(device_index)
        print(f"Default device: index={device_index}, name={dev_info['name']}")
        chosen_device_index = device_index

    stream = p.open(
        format=pyaudio.paFloat32,
        channels=config.CHANNELS,
        rate=config.SAMPLE_RATE,
        input=True,
        input_device_index=chosen_device_index,
        frames_per_buffer=config.PYAUDIO_READ_SIZE
    )

    # Set up Aubio beat detector
    beat_detector = aubio.tempo("default",
                                config.AUBIO_BUF_SIZE,
                                config.AUBIO_HOP_SIZE,
                                config.SAMPLE_RATE)
    beat_detector.set_silence(-40)
    beat_detector.set_threshold(0.1)

    print("Listening for audio...\nPress Ctrl+C to stop.")

    global smoothed_global_energy, smoothed_strobe_energy
    global beat_count

    try:
        while True:
            # 1) Read an audio chunk
            audio_data = stream.read(config.PYAUDIO_READ_SIZE, exception_on_overflow=False)
            samples = np.frombuffer(audio_data, dtype=aubio.float_type)

            # 2) Continuously compute & smooth strobe energy
            raw_strobe_energy = compute_filtered_energy(samples)
            if smoothed_strobe_energy == 0.0:
                smoothed_strobe_energy = raw_strobe_energy

            smoothed_strobe_energy = smooth_value(
                new_val=raw_strobe_energy,
                old_val=smoothed_strobe_energy,
                alpha=config.SMOOTHING_ALPHA
            )

            # 3) Check for all beats in this chunk
            while True:
                beat_onset = beat_detector(samples)
                if beat_onset == 0:
                    break

                # We got a beat
                beat_count += 1

                # (a) Update & smooth global energy for DROP
                raw_global_energy = compute_global_energy(samples)
                if smoothed_global_energy == 0.0:
                    smoothed_global_energy = raw_global_energy

                smoothed_global_energy = smooth_value(
                    new_val=raw_global_energy,
                    old_val=smoothed_global_energy,
                    alpha=config.SMOOTHING_ALPHA
                )

                # (b) DROP detection on this beat
                detect_drop_on_beat(smoothed_global_energy)

                # (c) STROBE detection on this beat
                strobe_logic_on_beat(osc_client, strobe_energy=smoothed_strobe_energy)

                # (d) Print beat info
                bpm = beat_detector.get_bpm()
                drop_msg = "[DROP]" if drop_active else ""
                print(
                    f"Beat detected! (BPM ~ {bpm:.1f}) | "
                    f"Global: {smoothed_global_energy:.2f} | "
                    f"Lowcut: {smoothed_strobe_energy:.2f} {drop_msg}"
                )

                # (e) Send OSC /beat:
                #     - If DROP is active => every beat
                #     - Else => every other beat
                if drop_active or (beat_count % 2 == 0):
                    osc_client.send_message(OSC_BEAT, 255)

    except KeyboardInterrupt:
        print("\nStopping audio detection...")

    finally:
        # Properly close resources
        stream.stop_stream()
        stream.close()
        p.terminate()


if __name__ == "__main__":
    main()
