"""
JARVIS - Personal AI Assistant for Windows
===========================================
Voice-controlled assistant with a local AI brain (Ollama).

Say "Jarvis" followed by your command, e.g.:
  "Jarvis, what time is it?"
  "Jarvis, open Notepad"
  "Jarvis, who is Alan Turing?"
  "Jarvis, volume up"
  "Jarvis, go to sleep"  (exits)

Requirements: Python 3.10+, microphone, internet (for speech recognition),
and Ollama running locally for the conversational brain (optional but recommended).
"""

import datetime
import json
import os
import random
import sys
import webbrowser

import pyttsx3
import requests
import speech_recognition as sr
import wikipedia

# ---------------------------------------------------------------- config
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"  # change to whichever model you pulled with Ollama
WAKE_WORD = "jarvis"

# ------------------------------------------------------- voice (speech)
engine = pyttsx3.init()  # uses SAPI5 on Windows - fully offline
engine.setProperty("rate", 175)

for _voice in engine.getProperty("voices"):
    if "david" in _voice.name.lower() or "mark" in _voice.name.lower():
        engine.setProperty("voice", _voice.id)
        break


def speak(text: str) -> None:
    """Speak text aloud and print it."""
    print(f"JARVIS: {text}")
    engine.say(text)
    engine.runAndWait()


# ------------------------------------------------------ morning briefing
if getattr(sys, "frozen", False):  # running as a PyInstaller exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "jarvis_config.json")

WEATHER_URL = ("https://api.open-meteo.com/v1/forecast?latitude=35.994"
               "&longitude=-78.8986&current=temperature_2m,weather_code"
               "&temperature_unit=fahrenheit&timezone=America%2FNew_York")

WMO_DESC = {0: "clear sky", 1: "mainly clear", 2: "partly cloudy",
            3: "overcast", 45: "foggy", 48: "foggy", 51: "light drizzle",
            53: "drizzle", 55: "heavy drizzle", 61: "light rain",
            63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
            75: "heavy snow", 80: "light showers", 81: "showers",
            82: "heavy showers", 95: "thunderstorms", 96: "storms with hail",
            99: "storms with hail"}

PRIORITY_NAME = {1: "low", 2: "medium", 3: "high", 4: "urgent"}


def get_weather():
    """Current Durham weather as a spoken phrase. None if unreachable."""
    try:
        # verify=False: school network inspects TLS; this is public data
        data = requests.get(WEATHER_URL, timeout=10, verify=False).json()
        cur = data.get("current", {})
        temp = round(cur.get("temperature_2m"))
        desc = WMO_DESC.get(cur.get("weather_code"), "fair")
        return f"{temp} degrees and {desc}"
    except Exception:
        return None


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def config_status() -> dict:
    """Where the config was looked for, whether it loaded, and why not.

    Exists so a frozen exe can say exactly which folder it checked —
    the silent {} fallback in load_config() is what made the
    "greets me as Boss" mystery hard to diagnose.
    """
    if not os.path.exists(CONFIG_PATH):
        return {"loaded": False, "path": CONFIG_PATH,
                "error": "file not found"}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        key = str(cfg.get("freshservice_api_key") or "")
        return {"loaded": True, "path": CONFIG_PATH, "error": None,
                "has_key": bool(key) and "PASTE" not in key}
    except Exception as exc:
        return {"loaded": False, "path": CONFIG_PATH,
                "error": f"could not parse: {exc}"}


def fs_my_tickets(cfg: dict):
    """Open/Pending Freshservice tickets assigned to me. None if not configured."""
    domain = cfg.get("freshservice_domain")
    api_key = cfg.get("freshservice_api_key")
    verify = cfg.get("freshservice_verify_ssl", True)
    if not domain or not api_key or "PASTE" in api_key:
        return None
    if not verify:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        me = requests.get(f"https://{domain}/api/v2/agents/me",
                          auth=(api_key, "X"), timeout=10,
                          verify=verify).json()
        my_id = me["agent"]["id"]
        found = {}
        for filt in ("new_and_my_open", "pending"):
            data = requests.get(
                f"https://{domain}/api/v2/tickets",
                params={"filter": filt, "per_page": 100, "page": 1},
                auth=(api_key, "X"), timeout=15,
                verify=verify).json()
            for t in data.get("tickets", []):
                if t.get("responder_id") == my_id and t.get("status") in (2, 3):
                    created = datetime.datetime.fromisoformat(
                        t["created_at"].replace("Z", "+00:00"))
                    days = (datetime.datetime.now(datetime.timezone.utc)
                            - created).days
                    found[t["id"]] = {
                        "number": t["id"],
                        "subject": t.get("subject", "No subject"),
                        "days": days,
                        "status": "open" if t["status"] == 2 else "pending",
                        "priority": t.get("priority", 2),
                    }
        return sorted(found.values(),
                      key=lambda x: (x["priority"], x["days"]), reverse=True)
    except Exception:
        return None


def morning_briefing() -> str:
    cfg = load_config()
    now = datetime.datetime.now()
    hour = now.hour
    greeting = ("Good morning" if hour < 12
                else "Good afternoon" if hour < 17 else "Good evening")
    name = cfg.get("name", "Boss").split()[0]
    parts = [f"{greeting}, {name}. "
             f"It is {now.strftime('%A, %B %d')}, "
             f"{now.strftime('%I:%M %p').lstrip('0')}."]

    # --- weather ---
    if cfg.get("weather", True):
        w = get_weather()
        if w:
            parts.append(f"In Durham it's {w}.")

    # --- tickets ---
    tickets = fs_my_tickets(cfg)
    if tickets is None:
        st = config_status()
        if not st["loaded"]:
            parts.append(
                "I couldn't find the config file. I looked for "
                f"jarvis_config.json in {os.path.dirname(st['path'])} "
                f"({st['error']}).")
        else:
            parts.append("I couldn't reach Freshservice. "
                         "Put your API key in jarvis_config.json to enable "
                         "ticket checks.")
    elif not tickets:
        parts.append("Your ticket queue is clear. Nicely done.")
    else:
        n = len(tickets)
        parts.append(f"You have {n} open ticket{'s' if n != 1 else ''} "
                     "assigned to you.")
        hot = [t for t in tickets if t["priority"] >= 3]
        if hot:
            parts.append(f"{len(hot)} of them "
                         f"{'is' if len(hot) == 1 else 'are'} "
                         f"{PRIORITY_NAME[hot[0]['priority']]} priority.")
        for t in tickets[:4]:
            extra = ""
            if t["priority"] == 4:
                extra = ", URGENT"
            elif t["priority"] == 3:
                extra = ", high priority"
            parts.append(f"Ticket {t['number']}: {t['subject']}. "
                         f"Status {t['status']}{extra}, open {t['days']} days.")
        if n > 4:
            parts.append(f"And {n - 4} more.")

    # --- deadlines ---
    today = now.date()
    deadlines = []
    for d in cfg.get("deadlines", []):
        try:
            due = datetime.datetime.strptime(d["due"], "%Y-%m-%d").date()
        except Exception:
            continue
        deadlines.append(((due - today).days, d.get("title", "Deadline"), due))
    deadlines.sort()
    for days_left, title, due in deadlines[:5]:
        if days_left < 0:
            parts.append(f"Overdue: {title}, was due {due.strftime('%B %d')}.")
        elif days_left == 0:
            parts.append(f"Due today: {title}.")
        elif days_left == 1:
            parts.append(f"Due tomorrow: {title}.")
        else:
            parts.append(f"{title}, due in {days_left} days, "
                         f"{due.strftime('%A, %B %d')}.")

    # --- routine ---
    routine = cfg.get("routine", [])
    if routine:
        parts.append("Today's routine: " + "; ".join(routine) + ".")

    parts.append("What would you like to tackle first?")
    return " ".join(parts)


# ------------------------------------------------------------------ brain
def ask_brain(prompt: str) -> str | None:
    """Ask the local Ollama model. Returns None if Ollama isn't reachable."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": (
                    "You are JARVIS, a witty but helpful AI assistant running on "
                    "the user's Windows laptop. Keep answers short and conversational, "
                    "as if speaking aloud.\n\nUser: " + prompt
                ),
                "stream": False,
            },
            timeout=90,
        )
        return response.json().get("response", "").strip() or None
    except Exception:
        return None


# -------------------------------------------------------------- commands
JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I would tell you a UDP joke, but you might not get it.",
    "There are only 10 kinds of people: those who understand binary and those who don't.",
    "Why did the developer go broke? He used up all his cache.",
]


def handle(command: str) -> str:
    """Run a built-in command, or fall back to the AI brain."""
    cmd = command.lower()

    # --- time & date ---
    if "time" in cmd:
        return "The time is " + datetime.datetime.now().strftime("%I:%M %p") + "."
    if "date" in cmd or "day is it" in cmd:
        return "Today is " + datetime.datetime.now().strftime("%A, %B %d, %Y") + "."

    # --- morning briefing ---
    if any(p in cmd for p in ("morning briefing", "brief me", "briefing",
                              "daily briefing", "my briefing", "start my day")):
        return morning_briefing()

    # --- greeting: tell me what I have for the day ---
    greetings = ("hi", "hello", "hey", "good morning", "good afternoon",
                 "good evening", "greetings", "howdy", "yo", "sup")
    if cmd in greetings or any(cmd.startswith(g + " ") for g in greetings):
        return morning_briefing()

    # --- open apps & sites ---
    if "open notepad" in cmd:
        os.system("start notepad")
        return "Opening Notepad."
    if "open calculator" in cmd:
        os.system("start calc")
        return "Opening Calculator."
    if "open youtube" in cmd:
        webbrowser.open("https://www.youtube.com")
        return "Opening YouTube."
    if "open browser" in cmd or "open chrome" in cmd or "open google" in cmd:
        webbrowser.open("https://www.google.com")
        return "Opening your browser."
    if "search" in cmd:
        query = cmd.replace("search", "").replace("for", "").strip()
        webbrowser.open(f"https://www.google.com/search?q={query}")
        return f"Searching for {query}."

    # --- volume ---
    if "volume up" in cmd or "turn it up" in cmd:
        import pyautogui
        for _ in range(5):
            pyautogui.press("volumeup")
        return "Turning the volume up."
    if "volume down" in cmd or "turn it down" in cmd:
        import pyautogui
        for _ in range(5):
            pyautogui.press("volumedown")
        return "Turning the volume down."
    if "mute" in cmd:
        import pyautogui
        pyautogui.press("volumemute")
        return "Muted."

    # --- system ---
    if "lock" in cmd:
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "Locking the workstation."

    # --- knowledge ---
    if "wikipedia" in cmd or "who is" in cmd or "what is" in cmd:
        topic = cmd
        for word in ("wikipedia", "who is", "what is"):
            topic = topic.replace(word, "")
        topic = topic.strip()
        if topic:
            try:
                return wikipedia.summary(topic, sentences=2)
            except Exception:
                pass  # fall through to the brain

    # --- fun ---
    if "joke" in cmd:
        return random.choice(JOKES)

    # --- fallback: ask the AI brain ---
    answer = ask_brain(command)
    if answer:
        return answer
    return (
        "My AI brain isn't reachable right now. "
        "Make sure Ollama is running — see the README."
    )


# --------------------------------------------------------------- listen
def listen() -> str:
    """Listen once via the microphone and return the transcribed text."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = recognizer.listen(source, timeout=15, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            return ""
    try:
        text = recognizer.recognize_google(audio)
        print(f"You: {text}")
        return text
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        speak("The speech service is unavailable. Check your internet connection.")
        return ""


# ----------------------------------------------------------------- main
def main() -> None:
    speak("JARVIS online. How can I help you?")
    print(f"\nListening... say '{WAKE_WORD}' followed by your command.\n")

    while True:
        try:
            text = listen()
        except KeyboardInterrupt:
            break
        if not text:
            continue
        if WAKE_WORD not in text.lower():
            continue

        command = text.lower().replace(WAKE_WORD, "").strip()
        if not command:
            speak("Yes?")
            continue
        if any(phrase in command for phrase in ("goodbye", "go to sleep", "shut down")):
            speak("Powering down. Goodbye.")
            break

        speak(handle(command))


if __name__ == "__main__":
    main()
