import os
import sys
import json
import webbrowser
import subprocess
import time
import threading
from datetime import datetime, timedelta
import requests
import psutil
import pyttsx3
from urllib.parse import quote
import re
import gc
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import imaplib
import email
import queue

# Advanced imports (install with: pip install selenium pyautogui opencv-python pillow pytesseract)
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import pyautogui
    import cv2
    import numpy as np
    from PIL import Image

    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    print("⚠️ Install automation libraries: pip install selenium pyautogui opencv-python pillow")

# Voice recognition
try:
    import speech_recognition as sr
    import pyaudio

    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

# For web search parsing
try:
    from bs4 import BeautifulSoup

    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    print("⚠️ Install BeautifulSoup: pip install beautifulsoup4")


# ---------- ADVANCED CONFIGURATION ----------
class LunaConfig:
    # System
    MODEL_NAME = "llama2"
    OLLAMA_HOST = "http://127.0.0.1:11434"
    MAX_MEMORY_USAGE = 90
    REQUEST_TIMEOUT = 20

    # Wake Word Detection (Simple version)
    WAKE_WORDS = ["hey luna", "luna", "hey assistant"]
    WAKE_WORD_TIMEOUT = 5

    # Email Configuration (Update these with your Gmail credentials)
    GMAIL_USER = "ribalaji335@gmail.com"  # Your Gmail - fill in password
    GMAIL_PASSWORD = ""  # Gmail App Password (not regular password)
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    IMAP_SERVER = "imap.gmail.com"

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, "luna_memory.db")
    SCREENSHOTS_PATH = os.path.join(BASE_DIR, "screenshots")

    # Chrome Profile Path (for persistent WhatsApp/LinkedIn login)
    CHROME_PROFILE_PATH = r"C:\Users\{}\AppData\Local\Google\Chrome\User Data".format(os.getlogin())

    # Features
    ENABLE_SCREEN_CONTROL = True
    ENABLE_EMAIL_MANAGEMENT = True
    ENABLE_SOCIAL_MEDIA = True
    ENABLE_FILE_MANAGEMENT = True
    ENABLE_WAKE_WORD = True
    ENABLE_BLUETOOTH_CALL = True  # New feature flag


config = LunaConfig()

# Create directories
os.makedirs(config.SCREENSHOTS_PATH, exist_ok=True)


# ---------- ADVANCED MEMORY SYSTEM ----------
class LunaMemory:
    def __init__(self):
        self.conn = None
        self.init_database()

    def init_database(self):
        """Initialize SQLite database for persistent memory"""
        self.conn = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)
        cursor = self.conn.cursor()

        # Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_input TEXT,
                luna_response TEXT,
                context TEXT,
                task_completed BOOLEAN DEFAULT FALSE
            )
        ''')

        # Contacts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                email TEXT,
                phone TEXT,
                whatsapp TEXT,
                linkedin TEXT,
                relationship TEXT,
                notes TEXT
            )
        ''')

        # Tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                due_date DATETIME,
                completed_at DATETIME
            )
        ''')

        # Bluetooth devices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bluetooth_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                address TEXT UNIQUE,
                device_type TEXT,
                last_connected DATETIME
            )
        ''')

        self.conn.commit()
        self.populate_default_data()

    def populate_default_data(self):
        """Add default contacts"""
        cursor = self.conn.cursor()

        # Default contacts
        default_contacts = [
            ("raj", "+919876543210", "raj@example.com", "friend", "Raj Kumar"),
            ("mom", "+919876543211", "mom@example.com", "family", "Mother"),
            ("dad", "+919876543212", "dad@example.com", "family", "Father"),
            ("boss", "+919876543213", "boss@company.com", "work", "Manager"),
            ("balaji", "+919876543214", "balaji.creator@gmail.com", "creator", "Balaji (Creator)"),
            ("sri", "+919876543215", "sri@example.com", "friend", "Sri's F02s")  # Added Sri's contact
        ]

        for name, phone, email, relationship, notes in default_contacts:
            cursor.execute('''
                INSERT OR IGNORE INTO contacts (name, phone, email, relationship, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, phone, email, relationship, notes))

        # Add Sri's phone Bluetooth device
        cursor.execute('''
            INSERT OR IGNORE INTO bluetooth_devices (name, address, device_type)
            VALUES (?, ?, ?)
        ''', ("Sri's F02s", "", "phone"))

        self.conn.commit()

    def remember_conversation(self, user_input, luna_response, context=""):
        """Store conversation in memory"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO conversations (user_input, luna_response, context)
            VALUES (?, ?, ?)
        ''', (user_input, luna_response, context))
        self.conn.commit()

    def get_recent_conversations(self, limit=5):
        """Get recent conversations for context"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT user_input, luna_response, timestamp 
            FROM conversations 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

    def get_contact(self, name):
        """Get contact information"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM contacts WHERE name LIKE ?', (f'%{name.lower()}%',))
        return cursor.fetchone()

    def add_task(self, title, description, priority=1):
        """Add new task"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (title, description, priority)
            VALUES (?, ?, ?)
        ''', (title, description, priority))
        self.conn.commit()
        return cursor.lastrowid

    def get_pending_tasks(self):
        """Get all pending tasks"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM tasks WHERE status = "pending" ORDER BY priority DESC, created_at')
        return cursor.fetchall()

    def update_bluetooth_device(self, name, address, device_type="phone"):
        """Update Bluetooth device information"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO bluetooth_devices (name, address, device_type, last_connected)
            VALUES (?, ?, ?, datetime('now'))
        ''', (name, address, device_type))
        self.conn.commit()

    def get_bluetooth_device(self, name):
        """Get Bluetooth device by name"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM bluetooth_devices WHERE name LIKE ?', (f'%{name}%',))
        return cursor.fetchone()


# ---------- SIMPLE WAKE WORD DETECTION ----------
class SimpleWakeWordDetector:
    def __init__(self):
        self.is_listening = False
        self.wake_word_detected = False
        self.recognizer = None
        self.microphone = None

        if VOICE_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()

    def listen_for_wake_word(self):
        """Listen for wake word (simplified version)"""
        if not VOICE_AVAILABLE:
            return False

        try:
            print("🎤 Listening for 'Hey Luna'...")

            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=config.WAKE_WORD_TIMEOUT, phrase_time_limit=3)

            text = self.recognizer.recognize_google(audio, language='en-US').lower()
            print(f"Heard: {text}")

            # Check if wake word is detected
            for wake_word in config.WAKE_WORDS:
                if wake_word in text:
                    self.wake_word_detected = True
                    return True

            return False

        except sr.WaitTimeoutError:
            return False
        except sr.UnknownValueError:
            return False
        except Exception as e:
            print(f"Wake word error: {e}")
            return False


# ---------- EMAIL MANAGEMENT ----------
class EmailManager:
    def __init__(self):
        self.gmail_user = config.GMAIL_USER
        self.gmail_password = config.GMAIL_PASSWORD

    def send_email(self, to_email, subject, body, cc=None):
        """Send email via Gmail"""
        if not self.gmail_user or self.gmail_user == "your-email@gmail.com" or not self.gmail_password:
            return "⚠️ Gmail credentials not configured. Update GMAIL_USER and GMAIL_PASSWORD in config."

        try:
            msg = MIMEMultipart()
            msg['From'] = self.gmail_user
            msg['To'] = to_email
            msg['Subject'] = subject

            if cc:
                msg['Cc'] = cc

            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            server.starttls()
            server.login(self.gmail_user, self.gmail_password)

            recipients = [to_email]
            if cc:
                recipients.extend(cc.split(','))

            text = msg.as_string()
            server.sendmail(self.gmail_user, recipients, text)
            server.quit()

            return f"✅ Email sent successfully to {to_email}"

        except Exception as e:
            return f"❌ Email failed: {str(e)[:100]}"

    def check_new_emails(self, limit=5):
        """Check for new emails"""
        if not self.gmail_user or self.gmail_user == "your-email@gmail.com" or not self.gmail_password:
            return "Gmail credentials not configured."

        try:
            mail = imaplib.IMAP4_SSL(config.IMAP_SERVER)
            mail.login(self.gmail_user, self.gmail_password)
            mail.select('inbox')

            # Search for unread emails
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()

            if not email_ids:
                return "📧 No new emails."

            email_info = []
            for i in email_ids[-limit:]:  # Get latest emails
                status, msg_data = mail.fetch(i, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])

                subject = msg.get('Subject', 'No Subject')
                from_addr = msg.get('From', 'Unknown')

                email_info.append(f"From: {from_addr}\nSubject: {subject}\n")

            mail.close()
            mail.logout()

            return f"📧 {len(email_info)} new emails:\n" + "\n---\n".join(email_info)

        except Exception as e:
            return f"Email check error: {str(e)[:100]}"

    def compose_formal_email(self, context, email_type="general"):
        """Generate formal email based on context"""
        user_name = os.getlogin()

        templates = {
            "leave": f"""Subject: Leave Application Request

Dear Sir/Madam,

I hope this email finds you well. I am writing to formally request leave from work.

{context}

I have ensured that my current projects are up to date and have briefed my team members about any pending tasks. I will be reachable via email for any urgent matters.

I would be grateful if you could approve my leave request. Please let me know if you need any additional information.

Thank you for your understanding.

Best regards,
{user_name}""",

            "meeting": f"""Subject: Meeting Request

Dear Sir/Madam,

I hope you are doing well. I would like to schedule a meeting to discuss:

{context}

Please let me know your availability, and I will arrange the meeting accordingly.

Thank you for your time.

Best regards,
{user_name}""",

            "general": f"""Subject: {context}

Dear Sir/Madam,

I hope this email finds you well.

{context}

Thank you for your attention to this matter.

Best regards,
{user_name}"""
        }

        # Auto-detect email type
        context_lower = context.lower()
        if any(word in context_lower for word in ['leave', 'vacation', 'sick', 'holiday']):
            return templates['leave']
        elif any(word in context_lower for word in ['meeting', 'discuss', 'schedule']):
            return templates['meeting']
        else:
            return templates['general']


# ---------- WHATSAPP AUTOMATION ----------
class WhatsAppManager:
    def __init__(self):
        self.driver = None

    def initialize_browser(self, headless=False):
        """Initialize Chrome browser"""
        if not AUTOMATION_AVAILABLE:
            return False

        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"--user-data-dir={config.CHROME_PROFILE_PATH}")

            self.driver = webdriver.Chrome(options=chrome_options)
            return True
        except Exception as e:
            print(f"Browser error: {e}")
            return False

    def send_whatsapp_message(self, contact_name, message, confirm_before_send=True):
        """Send WhatsApp message"""
        if not self.initialize_browser():
            return "❌ Could not start browser. Install ChromeDriver and Chrome."

        try:
            print("🌐 Opening WhatsApp Web...")
            self.driver.get("https://web.whatsapp.com")

            print("⏳ Please scan QR code if not logged in...")
            time.sleep(15)  # Wait for login

            # Search for contact
            print(f"🔍 Searching for contact: {contact_name}")
            search_xpath = '//div[@contenteditable="true"][@data-tab="3"]'

            search_box = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, search_xpath))
            )
            search_box.clear()
            search_box.send_keys(contact_name)
            time.sleep(3)

            # Click on contact
            contact_xpath = f'//span[@title="{contact_name}"]'
            try:
                contact = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, contact_xpath))
                )
                contact.click()
            except:
                # Alternative: click first search result
                first_result = self.driver.find_element(By.XPATH, '//div[@data-testid="cell-frame-container"][1]')
                first_result.click()

            time.sleep(2)

            # Show message preview
            if confirm_before_send:
                print(f"\n📱 WhatsApp Message Preview:")
                print(f"To: {contact_name}")
                print(f"Message: {message}")
                print("─" * 50)

                confirmation = input("Send this message? (yes/y to confirm): ").lower().strip()
                if confirmation not in ['yes', 'y']:
                    self.driver.quit()
                    return "❌ Message cancelled by user."

            # Type and send message
            message_xpath = '//div[@contenteditable="true"][@data-tab="10"]'
            message_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, message_xpath))
            )

            message_box.send_keys(message)
            message_box.send_keys(Keys.ENTER)

            time.sleep(3)
            self.driver.quit()

            return f"✅ WhatsApp message sent to {contact_name}!"

        except Exception as e:
            if self.driver:
                self.driver.quit()
            return f"❌ WhatsApp error: {str(e)[:150]}"


# ---------- SCREEN CONTROLLER ----------
class ScreenController:
    def __init__(self):
        if AUTOMATION_AVAILABLE:
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.5

    def take_screenshot(self, filename=None):
        """Take screenshot"""
        if not AUTOMATION_AVAILABLE:
            return "Screen capture not available. Install: pip install pyautogui pillow"

        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"

            filepath = os.path.join(config.SCREENSHOTS_PATH, filename)
            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)

            return f"✅ Screenshot saved: {filepath}"

        except Exception as e:
            return f"❌ Screenshot failed: {str(e)[:100]}"

    def get_screen_text(self):
        """Extract text from current screen (basic implementation)"""
        if not AUTOMATION_AVAILABLE:
            return "OCR not available."

        try:
            # Take screenshot
            screenshot = pyautogui.screenshot()

            # Basic text extraction (you'd need pytesseract for real OCR)
            return "Screen text extraction would require pytesseract installation."

        except Exception as e:
            return f"Screen text error: {str(e)[:100]}"


# ---------- BLUETOOTH MANAGER ----------
class BluetoothManager:
    def __init__(self, memory):
        self.last_checked = None
        self.connected_devices = []
        self.memory = memory
        self.device_queue = queue.Queue()

    def check_bluetooth_connection(self):
        """Check for connected Bluetooth devices - platform specific implementation"""
        try:
            # Windows implementation
            if sys.platform == "win32":
                # Use PowerShell to get Bluetooth devices
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Get-PnpDevice -Class Bluetooth | Where-Object {$_.Status -eq 'OK'} | Select-Object FriendlyName, Status"],
                    capture_output=True, text=True, timeout=10
                )

                if result.returncode == 0:
                    devices = []
                    lines = result.stdout.split('\n')

                    for line in lines:
                        if line.strip() and not line.startswith('FriendlyName'):
                            # Extract device name (everything before the status)
                            if 'OK' in line:
                                device_name = line.split('OK')[0].strip()
                                devices.append(device_name)

                    # Check if new devices connected
                    new_devices = [d for d in devices if d not in self.connected_devices]

                    if new_devices:
                        self.connected_devices = devices
                        return new_devices

            # Linux implementation (simplified)
            elif sys.platform.startswith('linux'):
                try:
                    # Try using hcitool or bluetoothctl
                    result = subprocess.run(
                        ["bluetoothctl", "devices"],
                        capture_output=True, text=True, timeout=10
                    )

                    if result.returncode == 0:
                        devices = []
                        lines = result.stdout.split('\n')

                        for line in lines:
                            if line.strip():
                                parts = line.split(' ', 2)
                                if len(parts) >= 3:
                                    devices.append(parts[2])

                        new_devices = [d for d in devices if d not in self.connected_devices]

                        if new_devices:
                            self.connected_devices = devices
                            return new_devices
                except:
                    # Fallback to basic detection
                    pass

            return []

        except Exception as e:
            print(f"Bluetooth check error: {e}")
            return []

    def monitor_bluetooth_connections(self, callback):
        """Monitor Bluetooth connections in background thread"""

        def monitor():
            while True:
                try:
                    new_devices = self.check_bluetooth_connection()
                    if new_devices:
                        for device in new_devices:
                            # Put device in queue instead of calling callback directly
                            self.device_queue.put(device)
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    print(f"Bluetooth monitoring error: {e}")
                    time.sleep(60)  # Wait longer if error occurs

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def process_device_queue(self, callback):
        """Process device queue from main thread to avoid SQLite issues"""
        try:
            while not self.device_queue.empty():
                device = self.device_queue.get_nowait()
                callback(device)
        except queue.Empty:
            pass


# ---------- SEARCH MANAGER ----------
class SearchManager:
    def __init__(self):
        pass

    def google_search(self, query, num_results=3):
        """Perform Google search and return results (without opening browser)"""
        try:
            # Use a simple requests approach to get search results
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            search_url = f"https://www.google.com/search?q={quote(query)}"
            response = requests.get(search_url, headers=headers, timeout=10)

            if response.status_code == 200:
                # Simple text parsing to extract results (fallback if BeautifulSoup not available)
                if BEAUTIFULSOUP_AVAILABLE:
                    return self._parse_with_beautifulsoup(response.text, query, num_results)
                else:
                    return self._parse_without_beautifulsoup(response.text, query)

            else:
                return f"Search failed with status code: {response.status_code}"

        except Exception as e:
            return f"Search error: {str(e)[:100]}"

    def _parse_with_beautifulsoup(self, html, query, num_results):
        """Parse search results using BeautifulSoup"""
        soup = BeautifulSoup(html, 'html.parser')

        results = []
        # Find search result containers
        for g in soup.find_all('div', class_='tF2Cxc')[:num_results]:
            title = g.find('h3')
            link = g.find('a')
            desc = g.find('div', class_='VwiC3b')

            if title and link:
                result = {
                    'title': title.get_text(),
                    'link': link.get('href'),
                    'description': desc.get_text() if desc else "No description available"
                }
                results.append(result)

        if results:
            summary = f"Here's what I found for '{query}':\n\n"
            for i, result in enumerate(results, 1):
                summary += f"{i}. {result['title']}\n"
                summary += f"   {result['description'][:100]}...\n\n"

            return summary
        else:
            return f"I couldn't find specific results for '{query}'. Try rephrasing your search."

    def _parse_without_beautifulsoup(self, html, query):
        """Simple text-based parsing fallback"""
        # Look for result-like patterns in the HTML
        if f"q={quote(query)}" in html:
            return f"I found results for '{query}' on Google. For detailed results, please install BeautifulSoup: pip install beautifulsoup4"
        else:
            return f"I searched for '{query}' but couldn't parse the results. Install BeautifulSoup for better search results: pip install beautifulsoup4"


# ---------- MAIN LUNA BRAIN ----------
class AdvancedLuna:
    def __init__(self):
        print("🧠 Initializing Advanced Luna...")

        # Initialize components
        self.memory = LunaMemory()
        self.email_manager = EmailManager()
        self.whatsapp_manager = WhatsAppManager()
        self.screen_controller = ScreenController()
        self.wake_detector = SimpleWakeWordDetector()
        self.bluetooth_manager = BluetoothManager(self.memory)
        self.search_manager = SearchManager()

        # TTS Engine
        self.tts_engine = None
        self.initialize_tts()

        # State
        self.voice_mode = False
        self.wake_word_mode = config.ENABLE_WAKE_WORD and VOICE_AVAILABLE
        self.current_task = None
        self.tts_lock = threading.Lock()

        # Start Bluetooth monitoring
        if config.ENABLE_BLUETOOTH_CALL:
            self.bluetooth_manager.monitor_bluetooth_connections(self.handle_bluetooth_connection)

        print("✅ Advanced Luna initialized!")

    def initialize_tts(self):
        """Initialize Text-to-Speech"""
        try:
            self.tts_engine = pyttsx3.init()
            voices = self.tts_engine.getProperty('voices')

            # Try to find female voice
            for voice in voices:
                if any(keyword in voice.name.lower() for keyword in ['zira', 'female', 'hazel', 'aria']):
                    self.tts_engine.setProperty('voice', voice.id)
                    print(f"👩 Female voice selected: {voice.name}")
                    break

            self.tts_engine.setProperty('rate', 165)
            self.tts_engine.setProperty('volume', 0.9)
            return True

        except Exception as e:
            print(f"TTS error: {e}")
            return False

    def speak(self, text):
        """Speak with enhanced personality - ALWAYS speaks even in text mode"""
        print(f"Luna: {text}")

        # Always try to speak regardless of mode
        if self.tts_engine:
            try:
                # Use a lock to prevent multiple threads from accessing TTS simultaneously
                with self.tts_lock:
                    # Stop any current speech to prevent "run loop already started" error
                    self.tts_engine.stop()
                    self.tts_engine.say(text)
                    self.tts_engine.runAndWait()
            except Exception as e:
                print(f"TTS error: {e}")

    def handle_bluetooth_connection(self, device_name):
        """Handle new Bluetooth device connection"""
        print(f"📱 Bluetooth device connected: {device_name}")

        # Check if this is Sri's phone
        if "f02s" in device_name.lower() or "sri" in device_name.lower():
            self.speak("Sri's phone is connected via Bluetooth. Would you like to call someone?")

            # Update device in database - this is called from main thread now
            self.memory.update_bluetooth_device("Sri's F02s", device_name)

        # You can add more device-specific actions here

    def process_complex_command(self, user_input):
        """Process complex multi-step commands"""
        user_input = user_input.lower().strip()

        # Remember this conversation
        response = ""

        # Google search (background search)
        if user_input.startswith("search for ") or user_input.startswith("google "):
            query = user_input.replace("search for", "").replace("google", "").strip()
            if query:
                response = self.search_manager.google_search(query)
            else:
                response = "What would you like me to search for?"

        # Complex WhatsApp task
        elif "whatsapp" in user_input and ("write" in user_input or "send" in user_input):
            response = self.handle_whatsapp_task(user_input)

        # Email tasks
        elif "email" in user_input and ("write" in user_input or "compose" in user_input or "send" in user_input):
            response = self.handle_email_task(user_input)

        # Email checking
        elif "check email" in user_input or "new email" in user_input:
            response = self.email_manager.check_new_emails()

        # Screenshot
        elif "screenshot" in user_input or "capture screen" in user_input:
            response = self.screen_controller.take_screenshot()

        # Task management
        elif "add task" in user_input or "remind me" in user_input:
            response = self.handle_task_creation(user_input)

        # Show tasks
        elif "show task" in user_input or "my task" in user_input:
            response = self.show_pending_tasks()

        # System control
        elif "open" in user_input:
            response = self.handle_app_opening(user_input)

        # Time and date
        elif "time" in user_input:
            response = f"Current time: {datetime.now().strftime('%I:%M %p')}"
        elif "date" in user_input:
            response = f"Today is {datetime.now().strftime('%A, %B %d, %Y')}"

        # Battery status
        elif "battery" in user_input:
            response = self.get_battery_status()

        # Voice mode control
        elif "voice mode on" in user_input:
            self.voice_mode = True
            response = "Voice mode activated!"
        elif "voice mode off" in user_input:
            self.voice_mode = False
            response = "Voice mode deactivated."

        # Wake word control
        elif "wake word on" in user_input:
            self.wake_word_mode = True
            response = "Wake word 'Hey Luna' activated!"
        elif "wake word off" in user_input:
            self.wake_word_mode = False
            response = "Wake word deactivated."

        # Bluetooth call
        elif "call" in user_input and "bluetooth" not in user_input:
            response = self.handle_call_command(user_input)

        # Help
        elif "help" in user_input or "what can you do" in user_input:
            response = self.show_capabilities()

        # Exit
        elif any(word in user_input for word in ["exit", "quit", "goodbye", "bye"]):
            response = "EXIT_COMMAND"

        # Fallback
        else:
            response = self.handle_general_query(user_input)

        # Remember conversation
        if response != "EXIT_COMMAND":
            self.memory.remember_conversation(user_input, response)

        return response

    def handle_call_command(self, user_input):
        """Handle call commands via Bluetooth"""
        try:
            # Extract contact name
            contact_name = user_input.replace("call", "").strip()

            if not contact_name:
                return "Who would you like to call?"

            # Get contact info
            contact = self.memory.get_contact(contact_name)
            if not contact:
                return f"I don't have contact information for {contact_name}."

            phone_number = contact[2]  # Phone field

            # Try to initiate call via Bluetooth
            if sys.platform == "win32":
                # Windows - use built-in dialer
                subprocess.Popen(f"start dialer:{phone_number}", shell=True)
                return f"Dialing {contact_name} at {phone_number}"
            else:
                # Other platforms - try to use default handler
                webbrowser.open(f"tel:{phone_number}")
                return f"Attempting to call {contact_name}"

        except Exception as e:
            return f"Call failed: {str(e)[:100]}"

    def handle_whatsapp_task(self, user_input):
        """Handle WhatsApp messaging tasks"""
        try:
            # Extract contact name
            contact_name = None
            if " to " in user_input:
                parts = user_input.split(" to ")
                if len(parts) > 1:
                    contact_part = parts[1].split(" and ")[0].strip()
                    contact = self.memory.get_contact(contact_part)
                    if contact:
                        contact_name = contact[1]  # name field
                    else:
                        contact_name = contact_part.title()

            if not contact_name:
                return "❌ Please specify who to send the message to. Try: 'send WhatsApp message to [contact name]'"

            # Generate message content based on context
            message_content = ""
            if "leave" in user_input:
                message_content = "Hello, I would like to request leave from work for personal reasons. Could you please approve my leave application? Thank you."
            elif "meeting" in user_input:
                message_content = "Hello, I would like to schedule a meeting to discuss some important work matters. Please let me know your availability."
            elif "formal" in user_input:
                message_content = "Hello, I hope you are doing well. I wanted to reach out regarding some official matters. Please let me know when we can connect. Thank you."
            else:
                message_content = "Hello! Hope you're doing well. Luna assistant here - just wanted to touch base with you."

            # Check if confirmation is needed
            confirm_before_send = "confirm" in user_input or "ask before" in user_input

            # Send message
            result = self.whatsapp_manager.send_whatsapp_message(contact_name, message_content, confirm_before_send)
            return result

        except Exception as e:
            return f"❌ WhatsApp task failed: {str(e)[:100]}"

    def handle_email_task(self, user_input):
        """Handle email composition and sending"""
        try:
            # Extract recipient
            recipient_email = None
            recipient_name = None

            if " to " in user_input:
                parts = user_input.split(" to ")
                if len(parts) > 1:
                    recipient_part = parts[1].split(" ")[0].strip()
                    contact = self.memory.get_contact(recipient_part)
                    if contact:
                        recipient_email = contact[3]  # email field
                        recipient_name = contact[1]  # name field

            if not recipient_email:
                return "❌ Please specify recipient email. Try: 'compose email to [contact]' or update contact info."

            # Generate email content
            if "leave" in user_input:
                context = "I am writing to request leave from work due to personal commitments. I would appreciate your approval for this leave request."
                email_content = self.email_manager.compose_formal_email(context, "leave")
            elif "meeting" in user_input:
                context = "I would like to schedule a meeting to discuss project updates and coordinate our next steps."
                email_content = self.email_manager.compose_formal_email(context, "meeting")
            else:
                context = "I hope this email finds you well. I wanted to reach out regarding some important matters."
                email_content = self.email_manager.compose_formal_email(context, "general")

            # Parse email content
            lines = email_content.strip().split('\n')
            subject = lines[0].replace('Subject: ', '') if lines[0].startswith(
                'Subject: ') else "Message from Luna Assistant"
            body = '\n'.join(lines[2:]) if len(lines) > 2 else email_content

            # Show preview
            print(f"\n📧 Email Preview:")
            print(f"To: {recipient_email}")
            print(f"Subject: {subject}")
            print(f"Body Preview: {body[:200]}...")
            print("─" * 50)

            # Confirm before sending
            if "confirm" in user_input or "ask before" in user_input:
                confirm = input("Send this email? (yes/y to send): ").lower().strip()
                if confirm not in ['yes', 'y']:
                    return "❌ Email cancelled by user."

            # Send email
            result = self.email_manager.send_email(recipient_email, subject, body)
            return result

        except Exception as e:
            return f"❌ Email task failed: {str(e)[:100]}"

    def handle_task_creation(self, user_input):
        """Create and manage tasks"""
        try:
            # Extract task details
            task_text = user_input
            if " to " in user_input:
                task_text = user_input.split(" to ")[1]
            elif "remind me " in user_input:
                task_text = user_input.replace("remind me ", "")
            elif "add task" in user_input:
                task_text = user_input.replace("add task ", "")

            # Determine priority
            priority = 1
            if any(word in user_input for word in ["urgent", "important", "asap"]):
                priority = 3
            elif any(word in user_input for word in ["soon", "quickly"]):
                priority = 2

            task_id = self.memory.add_task(task_text, task_text, priority)
            return f"✅ Task added (ID: {task_id}): {task_text}"

        except Exception as e:
            return f"❌ Task creation failed: {str(e)[:100]}"

    def show_pending_tasks(self):
        """Show all pending tasks"""
        try:
            tasks = self.memory.get_pending_tasks()
            if not tasks:
                return "📋 No pending tasks."

            task_list = "📋 Your Pending Tasks:\n"
            for i, task in enumerate(tasks[:10], 1):  # Show top 10
                task_list += f"{i}. {task[1]} (Priority: {task[3]})\n"

            return task_list

        except Exception as e:
            return f"❌ Could not fetch tasks: {str(e)[:100]}"

    def handle_app_opening(self, user_input):
        """Open applications"""
        app_name = user_input.replace("open ", "").strip().lower()

        try:
            if "whatsapp" in app_name:
                webbrowser.open("https://web.whatsapp.com")
                return "🌐 Opening WhatsApp Web"
            elif "gmail" in app_name or "email" in app_name:
                webbrowser.open("https://gmail.com")
                return "📧 Opening Gmail"
            elif "linkedin" in app_name:
                webbrowser.open("https://linkedin.com")
                return "💼 Opening LinkedIn"
            elif "notepad" in app_name:
                subprocess.Popen(["notepad.exe"])
                return "📝 Opening Notepad"
            elif "calculator" in app_name:
                subprocess.Popen(["calc.exe"])
                return "🧮 Opening Calculator"
            elif "chrome" in app_name:
                subprocess.Popen(["chrome"])
                return "🌐 Opening Chrome"
            elif "settings" in app_name:
                subprocess.Popen(["ms-settings:"])
                return "⚙️ Opening Settings"
            else:
                return f"❓ Don't know how to open '{app_name}'. Try: WhatsApp, Gmail, LinkedIn, Notepad, Calculator."

        except Exception as e:
            return f"❌ Could not open {app_name}: {str(e)[:50]}"

    def get_battery_status(self):
        """Get battery information"""
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return "🔋 Battery information not available."

            status = "charging" if battery.power_plugged else "discharging"
            return f"🔋 Battery: {int(battery.percent)}% ({status})"

        except Exception:
            return "🔋 Could not read battery status."

    def show_capabilities(self):
        """Show what Luna can do"""
        return """🤖 Luna's Advanced Capabilities:

📱 WhatsApp: "send WhatsApp message to [contact] about [topic]"
📧 Email: "compose email to [contact] about [subject]"
📋 Tasks: "add task [description]" or "show my tasks"
📸 Screenshot: "take screenshot"
🚀 Apps: "open [WhatsApp/Gmail/Chrome/Notepad/etc]"
⏰ Info: "what time is it" or "what's the date"
🔋 System: "battery status"
🎤 Voice: "voice mode on/off"
👂 Wake Word: "wake word on/off" (Hey Luna)
📞 Phone: "call [contact]" (opens dialer)
🔍 Search: "search for [query]" or "google [query]"
🔍 Email Check: "check my emails"
❓ Help: "what can you do"
👋 Exit: "goodbye" or "exit"

💡 Example Commands:
• "Hey Luna, send WhatsApp message to boss about leave and confirm before sending"
• "compose formal email to manager about meeting request"
• "take screenshot and open Gmail"
• "add urgent task to complete project report"
• "search for latest AI news"
"""

    def handle_general_query(self, user_input):
        """Handle general queries and conversation"""
        user_input = user_input.lower()

        # Personal questions about Luna
        if any(phrase in user_input for phrase in ["who are you", "what are you", "introduce yourself"]):
            return "👋 I'm Luna, your advanced personal assistant created by Balaji! I can control your laptop, manage emails, send messages, and help with daily tasks - just like Jarvis from Iron Man!"

        # Greetings
        elif any(word in user_input for word in ["hello", "hi", "hey"]):
            return "Hello! I'm Luna, ready to help you with anything. What would you like me to do?"

        # How are you
        elif "how are you" in user_input:
            return "I'm doing great! All systems running smoothly and ready to assist you. How can I help today?"

        # Weather (opens weather site)
        elif "weather" in user_input:
            webbrowser.open("https://weather.com")
            return "🌤️ Opening weather website for you!"

        # News
        elif "news" in user_input:
            webbrowser.open("https://news.google.com")
            return "📰 Opening Google News for you!"

        # Search
        elif "search for" in user_input or "google" in user_input:
            query = user_input.replace("search for", "").replace("google", "").strip()
            if query:
                return self.search_manager.google_search(query)
            else:
                return "What would you like me to search for?"

        # Memory/context
        elif "remember" in user_input:
            return "I'll remember our conversations in my memory database. What should I remember?"

        # Compliments
        elif any(phrase in user_input for phrase in ["good job", "well done", "thank you", "thanks"]):
            return "You're welcome! I'm here to make your life easier. What else can I do for you?"

        # Default fallback
        else:
            return f"I'm not sure about '{user_input}'. Try asking me to send messages, compose emails, take screenshots, open apps, or say 'help' to see what I can do!"

    def listen_for_input(self):
        """Listen for voice input"""
        if not VOICE_AVAILABLE or not self.voice_mode:
            return None

        try:
            recognizer = sr.Recognizer()
            microphone = sr.Microphone()

            with microphone as source:
                print("🎤 Listening...")
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)

            print("🔄 Processing speech...")
            text = recognizer.recognize_google(audio, language='en-US')
            print(f"✅ You said: {text}")
            return text.lower().strip()

        except sr.WaitTimeoutError:
            print("⏱️ No speech detected")
            return None
        except sr.UnknownValueError:
            print("❓ Could not understand speech")
            return None
        except Exception as e:
            print(f"🎤 Voice error: {e}")
            return None

    def run_wake_word_mode(self):
        """Run in wake word mode"""
        print("👂 Wake word mode active! Say 'Hey Luna' to activate...")

        while self.wake_word_mode:
            if self.wake_detector.listen_for_wake_word():
                self.speak("Yes, I'm listening!")

                # Get the actual command
                user_input = self.listen_for_input()
                if user_input:
                    response = self.process_complex_command(user_input)
                    if response == "EXIT_COMMAND":
                        break
                    self.speak(response)
                else:
                    self.speak("I didn't catch that. Please try again.")

                print("👂 Say 'Hey Luna' to activate again...")
            time.sleep(0.5)  # Small delay to prevent excessive CPU usage

    def run_main_loop(self):
        """Main interaction loop"""
        print("\n🚀 Luna is ready! Choose your interaction mode:")
        print("1. Type 'voice' for voice commands")
        print("2. Type 'wake' for wake word mode")
        print("3. Type commands directly")
        print("4. Type 'exit' to quit")

        while True:
            try:
                print("\n" + "─" * 50)

                # Process Bluetooth device queue from main thread
                self.bluetooth_manager.process_device_queue(self.handle_bluetooth_connection)

                # Check for wake word mode
                if self.wake_word_mode and VOICE_AVAILABLE:
                    user_input = input("Command (or 'wake' for wake word mode): ").strip()

                    if user_input.lower() == 'wake':
                        self.run_wake_word_mode()
                        continue
                else:
                    user_input = input("You: ").strip()

                if not user_input:
                    continue

                # Handle mode switches
                if user_input.lower() == 'voice':
                    if VOICE_AVAILABLE:
                        self.voice_mode = True
                        self.speak("Voice mode activated! Speak your command.")
                        user_input = self.listen_for_input()
                        if not user_input:
                            continue
                    else:
                        print("❌ Voice recognition not available. Install: pip install SpeechRecognition pyaudio")
                        continue

                # Process command
                print(f"⚡ Processing: {user_input[:50]}...")
                response = self.process_complex_command(user_input)

                if response == "EXIT_COMMAND":
                    self.speak("Goodbye! Luna signing off.")
                    break

                # Respond
                self.speak(response)

            except KeyboardInterrupt:
                print("\n👋 Interrupted by user")
                self.speak("Goodbye!")
                break
            except Exception as e:
                error_msg = f"❌ Error occurred: {str(e)[:100]}"
                print(error_msg)
                self.speak("Sorry, something went wrong.")


# ---------- PERFORMANCE OPTIMIZATION ----------
def optimize_system():
    """Optimize system for low-end hardware"""
    print("🔄 Optimizing system for low-end hardware...")

    # Reduce process priority to prevent system slowdown
    try:
        import win32api
        import win32process
        import win32con

        handle = win32api.GetCurrentProcess()
        win32process.SetPriorityClass(handle, win32process.BELOW_NORMAL_PRIORITY_CLASS)
        print("✅ Process priority optimized")
    except:
        pass

    # Clean up memory
    gc.collect()
    print("✅ Memory cleaned up")

    # Suggest closing heavy applications
    heavy_apps = ["chrome", "firefox", "photoshop", "illustrator", "aftereffects"]
    running_processes = [p.name().lower() for p in psutil.process_iter()]

    for app in heavy_apps:
        if any(app in proc for proc in running_processes):
            print(f"⚠️ Consider closing {app} to improve Luna's performance")


# ---------- MAIN EXECUTION ----------
def main():
    """Main function to run Advanced Luna"""
    print("=" * 60)
    print("  🤖 ADVANCED LUNA - JARVIS-LEVEL ASSISTANT")
    print("=" * 60)
    print("🚀 Created by Balaji - Your Personal AI Assistant")
    print("🎯 Capabilities: Email, WhatsApp, Tasks, Screenshots & More!")
    print("🎤 Voice Commands + Wake Word Detection")
    print("🧠 Persistent Memory & Smart Conversations")
    print("⚡ System Control & Automation")
    print("=" * 60)

    # Optimize for low-end system
    optimize_system()

    # System info
    memory = psutil.virtual_memory()
    print(f"📊 System Memory: {memory.percent}% used")
    print(f"💾 Available Memory: {memory.available // (1024 ** 3)}GB")

    # Check dependencies
    missing_deps = []
    if not VOICE_AVAILABLE:
        missing_deps.append("Voice: pip install SpeechRecognition pyaudio")
    if not AUTOMATION_AVAILABLE:
        missing_deps.append("Automation: pip install selenium pyautogui opencv-python pillow")
    if not BEAUTIFULSOUP_AVAILABLE:
        missing_deps.append("Web parsing: pip install beautifulsoup4")

    if missing_deps:
        print("\n⚠️ Optional Dependencies Missing:")
        for dep in missing_deps:
            print(f"   {dep}")
        print("\nLuna will work with reduced functionality.\n")

    # Initialize Luna
    try:
        luna = AdvancedLuna()

        # Startup message
        startup_msg = f"Hello! I'm Advanced Luna, your Jarvis-level assistant created by Balaji. I'm ready to control your laptop and help with everything - emails, messages, tasks, and more!"
        luna.speak(startup_msg)

        # Run main loop
        luna.run_main_loop()

    except Exception as e:
        print(f"❌ Luna initialization failed: {e}")
        print("Check your Python environment and dependencies.")

    finally:
        print("🔄 Cleaning up resources...")
        gc.collect()
        print("✅ Luna shutdown complete.")


if __name__ == "__main__":
    main()