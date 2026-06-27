import os
import sys
import json
import webbrowser
import subprocess
import time
import threading
from datetime import datetime
import requests
import psutil
import pyttsx3
from urllib.parse import quote
import re
import gc

# Only import speech libraries if available (graceful degradation)
try:
    import speech_recognition as sr
    import pyaudio

    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

# ---------- FIXED CONFIG ----------
MODEL_NAME = "llama2"
OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_API_GENERATE = f"{OLLAMA_HOST}/api/generate"

# FIXED: More reasonable memory threshold
MAX_MEMORY_USAGE = 92  # Increased from 80% to 92%
REQUEST_TIMEOUT = 15
MEMORY_CHECK_INTERVAL = 10  # Check memory every 10 interactions, not every time

# Handle paths
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Contact database
CONTACTS = {
    "raj": "+919876543210",
    "mom": "+919876543211",
    "dad": "+919876543212",
    "boss": "+919876543213"
}

# Knowledge base
KNOWLEDGE_BASE = {
    "briyani": "To make chicken biryani: Soak rice 30 min, marinate chicken 1 hour, fry onions golden, cook chicken tender, boil rice 70%, layer with saffron and ghee, cook dum 45 min.",
    "biryani": "To make chicken biryani: Soak rice 30 min, marinate chicken 1 hour, fry onions golden, cook chicken tender, boil rice 70%, layer with saffron and ghee, cook dum 45 min.",
    "weather": "I cannot check live weather, but I can open a weather website for you.",
    "python": "Python is a simple, readable programming language great for beginners and professionals.",
    "health": "For health advice, consult a doctor. General tips: drink water, exercise, balanced diet, good sleep.",
    "motivation": "Every day is a chance to improve. Stay focused and keep moving forward!"
}

# Global variables
VOICE_MODE = False
PHONE_CONNECTED = False
recognizer = None
microphone = None
memory_check_counter = 0


# ---------- FIXED MEMORY MANAGEMENT ----------
def check_system_resources():
    """Fixed memory check - less aggressive"""
    global memory_check_counter

    # Only check memory occasionally, not every time
    memory_check_counter += 1
    if memory_check_counter < MEMORY_CHECK_INTERVAL:
        return True

    memory_check_counter = 0  # Reset counter

    try:
        memory = psutil.virtual_memory()
        if memory.percent > MAX_MEMORY_USAGE:
            print(f"⚠️ Memory at {memory.percent}% - cleaning up...")
            gc.collect()
            time.sleep(1)  # Short pause, then continue
            return True  # Don't block operation, just clean up
        return True
    except Exception:
        return True


def cleanup_resources():
    """Gentle cleanup"""
    try:
        gc.collect()
    except Exception:
        pass


# ---------- FIXED TTS ----------
def speak(text: str):
    """Fixed TTS - no resource blocking"""
    if not text.strip():
        return

    print("Luna:", text)

    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 180)
        engine.setProperty('volume', 0.9)

        # Use default voice for speed
        engine.say(text)
        engine.runAndWait()
        engine.stop()
        del engine

    except Exception as e:
        print(f"TTS error: {e}")


# ---------- IMPROVED BLUETOOTH & PHONE DETECTION ----------
def check_bluetooth_earbuds():
    """Improved detection for Noise Buds VS201 and phone"""
    global PHONE_CONNECTED

    try:
        # Check for your specific earbuds "Noise Buds VS201"
        result = subprocess.run([
            'powershell', '-Command',
            'Get-PnpDevice | Where-Object {$_.FriendlyName -like "*Noise*" -or $_.FriendlyName -like "*VS201*" -or $_.FriendlyName -like "*Buds*" -or $_.FriendlyName -like "*Sri*" -or $_.FriendlyName -like "*F02s*"} | Select-Object FriendlyName, Status'
        ], capture_output=True, text=True, timeout=8)

        if result.returncode == 0:
            devices = result.stdout.lower()
            print(f"Bluetooth scan result:\n{result.stdout}")

            # Check for earbuds
            earbuds_found = any(keyword in devices for keyword in [
                'noise', 'vs201', 'buds', 'headphone', 'audio', 'a2dp'
            ])

            # Check for phone (Sri's F02s)
            phone_found = any(keyword in devices for keyword in [
                'sri', 'f02s', 'phone', 'mobile'
            ])

            PHONE_CONNECTED = phone_found

            if earbuds_found:
                print("✅ Bluetooth earbuds detected!")
                return True
            elif phone_found:
                print("✅ Phone detected but no earbuds")
                return False
            else:
                print("❌ No audio devices found")
                return False

        return False

    except Exception as e:
        print(f"Bluetooth scan error: {e}")
        return False


def test_microphone():
    """Quick microphone test"""
    if not VOICE_AVAILABLE:
        return False

    try:
        global recognizer, microphone
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()

        print("🎤 Testing microphone... Say 'hello' in 3 seconds")

        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=2)

        text = recognizer.recognize_google(audio, show_all=False)
        print(f"✅ Microphone working! Heard: {text}")
        return True

    except Exception as e:
        print(f"❌ Microphone test failed: {e}")
        return False


def initialize_voice_mode():
    """Initialize voice mode with better detection"""
    global VOICE_MODE

    if not VOICE_AVAILABLE:
        print("📦 Installing voice libraries:")
        print("   pip install SpeechRecognition pyaudio")
        return False

    print("🔍 Scanning for Bluetooth devices...")

    if check_bluetooth_earbuds():
        speak("Bluetooth earbuds found! Testing microphone.")

        if test_microphone():
            VOICE_MODE = True
            speak("Voice commands activated! You can now speak to me.")
            print("🎤 VOICE MODE: ENABLED")
            return True
        else:
            speak("Microphone not working properly. Using text mode.")
    else:
        print("❌ No Bluetooth earbuds found")
        if PHONE_CONNECTED:
            print("📱 Phone connected - calling features available")

    VOICE_MODE = False
    return False


def listen_for_voice_command():
    """Listen for voice with better error handling"""
    global recognizer, microphone

    if not VOICE_MODE or not recognizer or not microphone:
        return None

    try:
        print("🎤 Listening... (speak now)")

        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)

        print("🔄 Processing speech...")
        text = recognizer.recognize_google(audio)
        print(f"✅ You said: {text}")
        return text

    except sr.WaitTimeoutError:
        print("⏱️ No speech detected")
        return None
    except sr.UnknownValueError:
        print("❓ Could not understand")
        return None
    except Exception as e:
        print(f"🎤 Voice error: {e}")
        return None


# ---------- PHONE INTEGRATION ----------
def make_phone_call(contact_name):
    """Make calls through connected phone or WhatsApp"""
    contact_name = contact_name.lower().strip()

    if contact_name not in CONTACTS:
        return f"Contact '{contact_name}' not found. Available: " + ", ".join(CONTACTS.keys())

    phone = CONTACTS[contact_name]

    if PHONE_CONNECTED:
        # Try to make call through connected phone
        try:
            # Windows Phone Link integration
            subprocess.run(['start', f'tel:{phone}'], shell=True)
            return f"Calling {contact_name.title()} through connected phone..."
        except Exception:
            pass

    # Fallback to WhatsApp call
    try:
        whatsapp_call_url = f"https://wa.me/{phone}"
        webbrowser.open(whatsapp_call_url)
        return f"Opening WhatsApp call to {contact_name.title()}"
    except Exception:
        return f"Could not initiate call to {contact_name}"


def send_sms(contact_name, message):
    """Send SMS through phone or WhatsApp"""
    contact_name = contact_name.lower().strip()

    if contact_name not in CONTACTS:
        return f"Contact not found: {contact_name}"

    phone = CONTACTS[contact_name]

    if PHONE_CONNECTED:
        # Try SMS through Phone Link
        try:
            sms_url = f"sms:{phone}?body={quote(message)}"
            subprocess.run(['start', sms_url], shell=True)
            return f"SMS sent to {contact_name.title()}"
        except Exception:
            pass

    # Fallback to WhatsApp
    whatsapp_url = f"https://wa.me/{phone}?text={quote(message)}"
    webbrowser.open(whatsapp_url)
    return f"WhatsApp message opened for {contact_name.title()}"


# ---------- SYSTEM FUNCTIONS ----------
def is_ollama_running():
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return response.status_code == 200
    except Exception:
        return False


def tell_time():
    return datetime.now().strftime("It is %I:%M %p")


def tell_date():
    return datetime.now().strftime("Today is %A, %B %d, %Y")


def battery_status():
    try:
        b = psutil.sensors_battery()
        if b is None:
            return "Battery info not available."
        status = "charging" if b.power_plugged else "on battery"
        return f"Battery at {int(b.percent)}% and {status}."
    except Exception:
        return "Cannot read battery status."


def open_application(app_name):
    """Open applications optimized for your system"""
    app_name = app_name.lower().strip()

    try:
        if "whatsapp" in app_name:
            # Try Microsoft Store version first (common on Windows 11)
            try:
                subprocess.Popen(['start', 'ms-windows-store://pdp/?productid=9NKSQGP7F2NH'], shell=True)
                return "Opening WhatsApp from Microsoft Store."
            except Exception:
                pass

            # Try desktop paths
            paths = [
                r"C:\Users\{}\AppData\Local\WhatsApp\WhatsApp.exe".format(os.getlogin()),
                r"C:\Program Files\WhatsApp\WhatsApp.exe"
            ]

            for path in paths:
                if os.path.exists(path):
                    subprocess.Popen([path])
                    return "Opening WhatsApp desktop."

            webbrowser.open("https://web.whatsapp.com")
            return "Opening WhatsApp web."

        elif "notepad" in app_name:
            subprocess.Popen(["notepad.exe"])
            return "Opening Notepad."

        elif "calculator" in app_name or "calc" in app_name:
            subprocess.Popen(["calc.exe"])
            return "Opening Calculator."

        elif "chrome" in app_name:
            subprocess.Popen(["chrome"], shell=True)
            return "Opening Chrome."

        elif "edge" in app_name:
            subprocess.Popen(["msedge.exe"])
            return "Opening Edge."

        elif "settings" in app_name:
            subprocess.Popen(["ms-settings:"], shell=True)
            return "Opening Windows Settings."

        else:
            return f"Don't know how to open '{app_name}'. Try: WhatsApp, Notepad, Calculator, Chrome, Edge, Settings."

    except Exception as e:
        return f"Could not open {app_name}: {str(e)[:50]}"


def search_knowledge_base(query):
    """Search local knowledge"""
    query_lower = query.lower()
    for key, value in KNOWLEDGE_BASE.items():
        if key in query_lower:
            return value
    return None


def enhanced_local_intent(text):
    """Enhanced command processing with phone features"""
    global VOICE_MODE  # FIXED: Move global declaration to the beginning

    text = text.lower().strip()
    if not text:
        return None

    response = None

    # Creator questions
    if any(phrase in text for phrase in ["who created", "who made", "your creator"]):
        response = "I was created by Balaji! my buddy!"

    # Greetings
    elif any(word in text for word in ["hello", "hi", "hey"]):
        response = "Hello! How can I help you?"

    # Phone status
    elif "phone status" in text or "phone connected" in text:
        phone_status = "connected" if PHONE_CONNECTED else "not connected"
        voice_status = "enabled" if VOICE_MODE else "disabled"
        response = f"Phone is {phone_status}. Voice mode is {voice_status}."

    # Voice mode control
    elif "voice mode off" in text:
        VOICE_MODE = False
        response = "Voice mode disabled."
    elif "voice mode on" in text:
        if initialize_voice_mode():
            response = "Voice mode activated!"
        else:
            response = "Voice mode failed. Check Bluetooth earbuds or install: pip install SpeechRecognition pyaudio"

    # Phone calls
    elif "call " in text:
        contact = text.replace("call ", "").strip()
        response = make_phone_call(contact)

    # SMS
    elif "sms to" in text or "text to" in text:
        if " to " in text:
            parts = text.split(" to ")
            if len(parts) >= 2:
                contact = parts[1].strip()
                message = "Hello from Luna assistant!"
                response = send_sms(contact, message)
        else:
            response = "Please specify who to text."

    # System commands
    elif any(k in text for k in ("exit", "quit", "goodbye")):
        return "EXIT_NOW"
    elif any(k in text for k in ("time", "clock")):
        response = tell_time()
    elif any(k in text for k in ("date", "today")):
        response = tell_date()
    elif any(k in text for k in ("battery", "power")):
        response = battery_status()

    # Open apps
    elif text.startswith("open "):
        target = text[5:].strip()
        if target in ["youtube", "google"]:
            webbrowser.open(f"https://{target}.com")
            response = f"Opening {target.title()}."
        else:
            response = open_application(target)

    # Knowledge base search
    else:
        kb_response = search_knowledge_base(text)
        if kb_response:
            response = kb_response

    return response


# ---------- MAIN PROCESSING ----------
def process_text_input(text):
    """Process with fixed memory checking"""
    if not text.strip():
        return "Please say or type something."

    # Gentle resource check (not blocking)
    check_system_resources()

    # Local commands first
    local_response = enhanced_local_intent(text)
    if local_response == "EXIT_NOW":
        return "EXIT_NOW"
    elif local_response:
        return local_response

    # Knowledge base
    kb_response = search_knowledge_base(text)
    if kb_response:
        return kb_response

    # Ollama for longer queries
    if is_ollama_running() and len(text) < 200:
        try:
            payload = {
                "model": MODEL_NAME,
                "prompt": text,
                "system": "You are Luna. Keep replies under 100 words. Be helpful and conversational.",
                "stream": False
            }
            response = requests.post(OLLAMA_API_GENERATE, json=payload, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "").strip()[:300]
        except Exception:
            pass

    # Web search fallback
    try:
        search_url = f"https://www.google.com/search?q={quote(text[:100])}"
        webbrowser.open(search_url)
        return f"Opened web search for: {text[:50]}..."
    except Exception:
        return "Could not search the web."


# ---------- MAIN LOOP ----------
if __name__ == "__main__":
    print("=" * 55)
    print("  LUNA - DELL LATITUDE 3490 + PHONE INTEGRATION")
    print("=" * 55)
    print("🎧 Noise Buds VS201 detection")
    print("📱 Sri's F02s phone integration")
    print("🎤 Voice commands when earbuds connected")
    print("📞 Calls & SMS through phone or WhatsApp")
    print("🧠 Fixed memory management")
    print("=" * 55)

    # System status
    memory = psutil.virtual_memory()
    print(f"📊 Memory: {memory.percent}%")
    print(f"💾 Available: {memory.available // (1024 ** 3)}GB")

    # Initialize
    print("\n🚀 Initializing Luna...")
    initialize_voice_mode()

    if PHONE_CONNECTED:
        print("📱 Phone features: call [contact], sms to [contact]")

    print("=" * 55)

    # Startup
    startup_msg = "Hi! I'm Luna, ready to help with voice commands and phone features!"
    speak(startup_msg)

    # Main loop
    try:
        while True:
            print("\n" + "-" * 40)

            # Get input
            if VOICE_MODE:
                print("🎤 Voice or Text:")
                voice_input = listen_for_voice_command()
                user_input = voice_input if voice_input else input("You: ").strip()
            else:
                user_input = input("You: ").strip()

            if not user_input:
                continue

            # Process
            print(f"⚡ Processing: {user_input[:50]}...")
            response = process_text_input(user_input)

            if response == "EXIT_NOW":
                speak("Goodbye!")
                break

            speak(response)

            # Gentle cleanup
            if memory_check_counter == 0:  # Only when counter resets
                cleanup_resources()

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        speak("Goodbye!")
    except Exception as e:
        print(f"Error: {e}")
        speak("Something went wrong. Goodbye!")
    finally:
        cleanup_resources()
