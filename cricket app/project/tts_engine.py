import asyncio
import edge_tts
import sounddevice as sd
import soundfile as sf
import os

# =====================================================
# TTS QUEUE
# =====================================================

tts_queue = asyncio.Queue()

# =====================================================
# VOICE CONFIG
# =====================================================

VOICE = "bn-BD-NabanitaNeural"
TEMP_FILE = "temp_tts.wav"

# =====================================================
# TTS WORKER (runs forever)
# =====================================================

async def tts_worker():

    while True:

        text = await tts_queue.get()

        if not text:
            continue

        try:
            print(f"🔊 Speaking: {text}")

            # Generate speech
            communicate = edge_tts.Communicate(
                text,
                VOICE
            )

            await communicate.save(TEMP_FILE)

            # Load audio
            data, fs = sf.read(TEMP_FILE, dtype='float32')

            # Play audio (blocking until finished)
            sd.play(data, fs)
            sd.wait()

            # Cleanup
            if os.path.exists(TEMP_FILE):
                os.remove(TEMP_FILE)

        except Exception as e:
            print("❌ TTS ERROR:", e)

        finally:
            tts_queue.task_done()

# =====================================================
# ADD TEXT TO QUEUE
# =====================================================

async def speak(text: str):

    await tts_queue.put(text)

# =====================================================
# RUNNER (START SYSTEM)
# =====================================================

async def start_tts_system():

    worker = asyncio.create_task(tts_worker())

    return worker

# =====================================================
# EXAMPLE USAGE
# =====================================================

async def demo():

    await start_tts_system()

    # Sample cricket commentary (Bangla)
    await speak("ছক্কা! বলটা স্টেডিয়ামের বাইরে চলে গেছে!")
    await speak("দারুণ বোলিং, উইকেট তুলে নিল বোলার!")
    await speak("এক রান নেওয়া হলো। ম্যাচ জমে উঠেছে!")

    # Keep alive
    while True:
        await asyncio.sleep(1)

# =====================================================
# MAIN ENTRY
# =====================================================

if __name__ == "__main__":

    asyncio.run(demo())