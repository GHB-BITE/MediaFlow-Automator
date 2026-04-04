
"""
╔══════════════════════════════════════════════════════════╗
║         MediaFlow Automator PRO                          ║
║         FFmpeg Automation Suite — Fiverr Edition         ║
║         Python 3.10+ | Tkinter | subprocess              ║
╚══════════════════════════════════════════════════════════╝
"""

import subprocess
import threading
import queue
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import sys
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────
#  FFMPEG PATH  (fonctionne en .py ET .exe PyInstaller)
# ─────────────────────────────────────────────
def get_ffmpeg():
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    exe = os.path.join(base, "ffmpeg.exe")
    return exe if os.path.exists(exe) else "ffmpeg"   # fallback PATH


FFMPEG = get_ffmpeg()


# ─────────────────────────────────────────────
#  THEME  (GitHub-dark  +  accents néon)
# ─────────────────────────────────────────────
T = {
    "bg":       "#0E1117",
    "panel":    "#161B22",
    "card":     "#1C2128",
    "entry":    "#0D1117",
    "accent":   "#58A6FF",
    "green":    "#3FB950",
    "orange":   "#D29922",
    "red":      "#F85149",
    "purple":   "#BC8CFF",
    "fg":       "#E6EDF3",
    "fg2":      "#8B949E",
    "fg3":      "#484F58",
    "border":   "#30363D",
}

F       = ("Consolas", 10)
F_BOLD  = ("Consolas", 10, "bold")
F_SM    = ("Consolas", 9)
F_TITLE = ("Consolas", 17, "bold")
F_MONO  = ("Courier New", 9)


# ─────────────────────────────────────────────
#  HELPERS UI
# ─────────────────────────────────────────────
def btn(parent, text, cmd, fg=None, bg=None, font=F_SM, **kw):
    fg  = fg  or T["accent"]
    bg  = bg  or T["panel"]
    return tk.Button(
        parent, text=text, command=cmd,
        fg=fg, bg=bg,
        activeforeground="#FFFFFF", activebackground=T["card"],
        relief="flat", bd=0, padx=12, pady=6,
        font=font, cursor="hand2",
        highlightthickness=1,
        highlightbackground=fg, highlightcolor=fg,
        **kw,
    )


def lbl(parent, text, fg=None, font=F_SM, **kw):
    return tk.Label(parent, text=text,
                    fg=fg or T["fg2"], bg=parent.cget("bg"),
                    font=font, **kw)


def inp(parent, default="", width=30):
    e = tk.Entry(parent, width=width,
                 bg=T["entry"], fg=T["fg"],
                 insertbackground=T["accent"],
                 relief="flat", bd=6, font=F,
                 highlightthickness=1,
                 highlightbackground=T["border"],
                 highlightcolor=T["accent"])
    e.insert(0, default)
    return e


def sep(parent):
    tk.Frame(parent, bg=T["border"], height=1).pack(fill="x", padx=10, pady=6)


# ─────────────────────────────────────────────
#  TÂCHE + GESTIONNAIRE
# ─────────────────────────────────────────────
class Task:
    def __init__(self, name: str, command: list):
        self.name    = name
        self.command = command


class TaskManager:
    """
    File FIFO de tâches FFmpeg.
    Thread-safe : communique avec l'UI via des callbacks.
    """

    def __init__(self, log_cb, progress_cb, done_cb):
        self._queue    = queue.Queue()
        self._log      = log_cb
        self._progress = progress_cb
        self._done     = done_cb
        self.running   = False
        self._cancel   = False

    def add(self, task: Task):
        self._queue.put(task)
        self._log(f"[+] En attente : {task.name}", "info")

    def start(self):
        if self.running:
            return
        if self._queue.empty():
            self._log("⚠  Aucune tâche dans la file.", "warn")
            return
        self.running  = True
        self._cancel  = False
        threading.Thread(target=self._run, daemon=True).start()

    def cancel(self):
        self._cancel = True

    # ── worker thread ────────────────────────
    def _run(self):
        total = self._queue.qsize()
        done  = 0
        while not self._queue.empty():
            if self._cancel:
                self._log("✖  Annulé par l'utilisateur.", "warn")
                break
            task = self._queue.get()
            self._log(f"\n[▶] {task.name}", "section")
            self._exec(task)
            done += 1
            self._progress(int(done / total * 100))

        self.running = False
        self._done()

    def _exec(self, task: Task):
        self._log("  $ " + " ".join(str(c) for c in task.command), "cmd")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            proc = subprocess.Popen(
                task.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="ignore",
                creationflags=flags,
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self._log("  " + line, "ffmpeg")
            proc.wait()
            if proc.returncode == 0:
                self._log(f"  ✔ Terminé : {task.name}", "success")
            else:
                self._log(f"  ✖ Erreur (code {proc.returncode})", "error")
        except FileNotFoundError:
            self._log("  ✖ FFmpeg introuvable — vérifiez le PATH.", "error")
        except Exception as ex:
            self._log(f"  ✖ {ex}", "error")


# ─────────────────────────────────────────────
#  BARRE DE PROGRESSION (Frame-based, zéro Canvas)
# ─────────────────────────────────────────────
class ProgressBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=parent.cget("bg"), **kw)
        self._track = tk.Frame(self, bg=T["border"], height=7)
        self._track.pack(fill="x")
        self._track.pack_propagate(False)
        self._fill = tk.Frame(self._track, bg=T["accent"], height=7)
        self._fill.place(x=0, y=0, relheight=1.0, relwidth=0.0)
        self._lbl = lbl(self, "0 %", fg=T["fg3"], font=F_SM)
        self._lbl.pack(anchor="e", pady=(2, 0))

    def set(self, pct: int):
        pct = max(0, min(100, pct))
        color = T["green"] if pct == 100 else T["accent"]
        self._fill.config(bg=color)
        self._fill.place(relwidth=pct / 100)
        self._lbl.config(text=f"{pct} %", fg=color if pct == 100 else T["fg3"])


# ─────────────────────────────────────────────
#  CONSOLE DE LOG
# ─────────────────────────────────────────────
class Console(tk.Frame):
    COLORS = {
        "info":    T["fg2"],
        "cmd":     T["accent"],
        "ffmpeg":  T["fg3"],
        "section": T["purple"],
        "success": T["green"],
        "warn":    T["orange"],
        "error":   T["red"],
    }

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=T["panel"], **kw)

        hdr = tk.Frame(self, bg=T["panel"])
        hdr.pack(fill="x")
        lbl(hdr, "CONSOLE", fg=T["fg3"]).pack(side="left", padx=10, pady=6)
        btn(hdr, "Effacer", self.clear, fg=T["fg3"],
            bg=T["panel"]).pack(side="right", padx=6, pady=4)

        frame = tk.Frame(self, bg=T["bg"])
        frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        sb = tk.Scrollbar(frame, bg=T["bg"], troughcolor=T["bg"],
                          activebackground=T["accent"])
        self._txt = tk.Text(
            frame, bg=T["bg"], fg=T["fg2"],
            font=F_MONO, relief="flat", bd=0,
            state="disabled", selectbackground=T["accent"],
            wrap="word", yscrollcommand=sb.set,
        )
        sb.config(command=self._txt.yview)
        sb.pack(side="right", fill="y")
        self._txt.pack(fill="both", expand=True)

        for tag, col in self.COLORS.items():
            self._txt.tag_config(tag, foreground=col)

    def write(self, msg: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._txt.config(state="normal")
        self._txt.insert("end", f"[{ts}] {msg}\n", level)
        self._txt.see("end")
        self._txt.config(state="disabled")

    def clear(self):
        self._txt.config(state="normal")
        self._txt.delete("1.0", "end")
        self._txt.config(state="disabled")


# ─────────────────────────────────────────────
#  SECTION CARD  (conteneur visuel)
# ─────────────────────────────────────────────
class Card(tk.Frame):
    def __init__(self, parent, title: str, accent=None, **kw):
        super().__init__(parent, bg=T["card"],
                         highlightthickness=1,
                         highlightbackground=T["border"], **kw)
        hdr = tk.Frame(self, bg=T["panel"])
        hdr.pack(fill="x")
        tk.Label(hdr, text=title, font=F_BOLD,
                 fg=accent or T["accent"], bg=T["panel"],
                 padx=14, pady=8).pack(side="left")
        self._body = tk.Frame(self, bg=T["card"])
        self._body.pack(fill="both", expand=True, padx=14, pady=(8, 14))

    @property
    def body(self):
        return self._body


# ─────────────────────────────────────────────
#  APPLICATION PRINCIPALE
# ─────────────────────────────────────────────
class MediaFlowPro(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MediaFlow Automator PRO")
        self.geometry("880x680")
        self.minsize(800, 600)
        self.configure(bg=T["bg"])

        self._q    = queue.Queue()          # messages UI depuis le thread
        self._mgr  = TaskManager(
            log_cb      = self._enqueue_log,
            progress_cb = self._enqueue_progress,
            done_cb     = self._enqueue_done,
        )

        self._build()
        self.after(60, self._poll_queue)
        self._check_ffmpeg()

    # ── CONSTRUCTION ──────────────────────────
    def _build(self):
        self._header()
        # Corps principal : panedwindow gauche/droite
        pw = tk.PanedWindow(self, orient="horizontal",
                            bg=T["bg"], sashwidth=5)
        pw.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        left  = tk.Frame(pw, bg=T["bg"], width=360)
        right = tk.Frame(pw, bg=T["bg"])
        pw.add(left,  minsize=320)
        pw.add(right, minsize=360)

        self._left_panel(left)
        self._right_panel(right)

    def _header(self):
        h = tk.Frame(self, bg=T["panel"], height=58)
        h.pack(fill="x")
        h.pack_propagate(False)

        tk.Label(h, text="⬡ MediaFlow", font=F_TITLE,
                 fg=T["accent"], bg=T["panel"]).pack(side="left", padx=18, pady=10)
        tk.Label(h, text="Automator PRO", font=("Consolas", 14),
                 fg=T["purple"], bg=T["panel"]).pack(side="left", pady=12)

        self._status = tk.Label(h, text="● Prêt", font=F_SM,
                                fg=T["green"], bg=T["panel"])
        self._status.pack(side="right", padx=18)

        self._clock  = tk.Label(h, text="", font=F_SM,
                                fg=T["fg3"], bg=T["panel"])
        self._clock.pack(side="right", padx=8)
        self._tick()

    # ── PANNEAU GAUCHE  (fichier + paramètres) ─
    def _left_panel(self, parent):
        # ── Fichier d'entrée ──
        c1 = Card(parent, "📂  Fichier Source", accent=T["accent"])
        c1.pack(fill="x", pady=(0, 8))

        file_row = tk.Frame(c1.body, bg=T["card"])
        file_row.pack(fill="x")
        self._file_inp = inp(file_row, "", width=28)
        self._file_inp.pack(side="left", fill="x", expand=True, ipady=5)
        btn(file_row, "…", self._browse, fg=T["accent"],
            bg=T["card"], width=3).pack(side="right", padx=(6, 0))

        # ── Paramètres Cut ──
        c2 = Card(parent, "✂  Couper la Vidéo", accent=T["orange"])
        c2.pack(fill="x", pady=(0, 8))

        for label_txt, attr, default in [
            ("Début    (HH:MM:SS)", "_cut_start", "00:00:00"),
            ("Durée    (HH:MM:SS)", "_cut_dur",   "00:00:10"),
        ]:
            row = tk.Frame(c2.body, bg=T["card"])
            row.pack(fill="x", pady=3)
            lbl(row, label_txt, fg=T["fg2"]).pack(side="left", anchor="w")
            e = inp(row, default, width=13)
            e.pack(side="right")
            setattr(self, attr, e)

        btn(c2.body, "✂  Ajouter à la file", self._add_cut,
            fg=T["orange"]).pack(anchor="w", pady=(10, 0), ipady=7, fill="x")

        # ── Compression ──
        c3 = Card(parent, "⬇  Compression", accent=T["green"])
        c3.pack(fill="x", pady=(0, 8))

        crf_row = tk.Frame(c3.body, bg=T["card"])
        crf_row.pack(fill="x", pady=3)
        lbl(crf_row, "CRF  (18 = haute qualité, 32 = petit fichier)").pack(side="left")
        self._crf = inp(crf_row, "28", width=5)
        self._crf.pack(side="right")

        btn(c3.body, "⬇  Ajouter à la file", self._add_compress,
            fg=T["green"]).pack(anchor="w", pady=(10, 0), ipady=7, fill="x")

        # ── Extraction audio ──
        c4 = Card(parent, "♪  Extraire Audio", accent=T["purple"])
        c4.pack(fill="x", pady=(0, 8))

        fmt_row = tk.Frame(c4.body, bg=T["card"])
        fmt_row.pack(fill="x", pady=3)
        lbl(fmt_row, "Format de sortie").pack(side="left")
        self._audio_fmt = ttk.Combobox(
            fmt_row, values=["mp3","aac","wav","flac","ogg"],
            state="readonly", width=8, font=F,
        )
        self._audio_fmt.current(0)
        self._audio_fmt.pack(side="right")

        btn(c4.body, "♪  Ajouter à la file", self._add_audio,
            fg=T["purple"]).pack(anchor="w", pady=(10, 0), ipady=7, fill="x")

    # ── PANNEAU DROIT  (file + console + run) ─
    def _right_panel(self, parent):
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=0)
        parent.columnconfigure(0, weight=1)

        # File d'attente
        q_frame = Card(parent, "📋  File de tâches", accent=T["accent"])
        q_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        q_inner = tk.Frame(q_frame.body, bg=T["card"])
        q_inner.pack(fill="x")

        qsb = tk.Scrollbar(q_inner, bg=T["bg"], troughcolor=T["bg"])
        self._queue_lb = tk.Listbox(
            q_inner, bg=T["entry"], fg=T["fg"],
            font=F_SM, relief="flat",
            selectbackground=T["accent"],
            activestyle="none", height=5,
            yscrollcommand=qsb.set,
        )
        qsb.config(command=self._queue_lb.yview)
        qsb.pack(side="right", fill="y")
        self._queue_lb.pack(fill="x", expand=True)

        qbtn = tk.Frame(q_frame.body, bg=T["card"])
        qbtn.pack(fill="x", pady=(6, 0))
        btn(qbtn, "✖ Retirer sélection", self._remove_task,
            fg=T["red"], bg=T["card"]).pack(side="left")
        btn(qbtn, "🗑 Vider tout", self._clear_queue,
            fg=T["fg3"], bg=T["card"]).pack(side="left", padx=(6, 0))
        self._count_lbl = lbl(qbtn, "0 tâche(s)", fg=T["accent"])
        self._count_lbl.pack(side="right")

        # Console
        self._console = Console(parent)
        self._console.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        # Barre de contrôle
        ctrl = tk.Frame(parent, bg=T["panel"],
                        highlightthickness=1,
                        highlightbackground=T["border"])
        ctrl.grid(row=2, column=0, sticky="ew")
        ctrl_inner = tk.Frame(ctrl, bg=T["panel"])
        ctrl_inner.pack(fill="x", padx=12, pady=10)

        btn(ctrl_inner, "▶  LANCER TOUT", self._start,
            fg=T["green"], font=F_BOLD).pack(
            side="left", fill="x", expand=True, ipady=10, padx=(0, 8))
        btn(ctrl_inner, "⏹ Stop", self._stop,
            fg=T["red"]).pack(side="left", ipady=10, padx=(0, 8))
        btn(ctrl_inner, "🗑 Effacer log", self._console.clear,
            fg=T["fg3"]).pack(side="right", ipady=10)

        self._prog = ProgressBar(ctrl)
        self._prog.pack(fill="x", padx=12, pady=(0, 10))

    # ── ACTIONS ───────────────────────────────
    def _browse(self):
        f = filedialog.askopenfilename(
            filetypes=[("Vidéos / Audio",
                        "*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.flac"),
                       ("Tous", "*.*")])
        if f:
            self._file_inp.delete(0, "end")
            self._file_inp.insert(0, f)

    def _get_file(self) -> str | None:
        f = self._file_inp.get().strip()
        if not f:
            messagebox.showwarning("Fichier", "Sélectionnez un fichier source.")
            return None
        if not os.path.exists(f):
            messagebox.showerror("Fichier", "Fichier introuvable.")
            return None
        return f

    def _add_cut(self):
        f = self._get_file()
        if not f: return
        out = str(Path(f).with_stem(Path(f).stem + "_cut"))
        cmd = [FFMPEG, "-y", "-i", f,
               "-ss", self._cut_start.get(),
               "-t",  self._cut_dur.get(),
               "-c",  "copy", out]
        self._enqueue_task(Task("Cut — " + Path(f).name, cmd))

    def _add_compress(self):
        f = self._get_file()
        if not f: return
        out = str(Path(f).with_stem(Path(f).stem + "_compressed"))
        cmd = [FFMPEG, "-y", "-i", f,
               "-vcodec", "libx264",
               "-crf", self._crf.get(), out]
        self._enqueue_task(Task("Compress — " + Path(f).name, cmd))

    def _add_audio(self):
        f = self._get_file()
        if not f: return
        fmt = self._audio_fmt.get()
        out = str(Path(f).with_suffix(f".{fmt}"))
        cmd = [FFMPEG, "-y", "-i", f, "-q:a", "0", "-map", "a", out]
        self._enqueue_task(Task(f"Audio ({fmt}) — " + Path(f).name, cmd))

    def _enqueue_task(self, task: Task):
        self._mgr.add(task)
        self._queue_lb.insert("end", f"  {task.name}")
        n = self._queue_lb.size()
        self._count_lbl.config(text=f"{n} tâche(s)")

    def _remove_task(self):
        sel = self._queue_lb.curselection()
        if sel:
            self._queue_lb.delete(sel[0])
            self._count_lbl.config(text=f"{self._queue_lb.size()} tâche(s)")

    def _clear_queue(self):
        self._queue_lb.delete(0, "end")
        self._mgr._queue = queue.Queue()
        self._count_lbl.config(text="0 tâche(s)")

    def _start(self):
        if self._mgr.running:
            messagebox.showinfo("En cours", "Des tâches tournent déjà.")
            return
        self._prog.set(0)
        self._set_status("● Traitement…", T["orange"])
        self._mgr.start()

    def _stop(self):
        self._mgr.cancel()
        self._set_status("● Annulé", T["red"])

    # ── QUEUE POLLING (thread → UI) ───────────
    def _enqueue_log(self, msg, level="info"):
        self._q.put(("log", msg, level))

    def _enqueue_progress(self, pct):
        self._q.put(("progress", pct))

    def _enqueue_done(self):
        self._q.put(("done",))

    def _poll_queue(self):
        try:
            while True:
                item = self._q.get_nowait()
                if item[0] == "log":
                    self._console.write(item[1], item[2])
                elif item[0] == "progress":
                    self._prog.set(item[1])
                elif item[0] == "done":
                    self._set_status("● Terminé", T["green"])
                    self._queue_lb.delete(0, "end")
                    self._count_lbl.config(text="0 tâche(s)")
        except queue.Empty:
            pass
        self.after(60, self._poll_queue)

    # ── HELPERS ───────────────────────────────
    def _set_status(self, text, color=None):
        self._status.config(text=text, fg=color or T["green"])

    def _tick(self):
        self._clock.config(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick)

    def _check_ffmpeg(self):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            out = subprocess.check_output(
                [FFMPEG, "-version"], stderr=subprocess.STDOUT,
                creationflags=flags,
            )
            ver = out.decode(errors="ignore").split("\n")[0]
            self._console.write(f"✔ {ver}", "success")
        except FileNotFoundError:
            self._console.write(
                "✖ FFmpeg introuvable — placez ffmpeg.exe ici ou ajoutez au PATH.",
                "error")
            self._set_status("● FFmpeg manquant", T["red"])


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = MediaFlowPro()
    app.mainloop()
