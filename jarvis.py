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
MAX_MEMORY_USAGE = 92
REQUEST_TIMEOUT = 15
MEMORY_CHECK_INTERVAL = 10

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

# Context memory for better conversations
last_user_input = ""
last_response = ""
pending_action = ""

# TTS engine reference
tts_engine = None


# ---------- IMPROVED TTS WITH FEMALE VOICE ----------
def initialize_tts():
    """Initialize TTS with female voice"""
    global tts_engine
    try:
        tts_engine = pyttsx3.init()

        # Get available voices
        voices = tts_engine.getProperty('voices')

        # Try to find female voice
        female_voice = None
        for voice in voices:
            # Look for female indicators in voice name/id
            voice_name = voice.name.lower()
            voice_id = voice.id.lower()

            if any(keyword in voice_name or keyword in voice_id for keyword in
                   ['female', 'woman', 'zira', 'hazel', 'susan', 'aria', 'eva']):
                female_voice = voice.id
                break

        # Set female voice if found, otherwise use first available
        if female_voice:
            tts_engine.setProperty('voice', female_voice)
            print(f"✅ Female voice selected: {female_voice}")
        else:
            # Fallback: try index 1 (often female on Windows)
            if len(voices) > 1:
                tts_engine.setProperty('voice', voices[1].id)
                print(f"✅ Voice selected: {voices[1].name}")

        # Set speech properties
        tts_engine.setProperty('rate', 170)  # Slightly slower for clarity
        tts_engine.setProperty('volume', 0.9)

        return True

    except Exception as e:
        print(f"TTS initialization error: {e}")
        return False


def speak(text: str):
    """Enhanced TTS with female voice"""
    global tts_engine

    if not text.strip():
        return

    print("Luna:", text)

    try:
        if not tts_engine:
            initialize_tts()

        if tts_engine:
            tts_engine.say(text)
            tts_engine.runAndWait()

    except Exception as e:
        print(f"TTS error: {e}")
        # Reinitialize if failed
        try:
            initialize_tts()
        except Exception:
            pass


# ---------- IMPROVED VOICE RECOGNITION ----------
def improved_voice_recognition():
    """Enhanced voice recognition with better error handling"""
    global recognizer, microphone

    if not VOICE_MODE or not recognizer or not microphone:
        return None

    try:
        print("🎤 Listening... (speak clearly)")

        with microphone as source:
            # Better noise adjustment
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

            # Longer timeout, better phrase detection
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)

        print("🔄 Processing speech...")

        # Try Google first (most accurate)
        try:
            text = recognizer.recognize_google(audio, language='en-US')
            print(f"✅ You said: {text}")
            return text.lower().strip()

        except sr.UnknownValueError:
            # Try with different language settings
            try:
                text = recognizer.recognize_google(audio, language='en-IN')  # Indian English
                print(f"✅ You said: {text}")
                return text.lower().strip()
            except sr.UnknownValueError:
                print("❓ Could not understand speech clearly")
                return None

    except sr.WaitTimeoutError:
        print("⏱️ No speech detected (timeout)")
        return None
    except sr.RequestError as e:
        print(f"🌐 Speech service error: {e}")
        return None
    except Exception as e:
        print(f"🎤 Voice error: {e}")
        return None


# ---------- MEMORY MANAGEMENT ----------
def check_system_resources():
    """Fixed memory check - less aggressive"""
    global memory_check_counter

    memory_check_counter += 1
    if memory_check_counter < MEMORY_CHECK_INTERVAL:
        return True

    memory_check_counter = 0

    try:
        memory = psutil.virtual_memory()
        if memory.percent > MAX_MEMORY_USAGE:
            print(f"⚠️ Memory at {memory.percent}% - cleaning up...")
            gc.collect()
            time.sleep(1)
            return True
        return True
    except Exception:
        return True


def cleanup_resources():
    """Gentle cleanup"""
    try:
        gc.collect()
    except Exception:
        pass


# ---------- BLUETOOTH & PHONE DETECTION ----------
def check_bluetooth_earbuds():
    """Improved detection for Noise Buds VS201 and phone"""
    global PHONE_CONNECTED

    try:
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
    """Improved microphone test"""
    if not VOICE_AVAILABLE:
        return False

    try:
        global recognizer, microphone
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()

        print("🎤 Testing microphone... Say 'hello Luna' in 3 seconds")

        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=4, phrase_time_limit=3)

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
        print("📦 Install voice libraries: pip install SpeechRecognition pyaudio")
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


# ---------- PHONE INTEGRATION ----------
def make_phone_call(contact_name):
    """Make calls through connected phone or WhatsApp"""
    contact_name = contact_name.lower().strip()

    if contact_name not in CONTACTS:
        return f"Contact '{contact_name}' not found. Available: " + ", ".join(CONTACTS.keys())

    phone = CONTACTS[contact_name]

    if PHONE_CONNECTED:
        try:
            subprocess.run(['start', f'tel:{phone}'], shell=True)
            return f"Calling {contact_name.title()} through connected phone..."
        except Exception:
            pass

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
        try:
            sms_url = f"sms:{phone}?body={quote(message)}"
            subprocess.run(['start', sms_url], shell=True)
            return f"SMS sent to {contact_name.title()}"
        except Exception:
            pass

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

        status = "plugged in and charging" if b.power_plugged else "unplugged and on battery power"
        return f"Battery is at {int(b.percent)}% and {status}."
    except Exception:
        return "Cannot read battery status."


def open_application(app_name):
    """Open applications optimized for your system"""
    app_name = app_name.lower().strip()

    try:
        if "whatsapp" in app_name:
            try:
                subprocess.Popen(['start', 'ms-windows-store://pdp/?productid=9NKSQGP7F2NH'], shell=True)
                return "Opening WhatsApp from Microsoft Store."
            except Exception:
                pass

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


def open_weather_website():
    """Open weather website"""
    global pending_action
    try:
        webbrowser.open("https://weather.com")
        pending_action = ""
        return "Opening weather website for you!"
    except Exception:
        return "Could not open weather website."


def parse_multiple_questions(text):
    """Parse and answer multiple questions in one input"""
    text = text.lower().strip()

    # Split by common separators
    parts = []
    for separator in [" and ", ", ", " & ", " also ", " plus "]:
        if separator in text:
            parts = [part.strip() for part in text.split(separator)]
            break

    if not parts:
        parts = [text]

    return parts


def enhanced_local_intent(text):
    """IMPROVED command processing with better voice command detection"""
    global VOICE_MODE, last_user_input, last_response, pending_action

    text = text.lower().strip()
    if not text:
        return None

    # Handle multiple questions
    questions = parse_multiple_questions(text)
    responses = []

    for question in questions:
        question = question.strip()
        response = None

        # Context-aware responses
        if pending_action == "weather" and any(word in question for word in ["yes", "please", "sure", "ok", "okay"]):
            response = open_weather_website()

        # Creator questions
        elif any(phrase in question for phrase in ["who created", "who made", "your creator", "who are you"]):
            response = "I'm Luna, your personal assistant created by Balaji! I can help with calls, messages, apps, and more."

        # Greetings
        elif any(word in question for word in ["hello", "hi", "hey"]):
            response = "Hello! How can I help you?"

        # IMPROVED: Voice mode control with more variations
        elif any(phrase in question for phrase in [
            "voice mode off", "disable voice", "turn off voice", "stop voice",
            "voice off", "turn voice off", "disable voice mode", "exit voice mode",
            "off voice mode", "voice mode disable", "stop voice mode"
        ]):
            VOICE_MODE = False
            response = "Voice mode disabled. Switching to text mode."
        elif any(phrase in question for phrase in [
            "voice mode on", "enable voice", "turn on voice", "start voice",
            "voice on", "turn voice on", "enable voice mode", "start voice mode",
            "vioce mode on", "voice mode enable"  # Common typos
        ]):
            if initialize_voice_mode():
                response = "Voice mode activated!"
            else:
                response = "Voice mode failed. Check Bluetooth earbuds."

        # Phone status
        elif "phone status" in question or "phone connected" in question:
            phone_status = "connected" if PHONE_CONNECTED else "not connected"
            voice_status = "enabled" if VOICE_MODE else "disabled"
            response = f"Phone is {phone_status}. Voice mode is {voice_status}."

        # Phone calls
        elif "call " in question:
            contact = question.replace("call ", "").strip()
            response = make_phone_call(contact)

        # SMS
        elif "sms to" in question or "text to" in question:
            if " to " in question:
                parts = question.split(" to ")
                if len(parts) >= 2:
                    contact = parts[1].strip()
                    message = "Hello from Luna assistant!"
                    response = send_sms(contact, message)
            else:
                response = "Please specify who to text."

        # System commands
        elif any(k in question for k in ("exit", "quit", "goodbye", "bye")):
            return "EXIT_NOW"
        elif any(k in question for k in ("time", "clock")):
            response = tell_time()
        elif any(k in question for k in ("date", "today")):
            response = tell_date()
        elif any(k in question for k in ("battery", "power", "charge", "plug")):
            response = battery_status()

        # Weather
        elif any(k in question for k in ("weather",)):
            pending_action = "weather"
            response = "I cannot check live weather, but I can open a weather website for you. Should I open it?"

        # Open apps
        elif question.startswith("open "):
            target = question[5:].strip()
            if target in ["youtube", "google"]:
                webbrowser.open(f"https://{target}.com")
                response = f"Opening {target.title()}."
            else:
                response = open_application(target)
        elif question == "edge":
            try:
                subprocess.Popen(["msedge.exe"])
                response = "Opening Microsoft Edge."
            except Exception:
                webbrowser.open("https://www.google.com")
                response = "Opening web browser."

        # Knowledge base search
        else:
            kb_response = search_knowledge_base(question)
            if kb_response:
                response = kb_response

        if response:
            responses.append(response)

    # Combine all responses
    if responses:
        return " ".join(responses)

    return None


def process_text_input(text):
    """Process with context awareness"""
    global last_user_input, last_response

    if not text.strip():
        return "Please say or type something."

    last_user_input = text
    check_system_resources()

    # Local commands first
    local_response = enhanced_local_intent(text)
    if local_response == "EXIT_NOW":
        return "EXIT_NOW"
    elif local_response:
        last_response = local_response
        return local_response

    # Knowledge base
    kb_response = search_knowledge_base(text)
    if kb_response:
        last_response = kb_response
        return kb_response

    # Improved fallback
    fallback_response = "I didn't understand that. Try: time, date, battery, weather, voice mode off, open [app], call [contact], or sms to [contact]."
    last_response = fallback_response
    return fallback_response


# ---------- MAIN LOOP ----------
if __name__ == "__main__":
    print("=" * 55)
    print("  LUNA - DELL LATITUDE 3490 + PHONE INTEGRATION")
    print("=" * 55)
    print("🎧 Noise Buds VS201 detection")
    print("📱 Sri's F02s phone integration")
    print("🎤 Improved voice recognition")
    print("📞 Calls & SMS through phone or WhatsApp")
    print("🧠 Smart multiple question parsing + Context memory")
    print("👩 Female voice TTS")
    print("=" * 55)

    # System status
    memory = psutil.virtual_memory()
    print(f"📊 Memory: {memory.percent}%")
    print(f"💾 Available: {memory.available // (1024 ** 3)}GB")

    # Initialize TTS first
    print("🎵 Initializing female voice...")
    initialize_tts()

    # Initialize Luna
    print("🚀 Initializing Luna...")
    initialize_voice_mode()

    if PHONE_CONNECTED:
        print("📱 Phone features: call [contact], sms to [contact]")

    print("=" * 55)

    # Startup
    startup_msg = "Hi! I'm Luna, your personal assistant created by Balaji. Ready to help!"
    speak(startup_msg)

    # Main loop
    try:
        while True:
            print("\n" + "-" * 40)

            user_input = None

            # Get input - IMPROVED handling
            if VOICE_MODE:
                print("🎤 Voice or Text:")
                voice_input = improved_voice_recognition()

                if voice_input:
                    user_input = voice_input
                else:
                    # Fallback to text input if voice fails
                    print("Speak failed, type instead:")
                    user_input = input("You: ").strip()
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

            # Cleanup
            if memory_check_counter == 0:
                cleanup_resources()

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        speak("Goodbye!")
    except Exception as e:
        print(f"Error: {e}")
        speak("Something went wrong. Goodbye!")
    finally:
        cleanup_resources()
        if tts_engine:
            try:
                tts_engine.stop()
            except Exception:
                pass