"""
config.py
---------
Contains user-changeable parameters for audio detection.

Edit these values to tune thresholds, durations, and sample rates.
"""

### AUDIO SETTINGS ###
SAMPLE_RATE = 44100      # Sample rate in Hz
CHANNELS = 1             # 1 = mono, 2 = stereo
AUBIO_BUF_SIZE = 4096    # FFT size used by aubio
AUBIO_HOP_SIZE = 512     # Hop size for aubio
PYAUDIO_READ_SIZE = 512  # Number of samples to read from pyaudio in each chunk

### DROP DETECTION PARAMETERS ###
DROP_ENERGY_START = 300   # Trigger drop if energy at a beat is above this threshold
DROP_ENERGY_END = 300     # If drop is active, end it when energy falls below this
DROP_MIN_DURATION = 1.0    # Minimum time (seconds) for the DROP to be considered valid

### STROBE DETECTION PARAMETERS ###
STROBE_ENERGY_THRESHOLD = 250       # If lowcut energy > this at a beat -> strobe can start
STROBE_ENERGY_MINIMUM = 75          # If lowcut energy < this at a beat => end strobe
STROBE_COOLDOWN = 5                # Seconds to wait after strobe ends before starting again
NUM_STROBE_BEATS = 8             # Number of beats the strobe will stay active, set to None to disable

### LOW-PASS FILTER SETTINGS ###
LOW_PASS_CUTOFF = 200  # Frequency cutoff for low-pass filter (Hz)
LOW_PASS_ORDER = 4     # Order of the Butterworth filter

SMOOTHING_ALPHA = 0.5  # Smoothing factor for exponential moving average
                       # Smaller = smoother but slower response
                       # Larger  = quicker response but less smoothing