import edge_tts
import asyncio
import threading
import io
from pydub import AudioSegment
import simpleaudio as sa

speech_lock = threading.Lock()

def speak(text: str):
    if not STATE["voice_enabled"]:
        return

    def run():
        with speech_lock:
            try:
                print("🎙 SPEAKING (BN):", text)

                audio_bytes = asyncio.run(generate_audio(text))

                play_audio(audio_bytes)

            except Exception as e:
                print("TTS ERROR:", e)

    threading.Thread(target=run, daemon=True).start()


# =========================================
# 🎧 GENERATE AUDIO (EDGE TTS)
# =========================================
async def generate_audio(text):
    communicate = edge_tts.Communicate(
        text=text,
        voice="bn-BD-NabanitaNeural",
        rate="+15%"
    )

    audio_stream = b""

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_stream += chunk["data"]

    return audio_stream


# =========================================
# 🔊 PLAY AUDIO (NO pygame!)
# =========================================
def play_audio(audio_bytes):
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")

        playback = sa.play_buffer(
            audio.raw_data,
            num_channels=audio.channels,
            bytes_per_sample=audio.sample_width,
            sample_rate=audio.frame_rate
        )

        playback.wait_done()

    except Exception as e:
        print("AUDIO ERROR:", e)