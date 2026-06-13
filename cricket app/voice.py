import asyncio
import threading
import edge_tts
import sounddevice as sd
import soundfile as sf
import pyttsx3
import tempfile
import os
import time
import queue
from collections import deque
import warnings

warnings.filterwarnings("ignore")

# ======================= GLOBAL STATE =======================
stop_tts_flag = threading.Event()
is_playing = False
tts_queue = queue.Queue()
worker_thread = None
processing_lock = threading.Lock()

# ======================= STOP FUNCTION =======================
def stop_current_tts():
    """Stop any currently playing TTS"""
    global is_playing
    print("🛑 STOPPING CURRENT TTS...")
    stop_tts_flag.set()
    is_playing = False
    try:
        sd.stop()
    except:
        pass
    return True

def reset_stop_flag():
    """Reset stop flag"""
    global stop_tts_flag
    stop_tts_flag.clear()

# ======================= BANGLA TTS (NON-BLOCKING) =======================
def speak_bangla(text: str):
    """Internal function to actually play Bangla TTS"""
    global is_playing
    
    def play():
        global is_playing
        temp_file = None
        
        try:
            print(f"🎙 Playing: {text[:50]}...")
            
            # Generate audio
            async def get_audio():
                tts = edge_tts.Communicate(text, "bn-BD-NabanitaNeural")
                result = b""
                async for chunk in tts.stream():
                    if chunk["type"] == "audio":
                        result += chunk["data"]
                return result
            
            # Run async generation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio_data = loop.run_until_complete(get_audio())
            loop.close()
            
            if stop_tts_flag.is_set() or not audio_data:
                print("⏹️ Stopped before playback")
                return
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                temp_file = f.name
            
            # Play audio
            data, fs = sf.read(temp_file)
            
            if not stop_tts_flag.is_set():
                sd.play(data, fs)
                print("🔊 Playing...")
                
                # Wait for completion
                while sd.get_stream() and sd.get_stream().active:
                    time.sleep(0.05)
                    if stop_tts_flag.is_set():
                        sd.stop()
                        print("⏹️ Stopped by user")
                        return
                
                print("✅ Completed")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
            is_playing = False
    
    reset_stop_flag()
    is_playing = True
    thread = threading.Thread(target=play, daemon=True)
    thread.start()
    
    # Wait for the thread to actually start playing
    time.sleep(0.1)
    return thread

# ======================= ENGLISH TTS =======================
def speak_english(text: str):
    """Internal function for English TTS"""
    global is_playing
    
    def play():
        global is_playing
        try:
            print(f"🎙 English: {text[:50]}...")
            engine = pyttsx3.init()
            engine.setProperty("rate", 170)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
            print("✅ English completed")
        except Exception as e:
            print(f"❌ English error: {e}")
        finally:
            is_playing = False
    
    is_playing = True
    thread = threading.Thread(target=play, daemon=True)
    thread.start()
    return thread

# ======================= TTS QUEUE MANAGER (SOLUTION) =======================
class TTSManager:
    """Manages TTS queue to prevent overlapping"""
    
    def __init__(self):
        self.queue = deque()
        self.current_playing = False
        self.lock = threading.Lock()
        self.worker = None
        self.stop_requested = False
    
    def add(self, text, lang="bn", priority=False):
        """Add TTS to queue"""
        with self.lock:
            if priority:
                # Add to front of queue
                self.queue.appendleft((text, lang))
            else:
                self.queue.append((text, lang))
            
            # Start worker if not running
            if not self.current_playing:
                self._start_worker()
    
    def clear(self):
        """Clear all pending TTS"""
        with self.lock:
            self.queue.clear()
            self.stop_requested = True
            # Stop current playback
            if self.current_playing:
                stop_current_tts()
                self.current_playing = False
            self.stop_requested = False
    
    def _start_worker(self):
        """Start worker thread"""
        if self.worker is None or not self.worker.is_alive():
            self.worker = threading.Thread(target=self._process_queue, daemon=True)
            self.worker.start()
    
    def _process_queue(self):
        """Process TTS queue sequentially"""
        while True:
            # Check if there's work to do
            with self.lock:
                if not self.queue and not self.current_playing:
                    self.current_playing = False
                    break
                
                if self.current_playing or not self.queue:
                    time.sleep(0.1)
                    continue
                
                text, lang = self.queue.popleft()
                self.current_playing = True
            
            # Play the TTS
            try:
                if lang == "bn":
                    speak_bangla(text)
                else:
                    speak_english(text)
                
                # Wait for completion
                while self.current_playing and not self.stop_requested:
                    time.sleep(0.1)
                    with self.lock:
                        if not is_playing:
                            self.current_playing = False
                            break
                            
            except Exception as e:
                print(f"Queue error: {e}")
                with self.lock:
                    self.current_playing = False
            
            # Small delay between items
            time.sleep(0.2)

# ======================= SINGLETON INSTANCE =======================
tts_manager = TTSManager()

# ======================= PUBLIC API =======================
def speak(text: str, lang="bn", priority=False):
    """
    Main function to speak text
    - Automatically queues if something is playing
    - Use priority=True for urgent messages
    """
    # Replace {result} placeholder if needed
    text = text.replace("{result}", "")
    
    # Add to queue
    tts_manager.add(text, lang, priority)

def speak_immediate(text: str, lang="bn"):
    """
    Clear queue and speak immediately (for urgent messages)
    """
    tts_manager.clear()
    speak(text, lang, priority=True)

def stop_all():
    """Stop all TTS and clear queue"""
    tts_manager.clear()
    stop_current_tts()

# ======================= FOR YOUR MATCH EVENT HANDLER =======================
def handle_match_event(event_type: str, message: str):
    """
    Handle match events without overlapping
    """
    # Clean the message
    clean_message = message.replace("{result}", "").strip()
    
    if event_type == "TIME_OUT":
        # Use immediate for timeout events
        speak_immediate(clean_message, "bn")
    elif event_type == "COMPLETED_WITH_RESULT":
        # Normal priority for completion
        speak(clean_message, "bn")
    else:
        # Default
        speak(clean_message, "bn")

# ======================= TEST =======================
if __name__ == "__main__":
    print("=" * 60)
    print("TTS Queue Manager Test")
    print("=" * 60)
    
    # Test 1: Sequential messages (should play one after another)
    print("\n📝 Test 1: Sequential messages")
    speak("প্রথম বার্তা", "bn")
    time.sleep(0.5)
    speak("দ্বিতীয় বার্তা", "bn")
    time.sleep(0.5)
    speak("তৃতীয় বার্তা", "bn")
    time.sleep(5)
    
    # Test 2: Rapid messages (should queue properly)
    print("\n📝 Test 2: Rapid messages")
    for i in range(5):
        speak(f"বার্তা {i+1}", "bn")
        time.sleep(0.1)  # Rapid fire
    time.sleep(6)  # Wait for all to complete
    
    # Test 3: Priority (should interrupt)
    print("\n📝 Test 3: Priority message")
    speak("এটি একটি দীর্ঘ বার্তা যা বাজতে থাকবে", "bn")
    time.sleep(1)
    speak_immediate("জরুরী বার্তা!", "bn")  # This should play immediately
    time.sleep(4)
    
    # Test 4: Stop all
    print("\n📝 Test 4: Stop all")
    speak("এই বার্তাটি বন্ধ করা হবে", "bn")
    time.sleep(0.5)
    stop_all()
    time.sleep(1)
    
    print("\n✅ All tests completed!")

# ======================= INTEGRATION WITH YOUR EXISTING CODE =======================
"""
Replace your existing speak_bangla() calls with:

Instead of:
    speak_bangla("some text")

Use:
    speak("some text", "bn")  # For normal priority
    speak_immediate("urgent text", "bn")  # For urgent messages

For English:
    speak("some text", "en")

To stop everything:
    stop_all()
"""