# AI Score Transcriber

Python + Flask app that transcribes audio to MIDI files using **Basic Pitch**.

- Works with any instrument, **polyphonic**.
- On Windows uses **ONNX** by default (no TensorFlow required).
- Accepts **local file** (WAV, MP3, FLAC, OGG, M4A, WEBM) or **YouTube URL**.

## Features

### Audio input
- **Local upload**: audio file up to 100 MB (WAV, MP3, FLAC, OGG, M4A, WEBM).
- **YouTube URL**: the server downloads the audio temporarily with `yt-dlp`.
- Automatic conversion to WAV (22,050 Hz, mono) for Basic Pitch compatibility.

### Transcription
- Audio → MIDI transcription with **Basic Pitch** (notes, start/end, confidence).
- **BPM** and **time signature** detection from the generated MIDI.
- `.mid` file generation for download.

### After transcription
- **Piano view (waterfall)**: roll visualization of transcribed notes.
- **Sheet view**: score rendered with **VexFlow**; time signature selection (numerator/denominator).
- **Note data**: expandable panel with event table (start, end, MIDI note, duration, etc.).
- **Playback**:
  - Original audio player and MIDI preview (polyphonic synthesis with sustain).
  - Progress bar and time (play/pause, seek).
  - Separate **volume** controls for original audio and MIDI preview.
  - **BPM** adjustment (numeric field and +/− buttons) for sync.
- **Download**: button to download the MIDI; option to download the result’s original audio.
- **Reset**: clears the current result and returns to the initial state.
- Automatic cleanup of temporary files (results expire after 1 hour).

## Installation

```bash
cd "c:\Users\miguel.villamediana\OneDrive - IHS Towers\Área de Trabalho\NoteAIs"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Open in browser: **http://127.0.0.1:5000**

### Usage flow

1. Choose an input: upload an audio file or paste a YouTube URL.
2. Click **Transcribe**.
3. After transcription:
   - Switch between **Piano** and **Sheet** views.
   - Use the **Note data** table for per-event details.
   - Use the players and volume/BPM controls to listen and compare.
   - Download the MIDI file when you want.

## Project structure

```
NoteAIs/   (AI Score Transcriber)
├── app.py                 # Flask app, routes, audio conversion, MIDI synthesis
├── requirements.txt
├── README.md
├── transcribe/
│   ├── __init__.py
│   └── basic_pitch_module.py   # Basic Pitch, note normalization, BPM/time signature
└── templates/
    ├── base.html          # Base layout, logo, "What is it" modal
    └── index.html         # Form, Piano/Sheet views, players, note table
```

## Dependencies and notes

- **Basic Pitch**: works after `pip install basic-pitch` (ONNX on Windows).
- **YouTube**: requires `yt-dlp` for YouTube URLs.
- **Audio conversion**: uses `imageio-ffmpeg` (FFmpeg) for WAV.
- **MIDI preview**: uses `pretty_midi` and `soundfile` for synthesis; sheet view uses **VexFlow** (CDN) and **Tone.js MIDI** (CDN).
- **Session**: the active result is tied to the session; files in `results/` are removed automatically after 1 hour.
