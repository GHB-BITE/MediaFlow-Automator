# =============================
# MediaFlow Automator PRO (FINAL VERSION)
# =============================

import subprocess
import threading
import queue
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import sys

# =============================
# FFmpeg Path (PRO)
# =============================

def get_ffmpeg_path():
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, "ffmpeg.exe")

FFMPEG_PATH = get_ffmpeg_path()

# =============================
# FFmpeg Runner
# =============================

def run_ffmpeg(command, log_callback=None):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    for line in process.stderr:
        if log_callback:
            log_callback(line)

    process.wait()

# =============================
# Task System
# =============================

class Task:
    def __init__(self, name, command):
        self.name = name
        self.command = command

class TaskManager:
    def __init__(self, log_callback, progress_callback):
        self.tasks = queue.Queue()
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.running = False

    def add_task(self, task):
        self.tasks.put(task)
        self.log_callback(f"[+] Added: {task.name}\n")

    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        total = self.tasks.qsize()
        done = 0

        while not self.tasks.empty():
            task = self.tasks.get()
            self.log_callback(f"[▶] Running: {task.name}\n")

            run_ffmpeg(task.command, self.log_callback)

            done += 1
            progress = int((done / total) * 100)
            self.progress_callback(progress)

        self.running = False
        self.log_callback("\n[✓] All tasks completed\n")

# =============================
# GUI
# =============================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("MediaFlow PRO")
        self.root.geometry("750x550")

        self.task_manager = TaskManager(self.log, self.update_progress)

        # File input
        self.file_entry = tk.Entry(root, width=70)
        self.file_entry.pack(pady=10)

        tk.Button(root, text="Select File", command=self.select_file).pack()

        # CUT SETTINGS
        cut_frame = tk.LabelFrame(root, text="Cut Settings", padx=10, pady=10)
        cut_frame.pack(pady=10)

        tk.Label(cut_frame, text="Start Time (HH:MM:SS)").grid(row=0, column=0)
        self.start_entry = tk.Entry(cut_frame)
        self.start_entry.insert(0, "00:00:00")
        self.start_entry.grid(row=0, column=1)

        tk.Label(cut_frame, text="Duration (HH:MM:SS)").grid(row=1, column=0)
        self.duration_entry = tk.Entry(cut_frame)
        self.duration_entry.insert(0, "00:00:10")
        self.duration_entry.grid(row=1, column=1)

        # BUTTONS
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Cut Video", command=self.cut_video).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Extract Audio", command=self.extract_audio).grid(row=0, column=1, padx=5)
        tk.Button(btn_frame, text="Compress Video", command=self.compress_video).grid(row=0, column=2, padx=5)

        # Progress
        self.progress = ttk.Progressbar(root, length=500)
        self.progress.pack(pady=10)

        # Logs
        self.log_box = tk.Text(root, height=15)
        self.log_box.pack(fill="both", padx=10, pady=10)

        tk.Button(root, text="Start Processing", command=self.task_manager.start).pack()

    # =============================
    # Functions
    # =============================

    def select_file(self):
        file = filedialog.askopenfilename()
        self.file_entry.delete(0, tk.END)
        self.file_entry.insert(0, file)

    def log(self, message):
        self.log_box.insert(tk.END, message)
        self.log_box.see(tk.END)

    def update_progress(self, value):
        self.progress['value'] = value

    # =============================
    # TASKS
    # =============================

    def cut_video(self):
        file = self.file_entry.get()
        start = self.start_entry.get()
        duration = self.duration_entry.get()

        if not file:
            messagebox.showerror("Error", "Select a file first")
            return

        output = file.replace(".mp4", "_cut.mp4")

        command = [
            FFMPEG_PATH,
            "-i", file,
            "-ss", start,
            "-t", duration,
            "-c", "copy",
            output
        ]

        self.task_manager.add_task(Task("Custom Cut", command))

    def extract_audio(self):
        file = self.file_entry.get()

        if not file:
            messagebox.showerror("Error", "Select a file first")
            return

        output = file.replace(".mp4", ".mp3")

        command = [
            FFMPEG_PATH,
            "-i", file,
            "-q:a", "0",
            "-map", "a",
            output
        ]

        self.task_manager.add_task(Task("Extract Audio", command))

    def compress_video(self):
        file = self.file_entry.get()

        if not file:
            messagebox.showerror("Error", "Select a file first")
            return

        output = file.replace(".mp4", "_compressed.mp4")

        command = [
            FFMPEG_PATH,
            "-i", file,
            "-vcodec", "libx264",
            "-crf", "28",
            output
        ]

        self.task_manager.add_task(Task("Compress Video", command))

# =============================
# MAIN
# =============================

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
