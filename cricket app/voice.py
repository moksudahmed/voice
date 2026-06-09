import asyncio
import threading
import edge_tts
import sounddevice as sd
import soundfile as sf
import pyttsx3
import tempfile
import os
import hashlib

# ============================================================
# GLOBALS
# ============================================================

speech_lock = threading.Lock()

stop_tts_flag = threading.Event()

current_thread = None

is_playing = False

last_text_hash = None

# ============================================================
# RESET FLAG
# ============================================================

def reset_stop_flag():
    """
    Compatibility function.
    Keeps old imports working.
    """
    stop_tts_flag.clear()


# ============================================================
# STOP CURRENT TTS
# ============================================================

def stop_current_tts():
    global is_playing

    print("🛑 STOPPING CURRENT TTS")

    stop_tts_flag.set()

    try:
        sd.stop()
    except Exception:
        pass

    is_playing = False

    print("✅ TTS STOPPED")


# ============================================================
# BANGLA TTS
# ============================================================

def speak_bangla(text: str, force=False):

    global current_thread
    global is_playing
    global last_text_hash

    text = str(text).strip()

    if not text:
        return

    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

    # --------------------------------------------------------
    # Skip duplicate messages
    # --------------------------------------------------------

    if not force and text_hash == last_text_hash:
        print("⏭ Duplicate speech skipped")
        return

    # --------------------------------------------------------
    # Prevent overlapping voices
    # --------------------------------------------------------

    if is_playing:
        print("🎙 Voice already playing")
        return

    stop_tts_flag.clear()

    async def _speak():

        global is_playing
        global last_text_hash

        temp_file = None

        try:

            is_playing = True

            print(f"🎙 SPEAKING: {text}")

            tts = edge_tts.Communicate(
                text=text,
                voice="bn-BD-NabanitaNeural"
            )

            audio_bytes = b""

            async for chunk in tts.stream():

                if stop_tts_flag.is_set():
                    print("⏹ Speech interrupted")
                    return

                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]

            with tempfile.NamedTemporaryFile(
                suffix=".mp3",
                delete=False
            ) as f:

                temp_file = f.name
                f.write(audio_bytes)

            data, sample_rate = sf.read(temp_file)

            sd.play(data, sample_rate)

            while True:

                if stop_tts_flag.is_set():

                    try:
                        sd.stop()
                    except:
                        pass

                    print("⏹ Playback stopped")
                    return

                stream = sd.get_stream()

                if stream is None:
                    break

                if not stream.active:
                    break

                await asyncio.sleep(0.1)

            last_text_hash = text_hash

            print("✅ Speech completed")

        except Exception as e:

            print(f"❌ Bangla TTS Error: {e}")

        finally:

            is_playing = False

            try:
                sd.stop()
            except:
                pass

            if temp_file and os.path.exists(temp_file):

                try:
                    os.remove(temp_file)
                except:
                    pass

    def runner():

        with speech_lock:

            loop = asyncio.new_event_loop()

            try:
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_speak())

            finally:
                loop.close()

    current_thread = threading.Thread(
        target=runner,
        daemon=True
    )

    current_thread.start()

    return current_thread


# ============================================================
# ENGLISH TTS
# ============================================================

def speak_english(text: str):

    def run():

        global is_playing

        if is_playing:
            return

        try:

            is_playing = True

            print(f"🎙 ENGLISH: {text}")

            engine = pyttsx3.init()

            engine.setProperty("rate", 170)
            engine.setProperty("volume", 1.0)

            engine.say(text)

            engine.runAndWait()

            engine.stop()

        except Exception as e:

            print(f"❌ English TTS Error: {e}")

        finally:

            is_playing = False

    threading.Thread(
        target=run,
        daemon=True
    ).start()


# ============================================================
# TEST
# ============================================================
"""
if __name__ == "__main__":

    speak_bangla("বাংলাদেশ ক্রিকেট দলের সবাইকে স্বাগতম")

    input("Press Enter to stop...\n")

    stop_current_tts()"""