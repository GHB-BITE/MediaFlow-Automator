"""
╔══════════════════════════════════════════════════════════════════╗
║          MediaFlow Automator PRO  ·  Ultimate Edition            ║
║          FFmpeg Suite + Media Organizer — Merged & Enhanced      ║
║          Python 3.10+ | Tkinter | subprocess | shutil            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import subprocess
import threading
import queue
import shutil
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import sys
import time
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────────
#  FFMPEG PATH
# ─────────────────────────────────────────────────────────────────
def get_ffmpeg() -> str:
    """Retourne le chemin vers ffmpeg (embarqué ou système)."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    exe = os.path.join(base, "ffmpeg.exe")
    return exe if os.path.exists(exe) else "ffmpeg"


FFMPEG = get_ffmpeg()


# ─────────────────────────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────────────────────────
T = {
    "bg":     "#0E1117",
    "panel":  "#161B22",
    "card":   "#1C2128",
    "entry":  "#0D1117",
    "accent": "#58A6FF",
    "green":  "#3FB950",
    "orange": "#D29922",
    "red":    "#F85149",
    "purple": "#BC8CFF",
    "teal":   "#39D0D8",
    "fg":     "#E6EDF3",
    "fg2":    "#8B949E",
    "fg3":    "#484F58",
    "border": "#30363D",
}

F       = ("Consolas", 10)
F_BOLD  = ("Consolas", 10, "bold")
F_SM    = ("Consolas", 9)
F_TITLE = ("Consolas", 17, "bold")
F_MONO  = ("Courier New", 9)


# ─────────────────────────────────────────────────────────────────
#  FORMATS MEDIA
# ─────────────────────────────────────────────────────────────────
MEDIA_FORMATS: dict[str, list[str]] = {
    "mp4":  [".mp4"],  "mkv":  [".mkv"],  "avi":  [".avi"],
    "mov":  [".mov"],  "webm": [".webm"], "flv":  [".flv"],
    "mpeg": [".mpeg"], "ts":   [".ts"],   "vob":  [".vob"],
    "m4v":  [".m4v"],  "mp3":  [".mp3"],  "wav":  [".wav"],
    "aac":  [".aac"],  "m4a":  [".m4a"],  "flac": [".flac"],
    "ogg":  [".ogg"],  "opus": [".opus"],
}

VIDEO_EXTENSIONS: list[str] = [
    ".mp4", ".mkv", ".avi", ".mov", ".webm",
    ".flv", ".mpeg", ".ts", ".vob", ".m4v",
]


# ─────────────────────────────────────────────────────────────────
#  HELPERS UI
# ─────────────────────────────────────────────────────────────────
def btn(parent, text: str, cmd, fg=None, bg=None, font=F_SM, **kw) -> tk.Button:
    fg = fg or T["accent"]
    bg = bg or T["panel"]
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


def lbl(parent, text: str, fg=None, font=F_SM, **kw) -> tk.Label:
    return tk.Label(
        parent, text=text,
        fg=fg or T["fg2"],
        bg=parent.cget("bg"),
        font=font, **kw,
    )


def inp(parent, default: str = "", width: int = 30) -> tk.Entry:
    e = tk.Entry(
        parent, width=width,
        bg=T["entry"], fg=T["fg"],
        insertbackground=T["accent"],
        relief="flat", bd=6, font=F,
        highlightthickness=1,
        highlightbackground=T["border"],
        highlightcolor=T["accent"],
    )
    e.insert(0, default)
    return e


def sep(parent) -> None:
    tk.Frame(parent, bg=T["border"], height=1).pack(fill="x", padx=10, pady=6)


# ─────────────────────────────────────────────────────────────────
#  TASK + TASK MANAGER
# ─────────────────────────────────────────────────────────────────
class Task:
    """Représente une tâche FFmpeg (nom + commande)."""

    def __init__(self, name: str, command: list):
        self.name    = name
        self.command = command


class TaskManager:
    """
    File FIFO de tâches FFmpeg.
    Thread-safe : communique avec l'UI via des callbacks.
    done_cb reçoit maintenant (done: int, errors: int, duration: str).
    """

    def __init__(self, log_cb, progress_cb, done_cb):
        self._queue       = queue.Queue()
        self._log         = log_cb
        self._progress    = progress_cb
        self._done        = done_cb
        self.running      = False
        self._cancel      = False
        self._start_time  = 0.0
        self._error_count = 0

    def add(self, task: Task) -> None:
        self._queue.put(task)
        self._log(f"[+] En attente : {task.name}", "info")

    def start(self) -> None:
        if self.running:
            return
        if self._queue.empty():
            self._log("⚠  Aucune tâche dans la file.", "warn")
            return
        self.running = True
        self._cancel = False
        threading.Thread(target=self._run, daemon=True).start()

    def cancel(self) -> None:
        self._cancel = True

    def reset_queue(self) -> None:
        self._queue = queue.Queue()

    def _run(self) -> None:
        total             = self._queue.qsize()
        done              = 0
        self._start_time  = time.time()
        self._error_count = 0

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

        # ── calcul de la durée totale ──────────────────────────────
        elapsed      = time.time() - self._start_time
        mins, secs   = divmod(int(elapsed), 60)
        hrs,  mins   = divmod(mins, 60)
        duration     = f"{hrs:02d}:{mins:02d}:{secs:02d}"

        self._done(done, self._error_count, duration)

    def _exec(self, task: Task) -> None:
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
                self._error_count += 1
        except FileNotFoundError:
            self._log("  ✖ FFmpeg introuvable — vérifiez le PATH.", "error")
            self._error_count += 1
        except PermissionError as ex:
            self._log(f"  ✖ Permission refusée : {ex}", "error")
            self._error_count += 1
        except OSError as ex:
            self._log(f"  ✖ Erreur OS : {ex}", "error")
            self._error_count += 1
        except Exception as ex:
            self._log(f"  ✖ Erreur inattendue : {ex}", "error")
            self._error_count += 1


# ─────────────────────────────────────────────────────────────────
#  PROGRESS BAR
# ─────────────────────────────────────────────────────────────────
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

    def set(self, pct: int) -> None:
        pct   = max(0, min(100, pct))
        color = T["green"] if pct == 100 else T["accent"]
        self._fill.config(bg=color)
        self._fill.place(relwidth=pct / 100)
        self._lbl.config(text=f"{pct} %", fg=color if pct == 100 else T["fg3"])


# ─────────────────────────────────────────────────────────────────
#  CONSOLE
# ─────────────────────────────────────────────────────────────────
class Console(tk.Frame):
    COLORS = {
        "info":    T["fg2"],
        "cmd":     T["accent"],
        "ffmpeg":  T["fg3"],
        "section": T["purple"],
        "success": T["green"],
        "warn":    T["orange"],
        "error":   T["red"],
        "org":     T["teal"],
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

    def write(self, msg: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._txt.config(state="normal")
        self._txt.insert("end", f"[{ts}] {msg}\n", level)
        self._txt.see("end")
        self._txt.config(state="disabled")

    def clear(self) -> None:
        self._txt.config(state="normal")
        self._txt.delete("1.0", "end")
        self._txt.config(state="disabled")


# ─────────────────────────────────────────────────────────────────
#  CARD
# ─────────────────────────────────────────────────────────────────
class Card(tk.Frame):
    def __init__(self, parent, title: str, accent=None, **kw):
        super().__init__(
            parent, bg=T["card"],
            highlightthickness=1,
            highlightbackground=T["border"], **kw,
        )
        hdr = tk.Frame(self, bg=T["panel"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text=title, font=F_BOLD,
            fg=accent or T["accent"], bg=T["panel"],
            padx=14, pady=8,
        ).pack(side="left")
        self._body = tk.Frame(self, bg=T["card"])
        self._body.pack(fill="both", expand=True, padx=14, pady=(8, 14))

    @property
    def body(self) -> tk.Frame:
        return self._body


# ─────────────────────────────────────────────────────────────────
#  ONGLET 1 : FFMPEG AUTOMATOR
# ─────────────────────────────────────────────────────────────────
class FFmpegTab(tk.Frame):
    """Onglet FFmpeg : couper, compresser, extraire audio — en batch."""

    def __init__(self, parent, console: Console, mgr: TaskManager, **kw):
        super().__init__(parent, bg=T["bg"], **kw)
        self._console        = console
        self._mgr            = mgr
        self._selected_files: list[str] = []
        self._build()

    # ── Construction ──────────────────────────────────────────────
    def _build(self) -> None:
        pw = tk.PanedWindow(self, orient="horizontal",
                            bg=T["bg"], sashwidth=5)
        pw.pack(fill="both", expand=True)
        left  = tk.Frame(pw, bg=T["bg"], width=360)
        right = tk.Frame(pw, bg=T["bg"])
        pw.add(left,  minsize=320)
        pw.add(right, minsize=360)
        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent: tk.Frame) -> None:
        # ── Fichier source ─────────────────────────────────────────
        c1 = Card(parent, "📂  Fichier Source", accent=T["accent"])
        c1.pack(fill="x", pady=(0, 8))

        file_row = tk.Frame(c1.body, bg=T["card"])
        file_row.pack(fill="x")

        self._file_inp = inp(file_row, "", width=28)
        self._file_inp.pack(side="left", fill="x", expand=True, ipady=5)

        btn(file_row, "📄", self._browse,
            fg=T["accent"], bg=T["card"], width=3).pack(
            side="right", padx=(6, 0))
        btn(file_row, "📁", self._browse_folder,
            fg=T["teal"],  bg=T["card"], width=3).pack(
            side="right", padx=(6, 0))

        # ── Cut ────────────────────────────────────────────────────
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

        # ── Compression ────────────────────────────────────────────
        c3 = Card(parent, "⬇  Compression", accent=T["green"])
        c3.pack(fill="x", pady=(0, 8))

        crf_row = tk.Frame(c3.body, bg=T["card"])
        crf_row.pack(fill="x", pady=3)
        lbl(crf_row, "CRF  (18 = haute qualité, 32 = petit fichier)").pack(side="left")
        self._crf = inp(crf_row, "28", width=5)
        self._crf.pack(side="right")

        btn(c3.body, "⬇  Ajouter à la file", self._add_compress,
            fg=T["green"]).pack(anchor="w", pady=(10, 0), ipady=7, fill="x")

        # ── Audio ──────────────────────────────────────────────────
        c4 = Card(parent, "♪  Extraire Audio", accent=T["purple"])
        c4.pack(fill="x", pady=(0, 8))

        fmt_row = tk.Frame(c4.body, bg=T["card"])
        fmt_row.pack(fill="x", pady=3)
        lbl(fmt_row, "Format de sortie").pack(side="left")
        self._audio_fmt = ttk.Combobox(
            fmt_row, values=["mp3", "aac", "wav", "flac", "ogg"],
            state="readonly", width=8, font=F,
        )
        self._audio_fmt.current(0)
        self._audio_fmt.pack(side="right")

        btn(c4.body, "♪  Ajouter à la file", self._add_audio,
            fg=T["purple"]).pack(anchor="w", pady=(10, 0), ipady=7, fill="x")

    def _build_right(self, parent: tk.Frame) -> None:
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=0)
        parent.columnconfigure(0, weight=1)

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

        ctrl = tk.Frame(parent, bg=T["panel"],
                        highlightthickness=1,
                        highlightbackground=T["border"])
        ctrl.grid(row=1, column=0, sticky="ew")
        ctrl_inner = tk.Frame(ctrl, bg=T["panel"])
        ctrl_inner.pack(fill="x", padx=12, pady=10)

        btn(ctrl_inner, "▶  LANCER TOUT", self._start,
            fg=T["green"], font=F_BOLD).pack(
            side="left", fill="x", expand=True, ipady=10, padx=(0, 8))
        btn(ctrl_inner, "⏹ Stop", self._stop,
            fg=T["red"]).pack(side="left", ipady=10, padx=(0, 8))

        self._prog = ProgressBar(ctrl)
        self._prog.pack(fill="x", padx=12, pady=(0, 10))

    # ── Sélection fichiers ─────────────────────────────────────────

    def _browse(self) -> None:
        try:
            files = filedialog.askopenfilenames(
                title="Sélectionner des fichiers vidéo",
                filetypes=[
                    ("Fichiers vidéo",
                     "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.mpeg *.ts *.vob *.m4v"),
                    ("Tous les fichiers", "*.*"),
                ],
            )
            if files:
                self._selected_files = list(files)
                self._file_inp.delete(0, "end")
                self._file_inp.insert(0, f"{len(files)} fichier(s) sélectionné(s)")
                self._console.write(
                    f"📂 {len(files)} fichier(s) chargé(s)", "info"
                )
        except Exception as ex:
            self._console.write(f"✖ Erreur sélection fichiers : {ex}", "error")

    def _browse_folder(self) -> None:
        try:
            folder = filedialog.askdirectory(
                title="Sélectionner un dossier contenant des vidéos"
            )
            if not folder:
                return
            folder_path = Path(folder)
            files: list[Path] = []
            for ext in VIDEO_EXTENSIONS:
                files.extend(folder_path.glob(f"*{ext}"))
            if not files:
                messagebox.showwarning(
                    "Dossier vide",
                    "Aucun fichier vidéo trouvé dans ce dossier."
                )
                return
            self._selected_files = [str(f) for f in files]
            self._file_inp.delete(0, "end")
            self._file_inp.insert(
                0, f"{len(files)} vidéo(s) depuis le dossier"
            )
            self._console.write(
                f"📁 {len(files)} vidéo(s) chargée(s) depuis le dossier", "success"
            )
        except Exception as ex:
            self._console.write(f"✖ Erreur chargement dossier : {ex}", "error")

    def _get_files(self) -> list[str] | None:
        if not self._selected_files:
            messagebox.showwarning(
                "Fichiers",
                "Sélectionnez d'abord des fichiers vidéo."
            )
            return None
        return self._selected_files

    # ── Actions FFmpeg ─────────────────────────────────────────────

    def _add_cut(self) -> None:
        try:
            files = self._get_files()
            if not files:
                return
            start = self._cut_start.get().strip()
            dur   = self._cut_dur.get().strip()
            if not start or not dur:
                messagebox.showwarning("Paramètres", "Renseignez Début et Durée.")
                return
            for f in files:
                fpath = Path(f)
                out   = str(fpath.with_stem(fpath.stem + "_cut"))
                cmd   = [FFMPEG, "-y", "-i", str(fpath),
                         "-ss", start, "-t", dur, "-c", "copy", out]
                self._enqueue_task(Task(f"Cut — {fpath.name}", cmd))
        except Exception as ex:
            self._console.write(f"✖ Erreur ajout Cut : {ex}", "error")

    def _add_compress(self) -> None:
        try:
            files = self._get_files()
            if not files:
                return
            crf_val = self._crf.get().strip()
            if not crf_val.isdigit() or not (0 <= int(crf_val) <= 51):
                messagebox.showwarning(
                    "CRF invalide",
                    "La valeur CRF doit être un entier entre 0 et 51."
                )
                return
            count = 0
            for f in files:
                fpath = Path(f)
                out   = str(fpath.with_stem(fpath.stem + "_compressed"))
                cmd   = [FFMPEG, "-y", "-i", str(fpath),
                         "-vcodec", "libx264", "-crf", crf_val, out]
                self._enqueue_task(Task(f"Compress — {fpath.name}", cmd))
                count += 1
            self._console.write(
                f"✔ {count} tâche(s) de compression ajoutée(s)", "success"
            )
        except Exception as ex:
            self._console.write(f"✖ Erreur ajout Compress : {ex}", "error")

    def _add_audio(self) -> None:
        try:
            files = self._get_files()
            if not files:
                return
            fmt   = self._audio_fmt.get()
            count = 0
            for f in files:
                fpath = Path(f)
                out   = str(fpath.with_suffix(f".{fmt}"))
                cmd   = [FFMPEG, "-y", "-i", str(fpath),
                         "-q:a", "0", "-map", "a", out]
                self._enqueue_task(
                    Task(f"Audio ({fmt}) — {fpath.name}", cmd)
                )
                count += 1
            self._console.write(
                f"✔ {count} tâche(s) audio ajoutée(s)", "success"
            )
        except Exception as ex:
            self._console.write(f"✖ Erreur ajout Audio : {ex}", "error")

    # ── Gestion de la file ─────────────────────────────────────────

    def _enqueue_task(self, task: Task) -> None:
        try:
            self._mgr.add(task)
            self._queue_lb.insert("end", f"  {task.name}")
            self._count_lbl.config(text=f"{self._queue_lb.size()} tâche(s)")
        except Exception as ex:
            self._console.write(f"✖ Erreur file d'attente : {ex}", "error")

    def _remove_task(self) -> None:
        try:
            sel = self._queue_lb.curselection()
            if sel:
                self._queue_lb.delete(sel[0])
                self._count_lbl.config(text=f"{self._queue_lb.size()} tâche(s)")
        except Exception as ex:
            self._console.write(f"✖ Erreur retrait tâche : {ex}", "error")

    def _clear_queue(self) -> None:
        try:
            self._queue_lb.delete(0, "end")
            self._mgr.reset_queue()
            self._count_lbl.config(text="0 tâche(s)")
        except Exception as ex:
            self._console.write(f"✖ Erreur vidage file : {ex}", "error")

    def _start(self) -> None:
        try:
            if self._mgr.running:
                messagebox.showinfo("En cours", "Des tâches tournent déjà.")
                return
            self._prog.set(0)
            self._mgr.start()
        except Exception as ex:
            self._console.write(f"✖ Erreur démarrage : {ex}", "error")

    def _stop(self) -> None:
        try:
            self._mgr.cancel()
        except Exception as ex:
            self._console.write(f"✖ Erreur arrêt : {ex}", "error")

    def update_progress(self, pct: int) -> None:
        self._prog.set(pct)

    def reset_queue_ui(self) -> None:
        self._queue_lb.delete(0, "end")
        self._count_lbl.config(text="0 tâche(s)")


# ─────────────────────────────────────────────────────────────────
#  ONGLET 2 : MEDIA ORGANIZER
# ─────────────────────────────────────────────────────────────────
class OrganizerTab(tk.Frame):
    """Trie les fichiers médias dans des sous-dossiers selon leur extension."""

    def __init__(self, parent, console: Console, **kw):
        super().__init__(parent, bg=T["bg"], **kw)
        self._console         = console
        self._selected_folder: Path | None = None
        self._build()

    def _build(self) -> None:
        c1 = Card(self, "📁  Dossier à Organiser", accent=T["teal"])
        c1.pack(fill="x", pady=(0, 8))

        folder_row = tk.Frame(c1.body, bg=T["card"])
        folder_row.pack(fill="x")
        self._folder_inp = inp(folder_row, "Aucun dossier sélectionné", width=40)
        self._folder_inp.config(state="readonly")
        self._folder_inp.pack(side="left", fill="x", expand=True, ipady=5)
        btn(folder_row, "…", self._select_folder, fg=T["teal"],
            bg=T["card"], width=3).pack(side="right", padx=(6, 0))

        c2 = Card(self, "⚙  Options", accent=T["teal"])
        c2.pack(fill="x", pady=(0, 8))

        opt_row = tk.Frame(c2.body, bg=T["card"])
        opt_row.pack(fill="x", pady=4)

        self._dry_run = tk.BooleanVar(value=False)
        tk.Checkbutton(
            opt_row,
            text="Mode aperçu (ne déplace rien)",
            variable=self._dry_run,
            bg=T["card"], fg=T["fg2"],
            selectcolor=T["entry"],
            activebackground=T["card"],
            font=F_SM,
        ).pack(side="left")

        self._recursive = tk.BooleanVar(value=False)
        tk.Checkbutton(
            opt_row,
            text="Inclure les sous-dossiers",
            variable=self._recursive,
            bg=T["card"], fg=T["fg2"],
            selectcolor=T["entry"],
            activebackground=T["card"],
            font=F_SM,
        ).pack(side="left", padx=(20, 0))

        act = tk.Frame(c2.body, bg=T["card"])
        act.pack(fill="x", pady=(8, 0))
        btn(act, "🚀  Organiser les fichiers", self._organize,
            fg=T["teal"], font=F_BOLD).pack(
            side="left", ipady=8, fill="x", expand=True)

        c3 = Card(self, "📋  Formats pris en charge", accent=T["fg3"])
        c3.pack(fill="x", pady=(0, 8))

        fmt_inner = tk.Frame(c3.body, bg=T["card"])
        fmt_inner.pack(fill="x")
        for i, (folder, exts) in enumerate(MEDIA_FORMATS.items()):
            tk.Label(
                fmt_inner,
                text=f"{folder}/  {', '.join(exts)}",
                fg=T["fg3"], bg=T["card"],
                font=F_SM, anchor="w",
            ).grid(row=i // 6, column=i % 6, sticky="w", padx=10, pady=1)

    def _select_folder(self) -> None:
        try:
            folder = filedialog.askdirectory()
            if folder:
                self._selected_folder = Path(folder)
                self._folder_inp.config(state="normal")
                self._folder_inp.delete(0, "end")
                self._folder_inp.insert(0, folder)
                self._folder_inp.config(state="readonly")
                self._console.write(f"📁 Dossier sélectionné : {folder}", "org")
        except Exception as ex:
            self._console.write(f"✖ Erreur sélection dossier : {ex}", "error")

    def _organize(self) -> None:
        try:
            if not self._selected_folder:
                messagebox.showwarning("Dossier", "Sélectionnez un dossier d'abord.")
                return
            if not self._selected_folder.exists():
                messagebox.showerror("Dossier", "Le dossier sélectionné n'existe plus.")
                return
            dry_run   = self._dry_run.get()
            recursive = self._recursive.get()
            if dry_run:
                self._console.write(
                    "🔍 Mode aperçu activé (aucun fichier déplacé)", "warn"
                )
            threading.Thread(
                target=self._organize_worker,
                args=(dry_run, recursive),
                daemon=True,
            ).start()
        except Exception as ex:
            self._console.write(f"✖ Erreur lancement organisation : {ex}", "error")

    def _organize_worker(self, dry_run: bool, recursive: bool) -> None:
        """Worker thread — ne bloque pas l'UI."""
        try:
            moved   = 0
            skipped = 0
            errors  = 0

            glob_pattern = "**/*" if recursive else "*"
            files = [
                f for f in self._selected_folder.glob(glob_pattern)
                if f.is_file()
            ]

            self._console.write(
                f"[▶] Analyse de {len(files)} fichier(s)…", "section"
            )

            for file in files:
                if file.parent.name in MEDIA_FORMATS and not recursive:
                    skipped += 1
                    continue

                suffix  = file.suffix.lower()
                matched = False

                for folder_name, extensions in MEDIA_FORMATS.items():
                    if suffix in extensions:
                        target_folder = self._selected_folder / folder_name
                        target_path   = target_folder / file.name

                        if dry_run:
                            self._console.write(
                                f"  [aperçu] {file.name} → {folder_name}/", "org"
                            )
                            moved += 1
                        else:
                            try:
                                target_folder.mkdir(exist_ok=True)
                                if target_path.exists():
                                    ts = datetime.now().strftime("%H%M%S")
                                    target_path = (
                                        target_folder
                                        / f"{file.stem}_{ts}{file.suffix}"
                                    )
                                shutil.move(str(file), str(target_path))
                                self._console.write(
                                    f"  📦 {file.name} → {folder_name}/", "org"
                                )
                                moved += 1
                            except PermissionError as ex:
                                self._console.write(
                                    f"  ✖ Permission refusée : {file.name} — {ex}",
                                    "error",
                                )
                                errors += 1
                            except shutil.Error as ex:
                                self._console.write(
                                    f"  ✖ Erreur déplacement : {file.name} — {ex}",
                                    "error",
                                )
                                errors += 1
                            except OSError as ex:
                                self._console.write(
                                    f"  ✖ Erreur OS : {file.name} — {ex}", "error"
                                )
                                errors += 1
                        matched = True
                        break

                if not matched:
                    self._console.write(
                        f"  ⊘ Ignoré (format inconnu) : {file.name}", "ffmpeg"
                    )

            # ── Rapport final ──────────────────────────────────────
            now         = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
            mode_label  = "APERÇU (simulation)" if dry_run else "RÉEL (fichiers déplacés)"
            status_icon = "✔" if errors == 0 else "⚠"
            sep_line    = "─" * 52

            self._console.write(f"\n{sep_line}", "section")
            self._console.write(
                f"  {status_icon}  RAPPORT D'ORGANISATION — MediaFlow PRO", "section"
            )
            self._console.write(f"{sep_line}", "section")
            self._console.write(f"  📅  Date          : {now}", "info")
            self._console.write(f"  📁  Dossier       : {self._selected_folder}", "info")
            self._console.write(
                f"  ⚙   Mode          : {mode_label}",
                "warn" if dry_run else "info",
            )
            self._console.write(f"{sep_line}", "section")
            self._console.write(f"  📦  Fichiers déplacés   : {moved}", "success")
            self._console.write(f"  ⊘   Fichiers ignorés    : {skipped}", "ffmpeg")
            self._console.write(
                f"  ✖   Erreurs             : {errors}",
                "error" if errors > 0 else "ffmpeg",
            )
            self._console.write(f"  📊  Total analysés      : {len(files)}", "info")
            self._console.write(f"{sep_line}", "section")

            if errors == 0 and moved > 0:
                self._console.write(
                    "  ✅  Opération accomplie avec succès. Aucune erreur détectée.",
                    "success",
                )
                self.after(0, lambda m=moved, e=errors: messagebox.showinfo(
                    "✅  Organisation terminée",
                    f"Opération accomplie avec succès !\n\n"
                    f"📦  Fichiers déplacés : {m}\n"
                    f"✖   Erreurs           : {e}\n\n"
                    f"Consultez la console pour le rapport complet.",
                ))
            elif errors == 0 and moved == 0:
                self._console.write(
                    "  ℹ   Aucun fichier reconnu n'a été trouvé dans ce dossier.",
                    "warn",
                )
            else:
                self._console.write(
                    f"  ⚠   Opération terminée avec {errors} erreur(s). "
                    "Consultez les détails ci-dessus.",
                    "warn",
                )

            if dry_run:
                self._console.write(
                    "  💡  Mode aperçu : décochez l'option pour appliquer les changements.",
                    "warn",
                )

            self._console.write(f"{sep_line}\n", "section")

        except Exception as ex:
            self._console.write(f"✖ Erreur critique organisation : {ex}", "error")


# ─────────────────────────────────────────────────────────────────
#  APPLICATION PRINCIPALE
# ─────────────────────────────────────────────────────────────────
class MediaFlowPro(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MediaFlow Automator PRO — Ultimate Edition")
        self.geometry("960x720")
        self.minsize(860, 620)
        self.configure(bg=T["bg"])

        self._q   = queue.Queue()
        self._mgr = TaskManager(
            log_cb      = self._enqueue_log,
            progress_cb = self._enqueue_progress,
            done_cb     = self._enqueue_done,
        )

        self._build()
        self.after(60, self._poll_queue)
        self._check_ffmpeg()

    def _build(self) -> None:
        self._build_header()
        self._build_tabs()
        self._build_console()

    def _build_header(self) -> None:
        h = tk.Frame(self, bg=T["panel"], height=58)
        h.pack(fill="x")
        h.pack_propagate(False)

        tk.Label(h, text="⬡ MediaFlow", font=F_TITLE,
                 fg=T["accent"], bg=T["panel"]).pack(side="left", padx=18, pady=10)
        tk.Label(h, text="Automator PRO", font=("Consolas", 14),
                 fg=T["purple"], bg=T["panel"]).pack(side="left", pady=12)
        tk.Label(h, text="Ultimate Edition", font=("Consolas", 10),
                 fg=T["teal"], bg=T["panel"]).pack(side="left", padx=(8, 0), pady=14)

        self._status = tk.Label(h, text="● Prêt", font=F_SM,
                                fg=T["green"], bg=T["panel"])
        self._status.pack(side="right", padx=18)

        self._clock = tk.Label(h, text="", font=F_SM,
                               fg=T["fg3"], bg=T["panel"])
        self._clock.pack(side="right", padx=8)
        self._tick()

    def _build_tabs(self) -> None:
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background=T["bg"], borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background=T["panel"], foreground=T["fg2"],
            padding=[16, 8], font=F_SM, borderwidth=0,
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", T["card"])],
            foreground=[("selected", T["accent"])],
        )

        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.pack(fill="both", expand=True, padx=10, pady=(8, 0))

        self._ffmpeg_tab = FFmpegTab(nb, console=None, mgr=self._mgr)
        self._org_tab    = OrganizerTab(nb, console=None)

        nb.add(self._ffmpeg_tab, text="  🎬  FFmpeg Automator  ")
        nb.add(self._org_tab,    text="  📁  Media Organizer  ")

    def _build_console(self) -> None:
        self._console = Console(self)
        self._console.pack(fill="x", padx=10, pady=(6, 10))
        self._console.config(height=160)
        # Injection de la console partagée dans les deux onglets
        self._ffmpeg_tab._console = self._console
        self._org_tab._console    = self._console

    # ── Thread → UI ────────────────────────────────────────────────

    def _enqueue_log(self, msg: str, level: str = "info") -> None:
        self._q.put(("log", msg, level))

    def _enqueue_progress(self, pct: int) -> None:
        self._q.put(("progress", pct))

    def _enqueue_done(self, done: int, errors: int, duration: str) -> None:
        """Appelé depuis le thread TaskManager avec les stats de fin."""
        self._q.put(("done", done, errors, duration))

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self._q.get_nowait()
                if item[0] == "log":
                    self._console.write(item[1], item[2])
                elif item[0] == "progress":
                    self._ffmpeg_tab.update_progress(item[1])
                elif item[0] == "done":
                    _, done, errors, duration = item
                    self._set_status("● Terminé", T["green"])
                    self._ffmpeg_tab.reset_queue_ui()
                    self._show_toast(done, errors, duration)
        except queue.Empty:
            pass
        except Exception as ex:
            print(f"[poll_queue error] {ex}")
        finally:
            self.after(60, self._poll_queue)

    def _set_status(self, text: str, color=None) -> None:
        self._status.config(text=text, fg=color or T["green"])

    def _tick(self) -> None:
        try:
            self._clock.config(text=datetime.now().strftime("%H:%M:%S"))
        except Exception:
            pass
        self.after(1000, self._tick)

    def _check_ffmpeg(self) -> None:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            out = subprocess.check_output(
                [FFMPEG, "-version"],
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
            ver = out.decode(errors="ignore").split("\n")[0]
            self._console.write(f"✔ {ver}", "success")
        except FileNotFoundError:
            self._console.write(
                "✖ FFmpeg introuvable — placez ffmpeg.exe ici ou ajoutez au PATH.",
                "error",
            )
            self._set_status("● FFmpeg manquant", T["red"])
        except Exception as ex:
            self._console.write(f"✖ Erreur vérification FFmpeg : {ex}", "error")

    # ── Toast notification ─────────────────────────────────────────

    def _show_toast(self, done: int, errors: int, duration: str) -> None:
        """
        Popup flottante affichée en bas à droite de la fenêtre principale
        après la fin de toutes les tâches FFmpeg.
        Se ferme automatiquement après 8 secondes ou sur clic du bouton ✕.
        """
        try:
            win = tk.Toplevel(self)
            win.overrideredirect(True)          # fenêtre sans barre de titre
            win.attributes("-topmost", True)    # toujours au premier plan

            TOAST_W = 330
            TOAST_H = 162

            # ── positionnement : coin bas-droit de la fenêtre principale ──
            self.update_idletasks()
            rx = self.winfo_x() + self.winfo_width()  - TOAST_W - 18
            ry = self.winfo_y() + self.winfo_height() - TOAST_H - 18
            win.geometry(f"{TOAST_W}x{TOAST_H}+{rx}+{ry}")
            win.configure(bg=T["card"])

            # couleur d'accent : vert si succès total, orange sinon
            accent = T["green"] if errors == 0 else T["orange"]

            # ── bordure colorée (1 px via frame extérieure) ───────────────
            outer = tk.Frame(win, bg=accent, padx=1, pady=1)
            outer.pack(fill="both", expand=True)

            inner = tk.Frame(outer, bg=T["card"])
            inner.pack(fill="both", expand=True)

            # ── en-tête ───────────────────────────────────────────────────
            hdr = tk.Frame(inner, bg=T["card"])
            hdr.pack(fill="x", padx=14, pady=(10, 0))

            icon_txt = "✔" if errors == 0 else "⚠"

            # cercle d'icône
            icon_frame = tk.Frame(hdr, bg=accent, width=24, height=24)
            icon_frame.pack(side="left")
            icon_frame.pack_propagate(False)
            tk.Label(
                icon_frame, text=icon_txt,
                fg=T["card"], bg=accent,
                font=("Consolas", 10, "bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")

            title_txt = "TRAITEMENT TERMINÉ" if errors == 0 else "TERMINÉ AVEC ERREURS"
            tk.Label(
                hdr, text=f"  {title_txt}",
                fg=accent, bg=T["card"],
                font=("Consolas", 10, "bold"),
            ).pack(side="left")

            # bouton fermeture
            close_btn = tk.Button(
                hdr, text="✕",
                command=win.destroy,
                fg=T["fg3"], bg=T["card"],
                activeforeground=T["fg"],
                activebackground=T["border"],
                relief="flat", bd=0,
                font=("Consolas", 10),
                cursor="hand2",
            )
            close_btn.pack(side="right")

            # ── séparateur ────────────────────────────────────────────────
            tk.Frame(inner, bg=T["border"], height=1).pack(
                fill="x", padx=14, pady=(8, 4)
            )

            # ── stats ─────────────────────────────────────────────────────
            stats = tk.Frame(inner, bg=T["card"])
            stats.pack(fill="x", padx=14)

            def _stat_row(label: str, value: str, val_color: str) -> None:
                row = tk.Frame(stats, bg=T["card"])
                row.pack(fill="x", pady=2)
                tk.Label(
                    row, text=label,
                    fg=T["fg2"], bg=T["card"],
                    font=("Consolas", 9), anchor="w",
                ).pack(side="left")
                tk.Label(
                    row, text=value,
                    fg=val_color, bg=T["card"],
                    font=("Consolas", 9, "bold"), anchor="e",
                ).pack(side="right")

            succeeded  = done - errors
            err_color  = T["red"] if errors > 0 else T["fg3"]

            _stat_row("Tâches réussies :", f"{succeeded} / {done}", accent)
            _stat_row("Erreurs :",         str(errors),              err_color)
            _stat_row("Durée totale :",    duration,                 T["accent"])

            # ── horodatage ────────────────────────────────────────────────
            ts = datetime.now().strftime("%H:%M:%S")
            tk.Label(
                inner, text=ts,
                fg=T["fg3"], bg=T["card"],
                font=("Consolas", 8), anchor="e",
            ).pack(fill="x", padx=14, pady=(4, 8))

            # ── fermeture automatique après 8 secondes ────────────────────
            win.after(8000, lambda: win.destroy() if win.winfo_exists() else None)

        except Exception as ex:
            # Ne jamais planter l'application si le toast échoue
            self._console.write(f"⚠ Toast non affiché : {ex}", "warn")


# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        app = MediaFlowPro()
        app.mainloop()
    except Exception as ex:
        import traceback
        print(f"[FATAL] {ex}")
        traceback.print_exc()
