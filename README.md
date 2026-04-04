# 🎬 MediaFlow Automator PRO

> Advanced Python Automation Tool for Video & Audio Processing using FFmpeg

---

## 🚀 Overview

**MediaFlow Automator PRO** is a desktop application built with Python that allows you to automate video and audio processing tasks بسهولة وبدون تدخل يدوي.


📸 Preview 🖼️ Interface

<img width="880" height="711" alt="Capture" src="https://github.com/user-attachments/assets/16631bd0-2de0-44c7-ad78-d56f438e0a3f" />


The tool provides a clean GUI (Tkinter-based) to:

* Cut videos with custom timing
* Extract audio from video files
* Compress videos efficiently
* Execute multiple tasks in a queue system

---

🎥 Demo (How it works)



![Animation4](https://github.com/user-attachments/assets/b6dae06b-d3a1-4aab-b5be-b8cc8e3421f3)





## ✨ Features

* 🎯 **Custom Video Cutting**

  * Choose start time and duration manually

* 🎧 **Audio Extraction**

  * Convert video to high-quality MP3

* 📉 **Video Compression**

  * Reduce size using H.264 codec

* ⚙️ **Task Queue System**

  * Add multiple operations and process them automatically

* 🔁 **Multithreading**

  * Smooth UI without freezing

* 📊 **Progress Tracking**

  * Visual progress bar

* 🧾 **Real-time Logs**

  * Monitor FFmpeg execution output

---

## 🖥️ User Interface

Simple and clean interface built with `tkinter`:

* File selection input
* Cut settings panel (Start / Duration)
* Action buttons
* Progress bar
* Logs console

---

## 📦 Requirements

* Python 3.8+
* FFmpeg (must be installed and added to PATH)

### 🔧 Install FFmpeg

1. Download from: https://ffmpeg.org/download.html
2. Extract الملفات
3. Add `bin` folder to system PATH

Verify installation:

```bash
ffmpeg -version
```

---

## ▶️ How to Run

```bash
python main.py
```

---

## 🧪 Usage

### 1. Select a video file

Click **"Select File"**

### 2. Choose operation

#### ✂️ Cut Video

* Enter:

  * Start Time → `HH:MM:SS`
  * Duration → `HH:MM:SS`

#### 🎧 Extract Audio

* Converts `.mp4` → `.mp3`

#### 📉 Compress Video

* Reduces size using CRF 28

### 3. Start Processing

Click **"Start Processing"**

---

## 🧠 How It Works

* Uses `subprocess` to run FFmpeg commands
* Tasks are stored in a queue
* Executed in a separate thread
* Logs are streamed in real-time

---

## 📁 Output Files

Generated files are saved in the same directory as the input file:

| Operation      | Output Example       |
| -------------- | -------------------- |
| Cut Video      | video_cut.mp4        |
| Extract Audio  | video.mp3            |
| Compress Video | video_compressed.mp4 |

---

## ⚠️ Notes

* Make sure FFmpeg is correctly installed
* File formats supported depend on FFmpeg
* Large files may take time depending on system performance

---

## 🔮 Future Improvements

* 🎬 Video preview before cutting
* 🎛️ Advanced encoding settings
* 🎨 Modern UI (Dark Mode)
* 📦 Export as `.exe`
* 📊 Real FFmpeg progress parsing

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first.

---

## 📄 License

This project is open-source and free to use.

---

## 👨‍💻 Author

Developed by a Python Automation Developer 🚀

---

## ⭐ Support

If you like this project, consider giving it a **star ⭐ on GitHub**!
