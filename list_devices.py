import sounddevice as sd

print(f"sounddevice version: {sd.__version__}")
print(f"PortAudio version:   {sd.get_portaudio_version()}")
print()

devices = sd.query_devices()
for i, d in enumerate(devices):
    api = sd.query_hostapis(d["hostapi"])["name"]
    print(f"  [{i:2d}] {api:20s}  in={d['max_input_channels']}  out={d['max_output_channels']}  {d['name']}")
