# AI Score Transcriber

Web app that turns **audio into MIDI and sheet music** using the open source library [Basic Pitch](https://github.com/spotify/basic-pitch). Upload a file or paste a YouTube link → **piano roll**, **sheet music** (PDF downloadable), **playback**, and **MIDI** download.

---

## About

It's often hard to find piano scores for specific pieces. **AI Score Transcriber** generates both a MIDI file and a readable piano score (partitura) from any audio—e.g. a YouTube performance—so you can practice with a visual score without needing the official sheet music. Works with any instrument (polyphonic). On Windows it uses ONNX (no TensorFlow required).

---

## Features

| Area | Description |
|------|-------------|
| **Input** | Local file (WAV, MP3, FLAC, OGG, M4A, WEBM, up to 100 MB) or YouTube URL. Audio is converted to WAV (22,050 Hz, mono) for processing. |
| **Transcription** | Basic Pitch → MIDI with notes, BPM, and time signature. Same data drives the on-screen score. |
| **Views** | **Piano roll** (waterfall) and **Sheet** (full score with VexFlow). Time signature and BPM adjustable. **Note data** panel with event table. |
| **Playback** | Original audio + MIDI preview (polyphonic synthesis). Volume and BPM controls, seek bar. |
| **Export** | Download **MIDI**, **score as PDF** (from Sheet view), or original audio. Results expire after 1 hour (session-based). |

---

## Quick start

**1. Clone the repo**

```bash
git clone https://github.com/Villamediana/AIScoreTranscriber
cd AIScoreTranscriber
```

**2. Install**

Requires **Python 3.10**. Create the venv with Python 3.10 explicitly:

- **Windows:** `py -3.10 -m venv venv`
- **Linux/macOS:** `python3.10 -m venv venv`

```bash
py -3.10 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

*(On Linux/macOS use `source venv/bin/activate` instead of `venv\Scripts\activate`.)*

**3. Run**

```bash
python app.py
```

Open **http://127.0.0.1:5000**

**4. Use**

1. Upload an audio file or paste a YouTube URL.
2. Click **Transcribe**.
3. Switch between **Piano** and **Sheet** views; use **Note data** for details; adjust volume/BPM; download **MIDI** or **PDF** (Sheet view).

---

## Project structure

```
NoteAIs/
├── app.py                    # Flask app, routes, audio conversion, MIDI synthesis
├── requirements.txt
├── README.md
├── transcribe/
│   ├── __init__.py
│   └── basic_pitch_module.py  # Basic Pitch, note normalization, BPM/time signature
└── templates/
    ├── base.html              # Layout, logo, about modal
    └── index.html             # Form, Piano/Sheet views, players, note table, PDF export
```

---

## Production: YouTube em servidor

Em servidores (VPS, cloud), o YouTube pode bloquear descarregamentos com *"Sign in to confirm you're not a bot"*. Para contornar:

1. **Exportar cookies** do YouTube no teu browser (formato Netscape):
   - Extensão [Get cookies.txt LOCALLY](https://github.com/rotemdan/ExportCookies) (Chrome/Edge) ou [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) (Firefox).
   - Abre youtube.com, faz login se precisar, e exporta para `cookies.txt`.

2. **Enviar o ficheiro** para o servidor (ex.: `/root/AIScoreTranscriber/cookies.txt`).

3. **Definir a variável de ambiente** antes de correr a app:
   ```bash
   export YOUTUBE_COOKIES_FILE=/root/AIScoreTranscriber/cookies.txt
   python app.py
   ```
   Ou no systemd/PM2: coloca `YOUTUBE_COOKIES_FILE=/caminho/para/cookies.txt` no ambiente do processo.

Os cookies expiram; se voltar a dar erro de bot, exporta de novo e substitui o ficheiro.

---

## Dependencies

| Purpose | Dependency |
|--------|------------|
| Transcription | `basic-pitch` (ONNX on Windows) |
| YouTube | `yt-dlp` |
| Audio conversion | `imageio-ffmpeg` (FFmpeg) |
| MIDI preview | `pretty_midi`, `soundfile` |
| Sheet music (browser) | VexFlow, Tone.js MIDI, jsPDF (CDN) |
