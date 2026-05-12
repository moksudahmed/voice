import edge_tts
import asyncio

async def speak(text):
    communicate = edge_tts.Communicate(text, "en-IN-NeerjaNeural")
    await communicate.save("temp.wav")

    import sounddevice as sd
    import soundfile as sf

    data, fs = sf.read("temp.wav")
    sd.play(data, fs, device="CABLE Input")
    sd.wait()