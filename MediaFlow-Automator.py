"""
╔══════════════════════════════════════════════════════════╗
║         StartupKiller PRO  — v1.1  (bugfix)              ║
║         Windows Startup Process Manager                  ║
║         Python 3.10+ | subprocess | Tkinter              ║
╚══════════════════════════════════════════════════════════╝

BUGS CORRIGÉS v1.1 :
  BUG 1 — RAM parsing échouait silencieusement sur Windows FR/AR
           (tasklist renvoie "1 234 K" avec espace insécable \xa0)
           → re.sub(r"[^\d]", "", ...) : garde uniquement les chiffres

  BUG 2 — _fetch_worker lisait self._search_inp.get() depuis un thread
           → les valeurs sont maintenant capturées dans le main thread
             AVANT de lancer le thread (snapshot pattern)

  BUG 3 — ProgressBar placée avec .grid() sur row=0 en même temps que
           scroll_outer → écrasait la zone de cartes
           → déplacée dans un Frame dédié hors du grid principal

  BUG 4 — self._procs non initialisé → AttributeError sur _kill_selected
           → initialisé à [] dans __init__
"""

import subprocess
import threading
import queue
import re
import tkinter as tk
from tkinter import ttk, messagebox
import os
from datetime import datetime


# ─────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
#  HELPERS UI
# ─────────────────────────────────────────────
def mkbtn(parent, text, cmd, fg=None, bg=None, font=F_SM, **kw):
    fg = fg or T["accent"]
    bg = bg or T["panel"]
    return tk.Button(
        parent, text=text, command=cmd,
        fg=fg, bg=bg,
        activeforeground="#FFFFFF", activebackground=T["card"],
        relief="flat", bd=0, padx=10, pady=5,
        font=font, cursor="hand2",
        highlightthickness=1,
        highlightbackground=fg, highlightcolor=fg,
        **kw,
    )


def mklbl(parent, text, fg=None, font=F_SM, **kw):
    return tk.Label(
        parent, text=text,
        fg=fg or T["fg2"],
        bg=parent.cget("bg"),
        font=font, **kw,
    )


def mkinp(parent, default="", width=20):
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


# ─────────────────────────────────────────────
#  BARRE DE PROGRESSION  (Frame-based)
# ─────────────────────────────────────────────
class ProgressBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=parent.cget("bg"), **kw)
        self._track = tk.Frame(self, bg=T["border"], height=5)
        self._track.pack(fill="x")
        self._track.pack_propagate(False)
        self._fill = tk.Frame(self._track, bg=T["accent"], height=5)
        self._fill.place(x=0, y=0, relheight=1.0, relwidth=0.0)

    def set(self, pct: int):
        pct = max(0, min(100, pct))
        color = T["green"] if pct == 100 else T["accent"]
        self._fill.config(bg=color)
        self._fill.place(relwidth=pct / 100)


# ─────────────────────────────────────────────
#  CONSOLE
# ─────────────────────────────────────────────
class Console(tk.Frame):
    COLORS = {
        "info":    T["fg2"],
        "cmd":     T["accent"],
        "ok":      T["green"],
        "warn":    T["orange"],
        "error":   T["red"],
        "section": T["purple"],
        "muted":   T["fg3"],
    }

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=T["panel"], **kw)
        hdr = tk.Frame(self, bg=T["panel"])
        hdr.pack(fill="x")
        mklbl(hdr, "LOG", fg=T["fg3"]).pack(side="left", padx=10, pady=5)
        mkbtn(hdr, "Effacer", self.clear,
              fg=T["fg3"], bg=T["panel"]).pack(side="right", padx=6, pady=3)

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
#  CARTE PROCESSUS
# ─────────────────────────────────────────────
class ProcessCard(tk.Frame):
    def __init__(self, parent, proc: dict, kill_cb, **kw):
        super().__init__(
            parent, bg=T["card"],
            highlightthickness=1,
            highlightbackground=T["border"], **kw,
        )
        p = proc

        # ── En-tête ──
        hdr = tk.Frame(self, bg=T["card"])
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        mklbl(hdr, p["name"], fg=T["fg"], font=F_BOLD).pack(side="left")
        mklbl(hdr, f"  PID {p['pid']}", fg=T["fg3"],
              font=F_SM).pack(side="left")
        mkbtn(
            hdr, "⏹ Stop",
            # BUG FIX : capturer pid/name par défaut pour éviter closure tardive
            lambda pid=p["pid"], name=p["name"]: kill_cb(pid, name),
            fg=T["red"], bg=T["card"],
        ).pack(side="right")

        # ── Barre RAM (plus pertinente que CPU=0) ──
        ram   = p.get("ram_mb", 0)
        # Représenter la RAM sur une échelle de 0-2000 MB
        ratio = min(ram / 2000, 1.0)
        rcolor = (T["red"]    if ratio > 0.75
                  else T["orange"] if ratio > 0.40
                  else T["green"])

        bar_row = tk.Frame(self, bg=T["card"])
        bar_row.pack(fill="x", padx=12, pady=(0, 3))
        mklbl(bar_row, "RAM", fg=T["fg3"], font=F_SM).pack(side="left")
        mklbl(bar_row, f"{ram:.1f} MB", fg=rcolor,
              font=F_SM).pack(side="right")

        track = tk.Frame(self, bg=T["border"], height=5)
        track.pack(fill="x", padx=12, pady=(0, 6))
        track.pack_propagate(False)
        tk.Frame(track, bg=rcolor, height=5).place(
            relwidth=ratio, relheight=1)

        # ── Détails ──
        det = tk.Frame(self, bg=T["card"])
        det.pack(fill="x", padx=12, pady=(0, 10))
        for label_txt, val, col in [
            ("Statut", p.get("status", "running"), T["fg2"]),
            ("Type",   p.get("type",   "app"),     T["purple"]),
        ]:
            cf = tk.Frame(det, bg=T["card"])
            cf.pack(side="left", padx=(0, 24))
            mklbl(cf, label_txt, fg=T["fg3"], font=F_SM).pack(anchor="w")
            mklbl(cf, val,       fg=col,      font=F_BOLD).pack(anchor="w")


# ─────────────────────────────────────────────
#  MOTEUR  — subprocess pur, zéro psutil
# ─────────────────────────────────────────────
class ProcessManager:

    @staticmethod
    def list_processes(filter_name: str = "") -> list[dict]:
        """
        Parse la sortie de : tasklist /FO CSV /NH
        FIX BUG 1 : re.sub(r"[^\d]", "", ram_str)
                    → supprime TOUT sauf les chiffres
                    → fonctionne avec " K", "K", "\xa0K", espaces, virgules
                    → insensible à la langue Windows (FR, AR, EN…)
        """
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        results = []

        try:
            out = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"],
                stderr=subprocess.DEVNULL,
                encoding="utf-8", errors="ignore",
                creationflags=flags,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            return []
        except FileNotFoundError:
            return ProcessManager._list_unix()
        except Exception:
            return []

        for line in out.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            # ── Parsing CSV robuste ──────────────────
            # Format attendu : "nom.exe","pid","Console","0","ram K"
            parts = [p.strip('"') for p in line.split('","')]

            if len(parts) < 5:
                continue

            try:
                name    = parts[0].strip()
                pid_str = parts[1].strip()
                ram_str = parts[4].strip()

                if not pid_str.isdigit():
                    continue

                pid = int(pid_str)

                # ▶ FIX BUG 1 : extraction chiffres uniquement
                digits = re.sub(r"[^\d]", "", ram_str)
                if not digits:
                    continue
                ram_kb = int(digits)
                ram_mb = round(ram_kb / 1024, 1)

                # Filtre nom
                if filter_name and filter_name.lower() not in name.lower():
                    continue

                results.append({
                    "name":   name,
                    "pid":    pid,
                    "ram_mb": ram_mb,
                    "status": "running",
                    "type":   ProcessManager._classify(name),
                })

            except (ValueError, IndexError):
                continue

        return sorted(results, key=lambda x: x["ram_mb"], reverse=True)

    @staticmethod
    def kill(pid: int, name: str) -> tuple[bool, str]:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            r = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore",
                creationflags=flags, timeout=8,
            )
            if r.returncode == 0:
                return True, f"✔ {name} (PID {pid}) arrêté."
            err = (r.stderr or r.stdout or "erreur inconnue").strip()
            return False, f"✖ {name} : {err}"
        except subprocess.TimeoutExpired:
            return False, f"✖ {name} : timeout."
        except PermissionError:
            return False, f"✖ {name} : permission refusée."
        except FileNotFoundError:
            return False, "✖ taskkill introuvable (Windows requis)."
        except Exception as ex:
            return False, f"✖ {name} : {ex}"

    @staticmethod
    def _list_unix() -> list[dict]:
        """Fallback Linux/macOS."""
        try:
            out = subprocess.check_output(
                ["ps", "-eo", "pid,comm,rss"],
                encoding="utf-8", errors="ignore", timeout=10,
            )
            results = []
            for line in out.strip().splitlines()[1:]:   # skip header
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                try:
                    results.append({
                        "pid":    int(parts[0]),
                        "name":   parts[1],
                        "ram_mb": round(int(parts[2]) / 1024, 1),
                        "status": "running",
                        "type":   ProcessManager._classify(parts[1]),
                    })
                except ValueError:
                    continue
            return sorted(results, key=lambda x: x["ram_mb"], reverse=True)
        except Exception:
            return []

    _CATEGORIES = {
        "browser": ["chrome", "firefox", "msedge", "opera", "brave", "vivaldi", ],
        "media":   ["vlc", "spotify", "wmplayer", "itunes", "potplayer", "mpv", "video.ui", "mediaplayer" , "applicationframehost" ],
        "office":  ["winword", "excel", "powerpnt", "outlook", "onenote", "teams", "foxit","acrord32"],
        "system":  ["svchost", "csrss", "lsass", "winlogon", "smss",
                    "wininit", "services", "system", "registry"],
        "dev":     ["python", "node", "code", "pycharm", "git",
                    "cmd", "powershell", "windowsterminal"],
        "game":    ["steam", "epicgameslauncher", "battle.net",
                    "leagueoflegends", "riotclientservices"],
    }

    @classmethod
    def _classify(cls, name: str) -> str:
        n = name.lower().replace(".exe", "")
        for cat, keys in cls._CATEGORIES.items():
            if any(k in n for k in keys):
                return cat
        return "app"


# ─────────────────────────────────────────────
#  APPLICATION PRINCIPALE
# ─────────────────────────────────────────────
class StartupKillerApp(tk.Tk):

    SYSTEM_PROTECTED = {
        "system", "svchost.exe", "csrss.exe", "lsass.exe",
        "winlogon.exe", "smss.exe", "wininit.exe", "services.exe",
        "registry",
    }

    def __init__(self):
        super().__init__()
        self.title("StartupKiller PRO — Process Manager")
        self.geometry("980x720")
        self.minsize(820, 580)
        self.configure(bg=T["bg"])

        self._q      = queue.Queue()
        self._procs  = []          # FIX BUG 4 : initialisé ici

        self._build()
        self.after(60,  self._poll_queue)
        self.after(300, self._load_processes)

    # ── CONSTRUCTION ──────────────────────────
    def _build(self):
        self._header()
        self._toolbar()

        body = tk.PanedWindow(self, orient="horizontal",
                              bg=T["bg"], sashwidth=5)
        body.pack(fill="both", expand=True, padx=10, pady=(4, 0))

        left  = tk.Frame(body, bg=T["bg"], width=210)
        right = tk.Frame(body, bg=T["bg"])
        body.add(left,  minsize=190)
        body.add(right, minsize=520)

        self._sidebar(left)
        self._main_panel(right)
        self._footer()

    # ── HEADER ────────────────────────────────
    def _header(self):
        h = tk.Frame(self, bg=T["panel"], height=56)
        h.pack(fill="x")
        h.pack_propagate(False)

        tk.Label(h, text="⚡ StartupKiller",
                 font=F_TITLE, fg=T["accent"],
                 bg=T["panel"]).pack(side="left", padx=18, pady=10)
        tk.Label(h, text="PRO",
                 font=("Consolas", 14), fg=T["red"],
                 bg=T["panel"]).pack(side="left", pady=12)

        self._status_lbl = tk.Label(
            h, text="● Chargement…",
            font=F_SM, fg=T["orange"], bg=T["panel"])
        self._status_lbl.pack(side="right", padx=18)

        self._clock_lbl = tk.Label(
            h, text="", font=F_SM, fg=T["fg3"], bg=T["panel"])
        self._clock_lbl.pack(side="right", padx=8)
        self._tick()

    # ── TOOLBAR ───────────────────────────────
    def _toolbar(self):
        tb = tk.Frame(self, bg=T["bg"], pady=6)
        tb.pack(fill="x", padx=10)

        # Recherche
        mklbl(tb, "🔍", fg=T["fg3"]).pack(side="left", padx=(0, 4))
        self._search_inp = mkinp(tb, "", width=24)
        self._search_inp.pack(side="left", ipady=4)
        self._search_inp.bind("<Return>", lambda e: self._load_processes())

        mkbtn(tb, "Rechercher", self._load_processes,
              fg=T["accent"]).pack(side="left", padx=(6, 0))

        # Catégorie
        mklbl(tb, "  Catégorie :", fg=T["fg3"]).pack(side="left", padx=(12, 4))
        self._cat = tk.StringVar(value="Tous")
        cb = ttk.Combobox(
            tb, textvariable=self._cat,
            values=["Tous", "browser", "media", "office",
                    "dev", "game", "system", "app"],
            state="readonly", width=10, font=F_SM,
        )
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._load_processes())

        # Boutons droite
        mkbtn(tb, "⟳ Rafraîchir", self._load_processes,
              fg=T["green"]).pack(side="right", padx=(4, 0))
        mkbtn(tb, "⏹ Stopper affiché", self._kill_all_visible,
              fg=T["red"]).pack(side="right", padx=(4, 0))

    # ── SIDEBAR ───────────────────────────────
    def _sidebar(self, parent):
        # Stats
        sc = tk.Frame(parent, bg=T["card"],
                      highlightthickness=1,
                      highlightbackground=T["border"])
        sc.pack(fill="x", padx=6, pady=(0, 10))

        mklbl(sc, "PROCESSUS", fg=T["fg3"],
              font=F_SM).pack(anchor="w", padx=10, pady=(8, 0))
        self._count_lbl = tk.Label(
            sc, text="—", font=("Consolas", 26, "bold"),
            fg=T["accent"], bg=T["card"])
        self._count_lbl.pack(anchor="w", padx=10, pady=(0, 2))

        mklbl(sc, "RAM totale", fg=T["fg3"],
              font=F_SM).pack(anchor="w", padx=10)
        self._ram_lbl = tk.Label(
            sc, text="—", font=F_BOLD,
            fg=T["purple"], bg=T["card"])
        self._ram_lbl.pack(anchor="w", padx=10, pady=(0, 10))

        # Arrêt rapide
        mklbl(parent, "ARRÊT RAPIDE", fg=T["fg3"],
              font=F_SM).pack(anchor="w", padx=10, pady=(4, 4))

        for label_txt, cat, color in [
            ("🌐 Navigateurs",   "browser", T["accent"]),
            ("🎵 Médias",        "media",   T["purple"]),
            ("📄 Office",        "office",  T["orange"]),
            ("🎮 Jeux / Steam",  "game",    T["orange"]),
            ("🖥 Développement", "dev",     T["green"]),
        ]:
            mkbtn(
                parent, label_txt,
                lambda c=cat: self._kill_category(c),
                fg=color, bg=T["panel"],
            ).pack(fill="x", padx=6, pady=2, ipady=6)

        tk.Frame(parent, bg=T["bg"]).pack(fill="both", expand=True)

        # Avertissement
        w = tk.Frame(parent, bg=T["card"],
                     highlightthickness=1,
                     highlightbackground=T["red"])
        w.pack(fill="x", padx=6, pady=8)
        mklbl(w,
              "⚠ Ne pas arrêter\nles processus\nsystème\n(svchost, lsass…)",
              fg=T["orange"], font=F_SM).pack(padx=8, pady=8)

    # ── PANNEAU PRINCIPAL ─────────────────────
    def _main_panel(self, parent):
        """
        FIX BUG 3 :
          Layout corrigé avec pack() uniquement :
            1. ProgressBar  → pack(fill="x")     en haut
            2. Zone scroll  → pack(fill="both", expand=True)
            3. Console      → pack(fill="x")     en bas
          Plus de conflit grid/pack, plus de superposition.
        """
        # 1. Barre de progression en haut
        prog_frame = tk.Frame(parent, bg=T["bg"])
        prog_frame.pack(fill="x", pady=(0, 4))
        self._prog = ProgressBar(prog_frame)
        self._prog.pack(fill="x")

        # 2. Zone scrollable (expand=True pour prendre tout l'espace)
        scroll_outer = tk.Frame(parent, bg=T["bg"])
        scroll_outer.pack(fill="both", expand=True, pady=(0, 6))

        canvas = tk.Canvas(scroll_outer, bg=T["bg"], highlightthickness=0)
        sb = tk.Scrollbar(scroll_outer, orient="vertical",
                          command=canvas.yview,
                          bg=T["bg"], troughcolor=T["bg"])
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._cards_frame = tk.Frame(canvas, bg=T["bg"])
        self._win_id = canvas.create_window(
            (0, 0), window=self._cards_frame, anchor="nw")

        def _on_resize(e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(self._win_id, width=canvas.winfo_width())

        self._cards_frame.bind("<Configure>", _on_resize)
        canvas.bind("<Configure>", _on_resize)
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # 3. Console en bas (hauteur fixe)
        self._console = Console(parent)
        self._console.pack(fill="x", ipady=0)
        self._console.config(height=160)
        self._console.pack_propagate(False)

    # ── FOOTER ────────────────────────────────
    def _footer(self):
        f = tk.Frame(self, bg=T["panel"],
                     highlightthickness=1,
                     highlightbackground=T["border"])
        f.pack(fill="x", side="bottom")
        self._foot_lbl = mklbl(f, "● Prêt", fg=T["green"], font=F_SM)
        self._foot_lbl.pack(side="left", padx=12, pady=5)
        mklbl(f, "Windows 10/11  |  subprocess only  |  no psutil",
              fg=T["fg3"], font=F_SM).pack(side="right", padx=12, pady=5)

    # ── CHARGEMENT ────────────────────────────
    def _load_processes(self):
        self._set_status("● Chargement…", T["orange"])
        self._prog.set(20)

        # FIX BUG 2 : snapshot des valeurs UI dans le main thread
        #             AVANT de lancer le thread
        name_filter = self._search_inp.get().strip()
        cat_filter  = self._cat.get()

        threading.Thread(
            target=self._fetch_worker,
            args=(name_filter, cat_filter),
            daemon=True,
        ).start()

    def _fetch_worker(self, name_filter: str, cat_filter: str):
        """Thread séparé — ne touche JAMAIS à l'UI."""
        try:
            procs = ProcessManager.list_processes(name_filter)
            if cat_filter != "Tous":
                procs = [p for p in procs if p["type"] == cat_filter]
            self._q.put(("procs", procs))
        except Exception as ex:
            self._q.put(("log", f"✖ Erreur : {ex}", "error"))
            self._q.put(("procs", []))

    # ── RENDU DES CARTES ──────────────────────
    def _render_cards(self, procs: list):
        for w in self._cards_frame.winfo_children():
            w.destroy()

        self._procs = procs

        if not procs:
            mklbl(self._cards_frame,
                  "Aucun processus trouvé.",
                  fg=T["fg2"]).pack(pady=40)
            self._count_lbl.config(text="0")
            self._ram_lbl.config(text="0 MB")
            return

        for p in procs:
            ProcessCard(
                self._cards_frame, p,
                kill_cb=self._kill_one,
            ).pack(fill="x", pady=(0, 4), padx=2)

        total_ram = sum(p["ram_mb"] for p in procs)
        self._count_lbl.config(text=str(len(procs)))
        self._ram_lbl.config(
            text=f"{total_ram/1024:.1f} GB"
            if total_ram > 1024 else f"{total_ram:.0f} MB")

    # ── KILL ──────────────────────────────────
    def _kill_one(self, pid: int, name: str):
        if name.lower() in self.SYSTEM_PROTECTED:
            messagebox.showwarning(
                "Processus système",
                f"⚠ '{name}' est un processus système critique.\n"
                "L'arrêter peut déstabiliser Windows.")
            return
        if not messagebox.askyesno("Confirmer",
                                   f"Arrêter  {name}  (PID {pid}) ?"):
            return
        threading.Thread(
            target=self._kill_worker,
            args=(pid, name), daemon=True).start()

    def _kill_worker(self, pid: int, name: str):
        ok, msg = ProcessManager.kill(pid, name)
        self._q.put(("log", msg, "ok" if ok else "error"))
        if ok:
            self._q.put(("reload",))

    def _kill_all_visible(self):
        if not self._procs:
            self._console.write("⚠ Aucun processus affiché.", "warn")
            return
        safe = [p for p in self._procs
                if p["name"].lower() not in self.SYSTEM_PROTECTED]
        if not safe:
            self._console.write("⚠ Tous les processus visibles sont protégés.", "warn")
            return
        if not messagebox.askyesno(
                "Arrêt groupé",
                f"Arrêter {len(safe)} processus affichés ?\n"
                "Les processus système seront ignorés."):
            return
        threading.Thread(
            target=self._kill_many,
            args=(safe,), daemon=True).start()

    def _kill_many(self, procs: list):
        killed = 0
        for p in procs:
            ok, msg = ProcessManager.kill(p["pid"], p["name"])
            self._q.put(("log", msg, "ok" if ok else "error"))
            if ok:
                killed += 1
        self._q.put(("log",
                     f"── {killed}/{len(procs)} arrêtés. ──",
                     "section"))
        self._q.put(("reload",))

    def _kill_category(self, cat: str):
        targets = [p for p in self._procs
                   if p["type"] == cat
                   and p["name"].lower() not in self.SYSTEM_PROTECTED]
        if not targets:
            self._console.write(
                f"⚠ Aucun processus '{cat}' trouvé.", "warn")
            return
        if not messagebox.askyesno(
                "Arrêt catégorie",
                f"Arrêter tous les '{cat}' ({len(targets)}) ?"):
            return
        threading.Thread(
            target=self._kill_many,
            args=(targets,), daemon=True).start()

    # ── QUEUE POLLING ─────────────────────────
    def _poll_queue(self):
        try:
            while True:
                item = self._q.get_nowait()
                if item[0] == "procs":
                    self._render_cards(item[1])
                    self._prog.set(100)
                    n = len(item[1])
                    self._set_status(
                        f"● {n} processus", T["green"] if n else T["orange"])
                elif item[0] == "log":
                    self._console.write(item[1], item[2])
                elif item[0] == "reload":
                    self._load_processes()
        except queue.Empty:
            pass
        self.after(60, self._poll_queue)

    def _set_status(self, text, color=None):
        self._status_lbl.config(text=text, fg=color or T["green"])
        self._foot_lbl.config(text=text,   fg=color or T["green"])

    def _tick(self):
        self._clock_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick)


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = StartupKillerApp()
    app.mainloop()
