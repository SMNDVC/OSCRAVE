import soundcard as sc

# Replace with the exact name you found:
LOOPBACK_DEVICE_NAME = "Monitor of Built-in Audio Analog Stereo"

# Create the Microphone object
mic = sc.get_microphone(LOOPBACK_DEVICE_NAME)

# Now mic should represent your system’s loopback/monitor device
with mic.recorder(samplerate=44100, channels=2) as stream:
    data = stream.record(numframes=1024)
    print("Data shape:", data.shape)
    print("First few samples:", data[:10])
