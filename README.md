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

Em servidores (VPS, cloud), o YouTube pode bloquear com *"Sign in to confirm you're not a bot"*. A solução recomendada pela documentação do yt-dlp é **passar cookies** em ficheiro.

### Referência oficial
- [FAQ: How do I pass cookies to yt-dlp?](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [Extractors: Exporting YouTube cookies](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)

### Passos

1. **Exportar cookies** no teu PC (formato **Netscape**):
   - Usa uma extensão: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) (Chrome/Edge) ou [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) (Firefox).  
     *(Não uses "Get cookies.txt" sem "LOCALLY" — foi reportado como malware.)_
   - Abre **youtube.com** (faz login se quiseres), exporta só para **youtube.com** e guarda como `cookies.txt`.
   - O ficheiro deve estar em formato Netscape: a **primeira linha** tem de ser `# HTTP Cookie File` ou `# Netscape HTTP Cookie File`.
   - No **Linux** o ficheiro deve usar finais de linha **LF** (`\n`). Se exportares no Windows, converte para LF antes de enviar (ex.: no Notepad++ "Edit → EOL Conversion → Unix (LF)").

2. **Enviar** `cookies.txt` para o servidor (ex.: `/root/AIScoreTranscriber/cookies.txt`).

3. **Definir a variável de ambiente** e reiniciar a app:
   ```bash
   export YOUTUBE_COOKIES_FILE=/root/AIScoreTranscriber/cookies.txt
   # reinicia a app (nohup, systemd, etc.)
   ```
   Em systemd/PM2: adiciona `YOUTUBE_COOKIES_FILE=/caminho/para/cookies.txt` ao ambiente do processo.

4. **Manutenção**: Os cookies do YouTube expiram e são rotacionados. Se o erro de bot voltar, exporta de novo no browser e substitui o ficheiro no servidor.

**Nota:** Usar conta com yt-dlp pode levar a restrições na conta; usa com moderação ou uma conta secundária.

---

## Dependencies

| Purpose | Dependency |
|--------|------------|
| Transcription | `basic-pitch` (ONNX on Windows) |
| YouTube | `yt-dlp` |
| Audio conversion | `imageio-ffmpeg` (FFmpeg) |
| MIDI preview | `pretty_midi`, `soundfile` |
| Sheet music (browser) | VexFlow, Tone.js MIDI, jsPDF (CDN) |
