"""
App Flask: transcrição de áudio para MIDI com Basic Pitch.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import logging
import warnings
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file, render_template, flash, redirect, url_for, session
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

load_dotenv()

from transcribe.basic_pitch_module import transcribe_to_midi as basic_pitch_transcribe

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB
UPLOAD_FOLDER = Path(app.root_path) / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)
RESULTS_FOLDER = Path(app.root_path) / "results"
RESULTS_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {"wav", "mp3", "flac", "ogg", "m4a", "webm"}
YOUTUBE_DOMAINS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}

logger = logging.getLogger("noteai")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[AI Score Transcriber] %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

# Silencia logs muito verbosos de bibliotecas externas.
logging.getLogger().setLevel(logging.ERROR)
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("absl").setLevel(logging.ERROR)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=FutureWarning, module=r".*librosa.*")
warnings.filterwarnings("ignore", message=r".*urllib3.*doesn't match.*")
try:
    from requests.exceptions import RequestsDependencyWarning
    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except ImportError:
    pass


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS


def is_ajax_request() -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _safe_user_message(msg: str, generic: str = "An error occurred. Please try again.") -> str:
    """Retorna mensagem segura para a UI, sem tracebacks ou detalhes técnicos."""
    if not msg:
        return generic
    bad = ("Traceback", "File ", "runpy", "  File ", "  at ", ".py:", "Error:", "Exception:")
    if any(b in msg for b in bad) or len(msg) > 150:
        return generic
    return msg


def error_response(message: str, status_code: int = 400):
    safe_msg = _safe_user_message(message)
    if is_ajax_request():
        return jsonify({"error": safe_msg}), status_code
    flash(safe_msg, "error")
    return redirect(url_for("index"))


def is_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.netloc.lower()
    return host in YOUTUBE_DOMAINS or host.endswith(".youtube.com") or host.endswith(".youtu.be")


def cleanup_old_result_files(max_age_seconds: int = 60 * 60) -> None:
    now = time.time()
    for file_path in RESULTS_FOLDER.glob("*"):
        try:
            if file_path.is_file() and now - file_path.stat().st_mtime > max_age_seconds:
                file_path.unlink()
        except OSError:
            pass


def delete_result_assets(result_id: str | None) -> None:
    if not result_id:
        return
    patterns = (
        f"{result_id}_original.*",
        f"{result_id}_preview.wav",
        f"{result_id}_transcribed.mid",
        f"{result_id}_midi_preview.wav",
    )
    for pattern in patterns:
        for file_path in RESULTS_FOLDER.glob(pattern):
            try:
                file_path.unlink()
            except OSError:
                pass


def _synthesize_midi_polyphonic(midi_obj, fs: int = 44100):
    """
    Síntese customizada com envelope de sustain para que acordes (várias notas ao mesmo tempo)
    soem corretamente. O pretty_midi padrão usa decay muito rápido e notas simultâneas
    ficam abafadas.
    """
    import numpy as np
    from pretty_midi.utilities import note_number_to_hz

    if not midi_obj.instruments:
        return None

    all_ends = [n.end for inst in midi_obj.instruments for n in inst.notes]
    if not all_ends:
        return None
    end_time = max(all_ends)

    total_samples = int(fs * (end_time + 0.5))
    waveform = np.zeros(total_samples, dtype=np.float64)

    attack_s = 0.01
    release_s = 0.05

    for inst in midi_obj.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            start_samp = int(note.start * fs)
            end_samp = int(note.end * fs)
            if end_samp <= start_samp:
                continue
            n_samps = end_samp - start_samp
            freq = note_number_to_hz(note.pitch)
            t = np.arange(n_samps, dtype=np.float64) / fs
            osc = np.sin(2 * np.pi * freq * t)

            # Envelope tipo ADSR: attack rápido, sustain plano, release no fim
            env = np.ones(n_samps)
            attack_n = min(int(attack_s * fs), n_samps // 2)
            if attack_n > 0:
                env[:attack_n] = np.linspace(0, 1, attack_n)
            release_n = min(int(release_s * fs), n_samps // 2)
            if release_n > 0:
                env[-release_n:] = np.linspace(1, 0, release_n)

            vel = note.velocity / 127.0
            note_wave = osc * env * vel * 0.3
            waveform[start_samp:end_samp] += note_wave

    if np.abs(waveform).max() < 1e-9:
        return None
    waveform = waveform / np.abs(waveform).max() * 0.95
    return waveform.astype(np.float32)


def synthesize_midi_preview_wav(midi_bytes: bytes) -> Path | None:
    """Gera um WAV a partir do MIDI com síntese que preserva acordes (várias notas ao mesmo tempo)."""
    try:
        import numpy as np
        import pretty_midi
        import soundfile as sf
    except ImportError:
        logger.warning("MIDI synthesis dependencies not available.")
        return None

    midi_fd, midi_temp = tempfile.mkstemp(suffix=".mid", dir=str(UPLOAD_FOLDER))
    os.close(midi_fd)
    wav_fd, wav_temp = tempfile.mkstemp(suffix=".wav", dir=str(UPLOAD_FOLDER))
    os.close(wav_fd)
    midi_temp_path = Path(midi_temp)
    wav_temp_path = Path(wav_temp)

    try:
        midi_temp_path.write_bytes(midi_bytes)
        midi_obj = pretty_midi.PrettyMIDI(str(midi_temp_path))
        waveform = _synthesize_midi_polyphonic(midi_obj, fs=44100)
        if waveform is None or waveform.size == 0:
            return None
        sf.write(str(wav_temp_path), waveform, 44100, subtype="PCM_16")
        return wav_temp_path
    except Exception:
        wav_temp_path.unlink(missing_ok=True)
        return None
    finally:
        midi_temp_path.unlink(missing_ok=True)


def save_result_assets(
    audio_path: Path,
    preview_audio_path: Path,
    midi_bytes: bytes,
    midi_audio_preview_path: Path | None = None,
) -> tuple[str, Path, Path, Path, Path | None]:
    result_id = uuid.uuid4().hex
    source_suffix = audio_path.suffix.lower() or ".audio"
    original_copy_path = RESULTS_FOLDER / f"{result_id}_original{source_suffix}"
    preview_copy_path = RESULTS_FOLDER / f"{result_id}_preview.wav"
    midi_path = RESULTS_FOLDER / f"{result_id}_transcribed.mid"
    midi_audio_copy_path = RESULTS_FOLDER / f"{result_id}_midi_preview.wav"
    shutil.copy2(audio_path, original_copy_path)
    shutil.copy2(preview_audio_path, preview_copy_path)
    midi_path.write_bytes(midi_bytes)
    if midi_audio_preview_path and midi_audio_preview_path.exists():
        shutil.copy2(midi_audio_preview_path, midi_audio_copy_path)
        return result_id, original_copy_path, preview_copy_path, midi_path, midi_audio_copy_path
    return result_id, original_copy_path, preview_copy_path, midi_path, None


def get_audio_duration_seconds(audio_path: Path) -> float:
    """Retorna a duração em segundos do ficheiro de áudio."""
    try:
        import soundfile as sf
        info = sf.info(str(audio_path))
        return float(info.duration)
    except Exception:
        return 0.0


def convert_audio_to_wav(input_audio_path: Path) -> Path:
    """Converte qualquer input de áudio para WAV PCM, aumentando compatibilidade."""
    print(f"[WAV 1] A converter: {input_audio_path}")
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency to convert audio. Run: pip install imageio-ffmpeg"
        ) from exc

    fd, output_wav = tempfile.mkstemp(suffix=".wav", dir=str(UPLOAD_FOLDER))
    os.close(fd)
    output_wav_path = Path(output_wav)

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(input_audio_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "22050",
        "-ac",
        "1",
        str(output_wav_path),
    ]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0 or not output_wav_path.exists():
        if output_wav_path.exists():
            output_wav_path.unlink(missing_ok=True)
        print(f"[WAV 1] ERRO: ffmpeg returncode={result.returncode}")
        raise RuntimeError(
            "Could not process the audio from this file/link. Try another video or format."
        )
    print(f"[WAV 1] OK: {output_wav_path}")
    return output_wav_path


def download_youtube_audio(youtube_url: str) -> tuple[Path, str]:
    logger.info("A descarregar áudio do YouTube...")
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: install 'yt-dlp' to use YouTube URLs."
        ) from exc

    output_template = str(UPLOAD_FOLDER / f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # Reduz deteção de bot em servidores (YouTube pode pedir login)
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    # Cookies: em produção, o YouTube muitas vezes bloqueia sem sessão.
    # Definir YOUTUBE_COOKIES_FILE para o caminho de um ficheiro cookies.txt (Netscape).
    cookies_path = os.environ.get("YOUTUBE_COOKIES_FILE", "").strip()
    if cookies_path:
        cookie_file = Path(cookies_path)
        if cookie_file.is_file():
            ydl_opts["cookiefile"] = str(cookie_file)
            logger.info("A usar ficheiro de cookies para o YouTube.")
        else:
            logger.warning("YOUTUBE_COOKIES_FILE definido mas ficheiro não existe: %s", cookies_path)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        downloaded_path = ydl.prepare_filename(info)

    audio_path = Path(downloaded_path)
    if not audio_path.exists():
        raise RuntimeError("Failed to download audio from YouTube.")

    source_title = secure_filename(info.get("title", "")).strip("_-") or "youtube_audio"
    return audio_path, source_title


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/results/<result_id>/<kind>")
def result_media(result_id: str, kind: str):
    cleanup_old_result_files()
    if session.get("active_result_id") != result_id:
        return jsonify({"error": "Result not found for this session."}), 404
    download = request.args.get("download") == "1"

    if kind == "midi":
        target = RESULTS_FOLDER / f"{result_id}_transcribed.mid"
        if not target.exists():
            return jsonify({"error": "Result not found or expired."}), 404
        return send_file(
            str(target),
            mimetype="audio/midi",
            as_attachment=download,
            download_name=f"{result_id}_transcribed.mid",
        )

    if kind == "original":
        matches = list(RESULTS_FOLDER.glob(f"{result_id}_original.*"))
        if not matches:
            return jsonify({"error": "Result not found or expired."}), 404
        original_path = matches[0]
        return send_file(
            str(original_path),
            as_attachment=download,
            download_name=original_path.name,
        )

    if kind == "preview-audio":
        target = RESULTS_FOLDER / f"{result_id}_preview.wav"
        if not target.exists():
            return jsonify({"error": "Result not found or expired."}), 404
        return send_file(
            str(target),
            mimetype="audio/wav",
            as_attachment=download,
            download_name=f"{result_id}_preview.wav",
        )

    if kind == "midi-audio":
        target = RESULTS_FOLDER / f"{result_id}_midi_preview.wav"
        if not target.exists():
            return jsonify({"error": "MIDI audio preview not available for this result."}), 404
        return send_file(
            str(target),
            mimetype="audio/wav",
            as_attachment=download,
            download_name=f"{result_id}_midi_preview.wav",
        )

    return jsonify({"error": "Invalid media type."}), 400


@app.route("/results/reset", methods=["POST"])
def reset_result():
    cleanup_old_result_files()
    payload = request.get_json(silent=True) or {}
    requested_result_id = payload.get("result_id")
    active_result_id = session.get("active_result_id")
    target_result_id = active_result_id or requested_result_id

    if active_result_id and requested_result_id and requested_result_id != active_result_id:
        return jsonify({"error": "Invalid result for this session."}), 400

    delete_result_assets(target_result_id)
    session.pop("active_result_id", None)
    return jsonify({"ok": True})


@app.route("/transcribe", methods=["POST"])
def transcribe():
    print("[STEP 0] transcribe() iniciado")
    cleanup_old_result_files()
    file = request.files.get("audio")
    media_url = (request.form.get("youtube_url") or request.form.get("media_url") or "").strip()
    has_file = bool(file and file.filename)
    has_media_url = bool(media_url)
    print(f"[STEP 0] Input: has_file={has_file}, has_media_url={has_media_url}, media_url={media_url[:50] if media_url else ''}...")

    if has_file and has_media_url:
        return error_response("Choose only one option: local file or YouTube URL.")
    if not has_file and not has_media_url:
        return error_response("Upload an audio file or enter a YouTube URL.")

    audio_path = None
    transcription_audio_path = None
    midi_preview_audio_path = None
    base = "audio"

    try:
        if has_media_url:
            print("[STEP 1] A obter áudio da URL...")
            if is_youtube_url(media_url):
                print("[STEP 1a] YouTube detectado")
                audio_path, base = download_youtube_audio(media_url)
            else:
                return error_response("Invalid URL. Use a YouTube link.")
            print(f"[STEP 1] Download OK: audio_path={audio_path}, base={base}")
            logger.info("Download concluído: %s", base)
        else:
            print("[STEP 1] Ficheiro local")
            if not allowed_file(file.filename):
                return error_response(
                    f"Format not allowed. Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                )

            ext = file.filename.rsplit(".", 1)[-1].lower()
            safe_name = f"{uuid.uuid4().hex}.{ext}"
            audio_path = UPLOAD_FOLDER / safe_name
            file.save(str(audio_path))
            base = secure_filename(Path(file.filename).stem) or "audio"
            print(f"[STEP 1] Ficheiro guardado: {audio_path}")
            logger.info("Ficheiro recebido: %s", base)

        print("[STEP 2] A converter áudio para WAV...")
        logger.info("A converter áudio para WAV...")
        transcription_audio_path = convert_audio_to_wav(audio_path)
        print(f"[STEP 2] WAV OK: {transcription_audio_path}")

        print("[STEP 3] A transcrever para MIDI (Basic Pitch)...")
        logger.info("A transcrever para MIDI...")
        midi_bytes, note_events, time_sig, bpm = basic_pitch_transcribe(str(transcription_audio_path))
        print(f"[STEP 3] Basic Pitch OK: {len(midi_bytes)} bytes, {len(note_events)} notas")

        print("[STEP 4] A sintetizar preview MIDI...")
        midi_preview_audio_path = synthesize_midi_preview_wav(midi_bytes)
        print(f"[STEP 4] Síntese OK: {midi_preview_audio_path}")
        midi_filename = f"{base}_transcribed.mid"
        print(f"[STEP 5] A guardar resultados...")
        logger.info("Transcrição concluída: %s", midi_filename)

        if is_ajax_request():
            previous_result_id = session.get("active_result_id")
            if previous_result_id:
                delete_result_assets(previous_result_id)

            result_id, _, _, _, midi_audio_asset_path = save_result_assets(
                audio_path,
                transcription_audio_path,
                midi_bytes,
                midi_preview_audio_path,
            )
            session["active_result_id"] = result_id
            audio_duration = get_audio_duration_seconds(transcription_audio_path)
            payload = {
                "result_id": result_id,
                "original_audio_url": url_for("result_media", result_id=result_id, kind="preview-audio"),
                "midi_preview_url": url_for("result_media", result_id=result_id, kind="midi"),
                "midi_download_url": url_for("result_media", result_id=result_id, kind="midi", download=1),
                "original_download_url": url_for("result_media", result_id=result_id, kind="original", download=1),
                "midi_filename": midi_filename,
                "note_events": note_events,
                "note_events_total": len(note_events),
                "note_events_truncated": False,
                "time_signature": {"numerator": time_sig[0], "denominator": time_sig[1]},
                "bpm": bpm,
                "audio_duration": audio_duration,
                "expires_in_seconds": 3600,
            }
            if midi_audio_asset_path:
                payload["midi_audio_url"] = url_for("result_media", result_id=result_id, kind="midi-audio")
            print("[STEP 5] Concluído com sucesso!")
            return jsonify(payload)

        return send_file(
            path_or_file=BytesIO(midi_bytes),
            mimetype="audio/midi",
            as_attachment=True,
            download_name=midi_filename,
        )
    except RuntimeError as e:
        safe = _safe_user_message(str(e))
        print(f"[ERRO] RuntimeError: {safe}")
        logger.warning("Falha previsível na transcrição: %s", str(e)[:200])
        return error_response(safe, status_code=500)
    except Exception as e:
        print(f"[ERRO] Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        logger.error("Erro inesperado na transcrição: %s", e, exc_info=True)
        return error_response(
            "Transcription error. Check the file and try again.",
            status_code=500,
        )
    finally:
        if audio_path and audio_path.exists():
            try:
                audio_path.unlink()
            except OSError:
                pass
        if transcription_audio_path and transcription_audio_path.exists():
            try:
                transcription_audio_path.unlink()
            except OSError:
                pass
        if midi_preview_audio_path and midi_preview_audio_path.exists():
            try:
                midi_preview_audio_path.unlink()
            except OSError:
                pass


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    del e
    max_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return error_response(f"File too large. Limit: {max_mb} MB.", status_code=413)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
