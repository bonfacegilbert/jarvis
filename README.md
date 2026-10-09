# JARVIS — Personal AI Assistant for Windows

A voice-controlled assistant with a local AI brain. Say **"Jarvis"** followed by a command.

## What it can do

| Say... | It does... |
|---|---|
| "Jarvis, what time is it?" | Tells the time |
| "Jarvis, open Notepad / Calculator / browser / YouTube" | Opens apps & sites |
| "Jarvis, search for cats" | Google search |
| "Jarvis, volume up / down / mute" | Controls volume |
| "Jarvis, lock" | Locks your PC |
| "Jarvis, who is Alan Turing?" | Wikipedia answer |
| "Jarvis, tell me a joke" | Dad-level tech humor |
| "Jarvis, morning briefing" | Reads your tickets, deadlines & routine aloud |
| "Jarvis, go to sleep" | Exits |
| Anything else | Answered by the local AI brain |

## Setup (about 15 minutes)

### 1. Install Python
- Download from [python.org](https://www.python.org/downloads/) (3.10 or newer)
- ⚠️ During install, check **"Add python.exe to PATH"**

### 2. Install the AI brain (Ollama — free, runs offline)
- Download from [ollama.com](https://ollama.com/download) and install
- Open a terminal (PowerShell) and run:
  ```
  ollama pull llama3.2
  ```
- Leave Ollama running in the background. (No Ollama = built-in commands still work, but open questions won't.)

### 3. Install JARVIS
- Copy the `jarvis` folder to your laptop, e.g. `C:\jarvis`
- Open PowerShell **in that folder** and run:
  ```
  pip install -r requirements.txt
  ```
- If `PyAudio` fails (needed by SpeechRecognition), run:
  ```
  pip install pipwin
  pipwin install pyaudio
  ```

### 4. Run it
```
python jarvis.py
```
- Allow microphone access if Windows asks
- Say: **"Jarvis, what time is it?"**

## Tips
- Speak clearly, ~1–2 feet from the mic. First run calibrates background noise for 1 second.
- If the voice sounds wrong, change the voice-picking logic near the top of `jarvis.py` (Windows ships several SAPI5 voices).
- To use a different Ollama model, change `OLLAMA_MODEL` in `jarvis.py` and pull it with `ollama pull <name>`.

## Morning briefing

Say **"Jarvis, morning briefing"** (or "brief me") and he'll read aloud:
Durham weather, your open Freshservice tickets (urgent ones first),
upcoming deadlines, and your daily routine.

**Setup:**
1. Copy `jarvis_config.example.json` to `jarvis_config.json` (the real one is git-ignored, never committed).
2. Get your Freshservice API key: open Freshservice → click your profile
   picture (top right) → **Profile Settings** → copy the **API Key**.
3. Open `jarvis_config.json` (in the Jarvis folder) and paste the key into
   `freshservice_api_key`.
4. Edit `deadlines` and `routine` in the same file to match your day.

Without the API key, the briefing still covers deadlines and routine —
it just skips the ticket check.

## Desktop app version

Prefer a real window over the terminal? Run:

```
python jarvis_gui.py
```

Same brain, same voice — plus a conversation log, a Start/Stop button, and a
text box for typed commands (handy when the mic isn't convenient).

**Build a real Windows app** — double-click **build.bat** and it handles
everything: installs PyInstaller, builds `dist\JARVIS.exe` with the JARVIS
icon, and copies your config next to it. Double-click the exe to run —
it starts listening on its own, no button press needed.

Want JARVIS to greet you at login? Double-click **add_startup.bat**.

**Exe greets you as "Boss" or can't reach Freshservice?** The window now
shows a config-status line at the bottom: it tells you whether
`jarvis_config.json` loaded and exactly which folder it checked. If it says
NOT loaded, you're running a stale exe or the config isn't next to it —
rebuild with **build.bat** and launch the fresh `dist\JARVIS.exe` (keep your
real `jarvis_config.json` beside it, with your API key and
`freshservice_verify_ssl` set to `false` on the school network). Saying
"Jarvis, morning briefing" will also name the folder it looked in.

Note: keep Ollama running in the background — the exe talks to it for the
AI brain.

## Phase 2 ideas (when you're ready)
- **True wake word**: swap the "jarvis"-in-text check for [openWakeWord](https://github.com/dscripka/openWakeWord) so it listens hands-free without pressing anything
- **Home automation**: connect to Home Assistant via its REST API (`requests.post("http://homeassistant.local:8123/api/...")`) and add "Jarvis, turn off the living room lights"
- **GUI**: wrap it in a simple Tkinter window with a waveform animation
- **Memory**: log conversations to a file so it remembers context between sessions
