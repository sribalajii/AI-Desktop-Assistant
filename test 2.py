import os
import sys
import json
import webbrowser
from datetime import datetime
import requests
import psutil
import sounddevice as sd
import pyttsx3
import vosk
from pynput import keyboard
import time
import numpy as np

# ---------- CONFIG ----------
MODEL_NAME = "llama2"
OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_API_GENERATE = f"{OLLAMA_HOST}/api/generate"

# Handle both development and packaged paths
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VOSK_MODEL_PATH = os.path.join(BASE_DIR, "models", "vosk-en", "vosk-model-small-en-us-0.15")

HOTKEY_HOLD = keyboard.Key.space
HOTKEY_QUIT = keyboard.Key.esc

SAMPLE_RATE = 16000
CHANNELS = 1

# Audio device selection - Use Realtek Audio microphone (device 12 from your list)
PREFERRED_INPUT_DEVICE = 12  # Microphone (Realtek Audio), Windows WASAPI


# ---------- SIMPLE TTS ----------
def speak(text: str):
    """Simple TTS without threading issues"""
    print("Luna:", text)

    if not text.strip():
        return

    try:
        # Create new engine instance each time
        engine = pyttsx3.init()

        # Try to set to female voice (Zira)
        try:
            engine.setProperty('voice',
                               'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\TTS_MS_EN-US_ZIRA_11.0')
            print("Using Zira voice")
        except:
            print("Using default voice")

        engine.setProperty('rate', 170)
        engine.setProperty('volume', 1.0)
        engine.say(text)
        engine.runAndWait()

    except Exception as e:
        print(f"TTS error: {e}")


# ---------- STT (Vosk) ----------
if not os.path.isdir(VOSK_MODEL_PATH):
    error_msg = "Vosk model not found. Please check the models folder."
    print(error_msg)
    speak("Vosk model not found. Please check the models folder.")
    exit()

vosk_model = vosk.Model(VOSK_MODEL_PATH)
recognizer = vosk.KaldiRecognizer(vosk_model, SAMPLE_RATE)

is_recording = False
record_stream = None
audio_buffer = []


def audio_callback(indata, frames, time, status):
    """Callback to collect audio data"""
    global audio_buffer
    if status:
        print(f"Audio status: {status}")
    # Convert to the format Vosk expects and add to buffer
    audio_buffer.extend(indata.flatten().astype(np.int16).tobytes())


def get_supported_sample_rate(device_id):
    """Find a supported sample rate for the device"""
    # Common sample rates to try (Vosk works with these)
    sample_rates = [44100, 48000, 22050, 16000, 8000]

    for rate in sample_rates:
        try:
            # Test if this sample rate works with the device
            with sd.InputStream(device=device_id, samplerate=rate, channels=1, dtype='int16'):
                print(f"Device supports sample rate: {rate} Hz")
                return rate
        except:
            continue

    # Fallback to default
    return 44100


def start_recording():
    global is_recording, record_stream, audio_buffer, SAMPLE_RATE
    if is_recording:
        return False

    try:
        audio_buffer = []  # Reset audio buffer

        # Try to use the preferred input device, fallback to default if not available
        input_device = None
        try:
            # Check if preferred device exists and is available
            device_info = sd.query_devices(PREFERRED_INPUT_DEVICE)
            if device_info['max_input_channels'] > 0:
                input_device = PREFERRED_INPUT_DEVICE
                print(f"Using audio device: {device_info['name']}")

                # Get supported sample rate for this device
                supported_rate = get_supported_sample_rate(input_device)
                if supported_rate != SAMPLE_RATE:
                    print(f"Adjusting sample rate from {SAMPLE_RATE} to {supported_rate} Hz")
                    SAMPLE_RATE = supported_rate
                    # Update Vosk recognizer with new sample rate
                    global recognizer
                    recognizer = vosk.KaldiRecognizer(vosk_model, SAMPLE_RATE)
        except Exception as e:
            print(f"Preferred device error: {e}, using default")

        record_stream = sd.InputStream(
            device=input_device,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            callback=audio_callback,
            dtype='int16',
            blocksize=1024
        )
        record_stream.start()
        is_recording = True
        print("[REC] Started recording")
        return True
    except Exception as e:
        print("Start recording error:", e)
        is_recording = False
        return False


def simple_resample(audio_data, original_rate, target_rate):
    """Simple but effective resampling using linear interpolation"""
    if original_rate == target_rate:
        return audio_data

    # Calculate the ratio
    ratio = target_rate / original_rate
    new_length = int(len(audio_data) * ratio)

    # Create new time indices
    old_indices = np.linspace(0, len(audio_data) - 1, len(audio_data))
    new_indices = np.linspace(0, len(audio_data) - 1, new_length)

    # Interpolate
    resampled = np.interp(new_indices, old_indices, audio_data.astype(np.float32))

    return resampled.astype(np.int16)


def stop_recording():
    global is_recording, record_stream, audio_buffer
    if not is_recording:
        return ""

    try:
        record_stream.stop()
        record_stream.close()
        is_recording = False
        print("[REC] Stopped recording")

        # Process the collected audio data
        if len(audio_buffer) == 0:
            print("No audio data collected")
            return ""

        # Convert buffer to bytes if it's not already
        audio_bytes = bytes(audio_buffer)
        print(f"Processing {len(audio_bytes)} bytes of audio data")

        # Convert to numpy array for processing
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)

        # If sample rate was changed from 16000, we need to resample for Vosk
        if SAMPLE_RATE != 16000:
            print(f"Resampling from {SAMPLE_RATE}Hz to 16000Hz")
            audio_array = simple_resample(audio_array, SAMPLE_RATE, 16000)

        # Apply audio processing to improve recognition
        audio_float = audio_array.astype(np.float32)

        # Normalize audio to improve recognition (but preserve dynamic range)
        max_val = np.max(np.abs(audio_float))
        if max_val > 0:
            # Normalize to 70% of max range to avoid clipping
            audio_float = audio_float / max_val * 22000

        # Simple noise gate - remove very quiet parts
        noise_floor = np.std(audio_float) * 0.1
        audio_float = np.where(np.abs(audio_float) < noise_floor, 0, audio_float)

        # Convert back to int16
        audio_array = np.clip(audio_float, -32768, 32767).astype(np.int16)
        audio_bytes = audio_array.tobytes()

        # Check if we have meaningful audio data
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        print(f"Audio RMS level: {rms:.1f}")

        if rms < 100:  # Very quiet audio
            print("Audio level too low - try speaking louder or closer to microphone")
            return ""

        # Feed the audio data to Vosk in chunks
        text = ""
        chunk_size = 4000
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i + chunk_size]
            if recognizer.AcceptWaveform(chunk):
                result = json.loads(recognizer.Result())
                chunk_text = result.get('text', '').strip()
                if chunk_text:
                    text += " " + chunk_text
                    print(f"Partial result: '{chunk_text}'")

        # Get final result
        final_result = json.loads(recognizer.FinalResult())
        final_text = final_result.get('text', '').strip()
        if final_text:
            text += " " + final_text
            print(f"Final result: '{final_text}'")

        text = text.strip()
        if text:
            print(f"Recognized: '{text}'")
            return text
        else:
            print("No speech recognized")
            return ""

    except Exception as e:
        print("Stop recording error:", e)
        return ""


# ---------- Check if Ollama is running ----------
def is_ollama_running():
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False


# ---------- Local commands ----------
def tell_time():
    return "It is " + datetime.now().strftime("%I:%M %p")


def tell_date():
    return datetime.now().strftime("%A, %d %B %Y")


def battery_status():
    try:
        b = psutil.sensors_battery()
        if b is None:
            return "Battery information not available."
        status = "plugged in" if b.power_plugged else "not plugged in"
        return f"Battery is at {int(b.percent)} percent and is {status}."
    except Exception:
        return "Cannot read battery status."


def local_intent(text):
    t = text.lower().strip()
    if not t:
        return None

    # Greetings
    if any(word in t for word in ["hello", "hi", "hey", "greetings", "luna"]):
        return "Hello! How can I help you today?"

    if any(word in t for word in ["thank", "thanks", "appreciate"]):
        return "You're welcome! Is there anything else I can help with?"

    # System commands
    if any(k in t for k in ("exit", "quit", "stop", "shutdown", "goodbye")):
        return "EXIT_NOW"

    if any(k in t for k in ("time", "what time", "current time", "clock")):
        return tell_time()

    if any(k in t for k in ("date", "what day", "today", "current date")):
        return tell_date()

    if any(k in t for k in ("battery", "power", "charge")):
        return battery_status()

    if t.startswith("open "):
        target = t[5:].strip()
        if "youtube" in target:
            webbrowser.open("https://youtube.com")
            return "Opening YouTube."
        if "google" in target:
            webbrowser.open("https://google.com")
            return "Opening Google."
        return f"Opening {target}."

    return None


# ---------- Ollama call ----------
def ask_ollama(prompt: str) -> str:
    if not is_ollama_running():
        return "Ollama is not running. Please start it manually."

    try:
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "system": "You are Luna, a helpful AI assistant. Keep replies concise and conversational. Do not use emojis, emoticons, or special characters in your responses. Speak in a natural, friendly tone without visual elements.",
            "stream": False
        }

        response = requests.post(OLLAMA_API_GENERATE, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        return data.get("response", "").strip() or "I didn't understand that."

    except Exception as e:
        print(f"Ollama error: {e}")
        return "Sorry, I couldn't connect to the AI."


# ---------- Main processing ----------
def process_command():
    text = stop_recording()
    if not text:
        speak("I didn't catch that. Please try again.")
        return

    # Check for local commands first
    local_response = local_intent(text)
    if local_response == "EXIT_NOW":
        speak("Goodbye!")
        exit()
    elif local_response:
        speak(local_response)
        return

    # Use Ollama for other questions
    if not is_ollama_running():
        speak("Ollama is not running. I can only answer basic questions.")
        return

    speak("Let me think about that.")
    response = ask_ollama(text)
    speak(response)


# ---------- Hotkey listener ----------
def on_press(key):
    if key == HOTKEY_HOLD and not is_recording:
        if start_recording():
            print("Listening...")


def on_release(key):
    if key == HOTKEY_HOLD:
        process_command()
    elif key == HOTKEY_QUIT:
        speak("Goodbye!")
        exit()


# ---------- Main ----------
if __name__ == "__main__":
    # Print available audio devices for debugging
    print("Available audio devices:")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"{i}: {device['name']} (INPUT)")
    print(f"\nUsing device {PREFERRED_INPUT_DEVICE} for input")
    print("-" * 50)

    # Simple startup message
    speak("I'm Luna. Press and hold SPACE to speak, press ESC to exit.")

    # Start listening for hotkeys
    print("Luna is ready. Hold SPACE to speak, ESC to quit.")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            speak("Goodbye!")