"""
JARVIS Desktop App - GUI version with live animated visualizer
===============================================================
A proper windowed app built on the same JARVIS engine (jarvis.py).

The HUD visualizer is LIVE:
  - idle      -> slow rotation, dim
  - listening -> arcs spin up bright, satellite dials sweep
  - speaking  -> core throbs, radial bars dance

Run it:
    python jarvis_gui.py

Build a standalone .exe (no Python needed to run it):
    pip install pyinstaller
    pyinstaller --onefile --windowed --name JARVIS jarvis_gui.py
    -> the exe lands in the dist/ folder. Double-click to run.
"""

import math
import os
import queue
import random
import sys
import threading
import time
import tkinter as tk
from tkinter import scrolledtext

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    psutil = None
    _HAS_PSUTIL = False

import jarvis as core  # engine: speak(), listen(), handle(), WAKE_WORD

# ------------------------------------------------------------- theme
BG = "#0a0e14"
PANEL = "#11161f"
ACCENT = "#00d4ff"
ACCENT_DIM = "#0a5a73"
TEXT = "#e6edf3"
DIM = "#8b949e"
GREEN = "#3fb950"
ORANGE = "#ff9a3c"

EXIT_PHRASES = ("goodbye", "go to sleep", "shut down", "power off")


def _app_dir():
    if getattr(sys, "frozen", False):  # PyInstaller exe
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _set_window_icon(root: tk.Tk):
    icon = os.path.join(_app_dir(), "jarvis.ico")
    if os.path.exists(icon):
        try:
            root.iconbitmap(icon)
        except Exception:
            pass


class JarvisApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("JARVIS")
        self.root.geometry("520x780")
        self.root.configure(bg=BG)
        self.root.minsize(420, 620)
        _set_window_icon(self.root)

        self.running = False
        self.events: queue.Queue = queue.Queue()
        self.viz_state = "idle"  # idle | listening | speaking
        self._t0 = time.time()

        # ---- header ----
        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=16, pady=(14, 4))

        self.dot = tk.Canvas(header, width=18, height=18, bg=BG, highlightthickness=0)
        self.dot.pack(side="left")
        self._draw_dot(DIM)

        title = tk.Frame(header, bg=BG)
        title.pack(side="left", padx=10)
        tk.Label(title, text="JARVIS", font=("Segoe UI", 18, "bold"),
                 fg=ACCENT, bg=BG).pack(anchor="w")
        self.status_var = tk.StringVar(value="Offline")
        tk.Label(title, textvariable=self.status_var, font=("Segoe UI", 10),
                 fg=DIM, bg=BG).pack(anchor="w")

        # ---- live visualizer ----
        self.viz = tk.Canvas(root, height=300, bg=BG, highlightthickness=0)
        self.viz.pack(fill="x", padx=16, pady=4)

        # ---- conversation log ----
        self.log_box = scrolledtext.ScrolledText(
            root, bg=PANEL, fg=TEXT, font=("Segoe UI", 11),
            insertbackground=TEXT, relief="flat", padx=12, pady=12,
            state="disabled", wrap="word",
        )
        self.log_box.pack(fill="both", expand=True, padx=16, pady=6)
        self.log_box.tag_config("you", foreground=ACCENT)
        self.log_box.tag_config("jarvis", foreground=TEXT)
        self.log_box.tag_config("sys", foreground=DIM, font=("Segoe UI", 10, "italic"))

        # ---- typed command row ----
        entry_row = tk.Frame(root, bg=BG)
        entry_row.pack(fill="x", padx=16, pady=6)
        self.entry = tk.Entry(entry_row, bg=PANEL, fg=TEXT, font=("Segoe UI", 11),
                              insertbackground=TEXT, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self.send_typed())
        tk.Button(entry_row, text="Send", command=self.send_typed,
                  bg=ACCENT, fg=BG, font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=6,
                  activebackground=ACCENT).pack(side="right")

        # ---- control buttons ----
        btn_row = tk.Frame(root, bg=BG)
        btn_row.pack(fill="x", padx=16, pady=(0, 14))
        self.toggle_btn = tk.Button(
            btn_row, text="▶  Start Listening", command=self.toggle,
            bg="#1c2530", fg=TEXT, font=("Segoe UI", 11, "bold"),
            relief="flat", pady=8, activebackground="#243040", activeforeground=TEXT,
        )
        self.toggle_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(btn_row, text="Clear", command=self.clear_log,
                  bg="#1c2530", fg=DIM, font=("Segoe UI", 10),
                  relief="flat", pady=8, padx=16,
                  activebackground="#243040", activeforeground=TEXT).pack(side="right")

        # ---- config status footer ----
        # Shows exactly which config the app loaded (or where it looked),
        # so a "greets me as Boss" launch is diagnosed at a glance.
        self.cfg_var = tk.StringVar()
        tk.Label(root, textvariable=self.cfg_var, font=("Segoe UI", 9),
                 fg=DIM, bg=BG, anchor="w", justify="left"
                 ).pack(fill="x", padx=16, pady=(0, 10))
        self._refresh_config_status()
        self.log("System", f"Config check: {self.cfg_var.get()}")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self._pump_events)
        self.root.after(50, self._animate)
        # real-app behavior: start listening on launch, no button press needed
        self.root.after(1500, self._autostart)

    def _autostart(self):
        if not self.running:
            self.toggle()

    # --------------------------------------------------- visualizer
    def _animate(self):
        """Redraw the HUD every 50ms. Called on the UI thread."""
        c = self.viz
        c.delete("all")
        w = c.winfo_width() or 480
        cx, cy = w / 2, 140
        t = time.time() - self._t0
        self._draw_hud(c, cx, cy, t, self.viz_state)
        self.root.after(50, self._animate)

    def _hex(self, c: tk.Canvas, x: float, y: float, r: float, t: float):
        pts = []
        for i in range(6):
            a = math.radians(t * 15 + i * 60)
            pts += [x + r * math.cos(a), y + r * math.sin(a)]
        c.create_polygon(pts, outline=ACCENT_DIM, fill="", width=1)

    def _draw_hud(self, c: tk.Canvas, cx: float, cy: float, t: float, state: str):
        """Super HUD: clock core, cyan+amber rings, live stats, hexagons."""
        bright = state in ("listening", "speaking")
        ring = ACCENT if bright else ACCENT_DIM

        # corner hexagons
        self._hex(c, cx - 196, 34, 15, t)
        self._hex(c, cx - 172, 52, 9, -t)
        self._hex(c, cx + 196, 34, 15, -t)
        self._hex(c, cx + 172, 52, 9, t)

        # live CPU / RAM readouts with leader lines
        if _HAS_PSUTIL:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            c.create_text(cx + 158, 26, text=f"{cpu:.0f}%", fill=ACCENT,
                          font=("Segoe UI", 13, "bold"))
            c.create_text(cx + 158, 42, text="CPU", fill=DIM,
                          font=("Segoe UI", 8))
            c.create_line(cx + 140, 52, cx + 118, 66, cx + 92, 66,
                          fill=ACCENT_DIM, width=1)
            c.create_text(cx - 158, 252, text=f"{mem:.0f}%", fill=ORANGE,
                          font=("Segoe UI", 13, "bold"))
            c.create_text(cx - 158, 268, text="RAM", fill=DIM,
                          font=("Segoe UI", 8))
            c.create_line(cx - 140, 242, cx - 118, 228, cx - 92, 228,
                          fill=ACCENT_DIM, width=1)

        # angular side brackets
        bx = 112
        for sgn in (-1, 1):
            x0 = cx + sgn * (bx + 30)
            x1 = cx + sgn * bx
            c.create_line(x0, cy - 84, x1, cy - 84, x1, cy - 30,
                          fill=ACCENT_DIM, width=2)
            c.create_line(x0, cy + 84, x1, cy + 84, x1, cy + 30,
                          fill=ACCENT_DIM, width=2)

        # outer tick ring (long ticks glow amber)
        R = 112
        for i in range(60):
            a = math.radians(i * 6)
            wide = i % 5 == 0
            r1, r2 = R, R + (10 if wide else 5)
            x1, y1 = cx + r1 * math.cos(a), cy + r1 * math.sin(a)
            x2, y2 = cx + r2 * math.cos(a), cy + r2 * math.sin(a)
            col = ORANGE if wide else ACCENT_DIM
            c.create_line(x1, y1, x2, y2, fill=col, width=2 if wide else 1)

        # dashed rotating ring
        for i in range(36):
            start = (t * 30 + i * 10) % 360
            c.create_arc(cx - 98, cy - 98, cx + 98, cy + 98,
                         start=start, extent=5,
                         outline=ACCENT_DIM, width=2, style="arc")

        # main cyan arc segments
        speed = 70 if bright else 25
        for i in range(4):
            start = (t * speed + i * 90) % 360
            c.create_arc(cx - 80, cy - 80, cx + 80, cy + 80,
                         start=start, extent=55,
                         outline=ring, width=7, style="arc")

        # amber arc segments, counter-rotating
        for i in range(3):
            start = (-t * speed * 0.7 + i * 120) % 360
            c.create_arc(cx - 88, cy - 88, cx + 88, cy + 88,
                         start=start, extent=40,
                         outline=ORANGE, width=4, style="arc")

        # thin counter-rotating cyan arcs
        for i in range(3):
            start = (-t * speed * 0.6 + i * 120 + 60) % 360
            c.create_arc(cx - 64, cy - 64, cx + 64, cy + 64,
                         start=start, extent=40,
                         outline=ACCENT_DIM, width=2, style="arc")

        # center clock - throbs while speaking
        if state == "speaking":
            env = abs(math.sin(t * 6.1)) * (0.55 + 0.45 * math.sin(t * 2.3 + 1))
            cr = 52 + 14 * env * random.uniform(0.7, 1.0)
        else:
            cr = 52 * (1 + 0.04 * math.sin(t * 2.5))
        c.create_oval(cx - cr, cy - cr, cx + cr, cy + cr, outline=ring, width=2)
        c.create_oval(cx - cr - 12, cy - cr - 12, cx + cr + 12, cy + cr + 12,
                      outline=ORANGE, width=1)
        c.create_text(cx, cy - 10, text=time.strftime("%I:%M %p"), fill=TEXT,
                      font=("Segoe UI", 24, "bold"))
        c.create_text(cx, cy + 22, text=time.strftime("%A, %B %d").upper(),
                      fill=DIM, font=("Segoe UI", 9))

        # speaking: dancing radial bars
        if state == "speaking":
            for i in range(28):
                a = math.radians(i * (360 / 28))
                h = 6 + 20 * abs(math.sin(t * 7 + i * 0.8)) * random.uniform(0.6, 1.0)
                x1, y1 = cx + 88 * math.cos(a), cy + 88 * math.sin(a)
                x2, y2 = cx + (88 + h) * math.cos(a), cy + (88 + h) * math.sin(a)
                c.create_line(x1, y1, x2, y2, fill=ACCENT, width=3)

        # side satellite dials (left cyan, right amber)
        for j, sx in enumerate((cx - 172, cx + 172)):
            dial = ring if j == 0 else ORANGE
            c.create_oval(sx - 22, cy - 22, sx + 22, cy + 22,
                          outline=ACCENT_DIM, width=2)
            start = (t * 50) % 360 if j == 0 else (-t * 50) % 360
            c.create_arc(sx - 22, cy - 22, sx + 22, cy + 22,
                         start=start, extent=120,
                         outline=dial, width=3, style="arc")
            c.create_oval(sx - 6, cy - 6, sx + 6, cy + 6, fill=ACCENT_DIM, outline="")

        labels = {"idle": "STANDBY", "listening": "LISTENING", "speaking": "SPEAKING"}
        c.create_text(cx, cy + R + 26, text=labels.get(state, ""),
                      fill=DIM, font=("Segoe UI", 10))

    # ------------------------------------------------------- UI helpers
    def _draw_dot(self, color: str):
        self.dot.delete("all")
        self.dot.create_oval(3, 3, 15, 15, fill=color, outline=color)

    def _refresh_config_status(self):
        """One-line diagnosis of the config load, shown in the footer."""
        st = core.config_status()
        if st["loaded"]:
            key_note = ("API key set" if st.get("has_key")
                        else "no API key yet — ticket checks off")
            self.cfg_var.set(f"Config loaded ✓ · {key_note}")
        else:
            where = os.path.dirname(st["path"])
            self.cfg_var.set(
                f"Config NOT loaded ✗ ({st['error']}) — looked in {where}")

    def _pump_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    who, text = payload
                    self._append(who, text)
                elif kind == "status":
                    self.status_var.set(payload)
                    self._draw_dot(GREEN if self.running else DIM)
                elif kind == "viz":
                    self.viz_state = payload
                elif kind == "stopped":
                    self.running = False
                    self.viz_state = "idle"
                    self.status_var.set("Offline")
                    self._draw_dot(DIM)
                    self.toggle_btn.config(text="▶  Start Listening")
        except queue.Empty:
            pass
        self.root.after(100, self._pump_events)

    def _append(self, who: str, text: str):
        self.log_box.config(state="normal")
        tag = {"You": "you", "JARVIS": "jarvis"}.get(who, "sys")
        self.log_box.insert("end", f"{who}: {text}\n\n", tag)
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def log(self, who: str, text: str):
        self.events.put(("log", (who, text)))

    def set_status(self, text: str):
        self.events.put(("status", text))

    def set_viz(self, state: str):
        self.events.put(("viz", state))

    def clear_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")

    # ---------------------------------------------------------- actions
    def toggle(self):
        if self.running:
            self.running = False
            self.set_viz("idle")
            self.log("System", "Stopping listener…")
            return
        self.running = True
        self.toggle_btn.config(text="■  Stop")
        self.set_status("Online — listening")
        self.set_viz("listening")
        threading.Thread(target=self._worker, daemon=True).start()

    def send_typed(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self.log("You", text)
        threading.Thread(target=self._answer, args=(text,), daemon=True).start()

    def _answer(self, command: str):
        response = core.handle(command)
        self.log("JARVIS", response)
        self.set_viz("speaking")
        core.speak(response)
        self.set_viz("listening" if self.running else "idle")

    def _worker(self):
        self.log("JARVIS", "JARVIS online. How can I help you?")
        self.set_viz("speaking")
        core.speak("JARVIS online. How can I help you?")
        self.set_viz("listening")
        self.log("System", f"Say '{core.WAKE_WORD}' followed by your command.")
        while self.running:
            try:
                text = core.listen()
            except Exception as exc:  # mic errors shouldn't kill the app
                self.log("System", f"Microphone error: {exc}")
                break
            if not text:
                continue
            if core.WAKE_WORD not in text.lower():
                continue
            command = text.lower().replace(core.WAKE_WORD, "").strip()
            self.log("You", text)
            if not command:
                self._answer("yes?")
                continue
            if any(p in command for p in EXIT_PHRASES):
                self.log("JARVIS", "Powering down. Goodbye.")
                self.set_viz("speaking")
                core.speak("Powering down. Goodbye.")
                break
            self._answer(command)
        self.events.put(("stopped", None))

    def on_close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    app_root = tk.Tk()
    JarvisApp(app_root)
    app_root.mainloop()
