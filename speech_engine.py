import speech_recognition as sr
import asyncio
import logging
import edge_tts
import pygame
import os
import tempfile
import hashlib
from faster_whisper import WhisperModel

# logging.basicConfig(level=logging.INFO)

# Initialize Pygame Mixer
try:
    pygame.mixer.init()
except Exception as e:
    logging.error(f"Failed to initialize Pygame mixer: {e}")

# Voice Configuration
VOICE = "en-GB-RyanNeural" 

# Initialize Faster Whisper (Load once)
# Use 'tiny' or 'base' for speed on CPU. 'small' or 'medium' for accuracy.
MODEL_SIZE = "base.en" 
try:
    logging.info(f"Loading Faster Whisper Model ({MODEL_SIZE})...")
    whisper_model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    logging.info("Faster Whisper Loaded.")
except Exception as e:
    logging.error(f"Failed to load Faster Whisper: {e}")
    whisper_model = None

# TTS Cache
CACHE_DIR = os.path.join(os.getcwd(), "tts_cache")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

_is_speaking = False

def stop_speaking():
    """Stops the current speech playback immediately."""
    global _is_speaking
    _is_speaking = False
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
    except Exception as e:
        logging.error(f"Error stopping speech: {e}")

async def speak(text):
    """Generates speech using Edge-TTS and plays it with Pygame (with Caching)."""
    global _is_speaking
    if not text:
        return

    # Check for interruption before starting
    if not pygame.mixer.get_init():
        return

    try:
        # Generate filename based on text hash
        text_hash = hashlib.md5(text.encode()).hexdigest()
        audio_file = os.path.join(CACHE_DIR, f"{text_hash}.mp3")
        
        # Generate if not cached
        if not os.path.exists(audio_file):
            communicate = edge_tts.Communicate(text, VOICE)
            await communicate.save(audio_file)
        
        # Play
        _is_speaking = True
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        
        # Wait for playback to finish
        while pygame.mixer.music.get_busy() and _is_speaking:
            await asyncio.sleep(0.1)
            
        if not _is_speaking:
            pygame.mixer.music.stop()
            
        pygame.mixer.music.unload()
        _is_speaking = False
            
    except Exception as e:
        logging.error(f"Edge-TTS Error: {e}")
        _is_speaking = False

def speak_sync(text):
    """Synchronous wrapper for speak."""
    asyncio.run(speak(text))

def listen_sync():
    """Listens using SpeechRecognition but transcribes with Faster Whisper."""
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    
    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            logging.info("Listening...")
            try:
                # Capture audio
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                return None
        
        logging.info("Transcribing with Faster Whisper...")
        
        # Save to temp file for Whisper (it needs a file path or similar)
        # We can also pass raw bytes but file is safer for format
        temp_wav = os.path.join(tempfile.gettempdir(), "temp_command.wav")
        with open(temp_wav, "wb") as f:
            f.write(audio.get_wav_data())
            
        if whisper_model:
            segments, info = whisper_model.transcribe(temp_wav, beam_size=5)
            command = " ".join([segment.text for segment in segments]).strip().lower()
        else:
            # Fallback if model failed to load
            logging.warning("Faster Whisper not loaded, falling back to Google.")
            command = recognizer.recognize_google(audio).lower()
            
        # Cleanup
        try:
            os.remove(temp_wav)
        except:
            pass
            
        logging.info(f"User said: {command}")
        return command
            
    except Exception as e:
        logging.error(f"Speech Error: {e}")
        return None

async def listen():
    return await asyncio.to_thread(listen_sync)
