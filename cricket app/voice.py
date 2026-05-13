import asyncio
import threading
import edge_tts
import sounddevice as sd
import soundfile as sf
import pyttsx3
speech_lock = threading.Lock()

def speak_bangla(text: str):

    async def _speak():

        try:
            print("🎙 AI SPEAK (BN):", text)

            output_file = "temp_bn.mp3"

            tts = edge_tts.Communicate(
                text,
                "bn-BD-NabanitaNeural"
            )

            await tts.save(output_file)

            data, fs = sf.read(output_file)

            sd.play(data, fs)
            sd.wait()

        except Exception as e:
            print("❌ TTS ERROR:", e)

    def runner():
        with speech_lock:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_speak())
            loop.close()

    threading.Thread(
        target=runner,
        daemon=True
    ).start()

def speak_english(text: str):
    def run():
        with speech_lock:
            try:
                print("🎙 SPEAKING:", text)

                engine = pyttsx3.init()   # 🔥 NEW ENGINE EVERY TIME
                engine.setProperty("rate", 170)
                engine.setProperty("volume", 1.0)                

                engine.say(text)
                engine.runAndWait()

            except Exception as e:
                print("TTS ERROR:", e)

    threading.Thread(target=run, daemon=True).start()
