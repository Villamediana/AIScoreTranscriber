"""
Transcrição áudio -> MIDI usando Basic Pitch.
Funciona com qualquer instrumento, polifónico.
"""
import os
import tempfile
from typing import Optional


def _normalize_note_events(note_events) -> list[dict]:
    """Normaliza eventos de nota do Basic Pitch para dicionários simples."""
    normalized: list[dict] = []
    if not note_events:
        return normalized

    for evt in note_events:
        start_time = None
        end_time = None
        pitch = None
        confidence = None

        if isinstance(evt, dict):
            start_time = evt.get("start_time", evt.get("start"))
            end_time = evt.get("end_time", evt.get("end"))
            pitch = evt.get("pitch", evt.get("midi"))
            confidence = evt.get("confidence", evt.get("amplitude", evt.get("velocity")))
        elif isinstance(evt, (list, tuple)):
            if len(evt) > 0:
                start_time = evt[0]
            if len(evt) > 1:
                end_time = evt[1]
            if len(evt) > 2:
                pitch = evt[2]
            if len(evt) > 3:
                confidence = evt[3]
        else:
            start_time = getattr(evt, "start_time", getattr(evt, "start", None))
            end_time = getattr(evt, "end_time", getattr(evt, "end", None))
            pitch = getattr(evt, "pitch", getattr(evt, "midi", None))
            confidence = getattr(
                evt, "confidence", getattr(evt, "amplitude", getattr(evt, "velocity", None))
            )

        if start_time is None or end_time is None or pitch is None:
            continue

        normalized.append(
            {
                "start_time": float(start_time),
                "end_time": float(end_time),
                "pitch": int(pitch),
                "confidence": float(confidence) if confidence is not None else None,
            }
        )

    return normalized


def _get_bpm_from_midi(midi_data) -> Optional[float]:
    """Extrai BPM do PrettyMIDI. Retorna o primeiro tempo ou None."""
    try:
        times, tempi = midi_data.get_tempo_changes()
        if tempi is not None and len(tempi) > 0:
            bpm = float(tempi[0])
            if 20 <= bpm <= 300:
                return round(bpm)
    except (AttributeError, TypeError, IndexError):
        pass
    return None


def _get_time_sig_from_midi(midi_data) -> Optional[tuple[int, int]]:
    """Extrai time signature do PrettyMIDI. Retorna (numerator, denominator) ou None."""
    try:
        changes = getattr(midi_data, "time_signature_changes", None)
        if not changes:
            return None
        # Usar o primeiro time signature (início da peça)
        ts = changes[0]
        num = int(getattr(ts, "numerator", 4))
        denom = int(getattr(ts, "denominator", 4))
        if num < 1 or num > 16 or denom not in (1, 2, 4, 8, 16):
            return None
        return (num, denom)
    except (IndexError, TypeError, AttributeError):
        return None


def _estimate_bpm(note_events: list[dict]) -> float:
    """Estima BPM a partir dos intervalos entre onsets."""
    if not note_events:
        return 120.0
    onsets = sorted([float(e["start_time"]) for e in note_events])
    diffs = []
    for i in range(1, min(len(onsets), 100)):
        d = onsets[i] - onsets[i - 1]
        if 0.05 < d < 2.0:
            diffs.append(d)
    if not diffs:
        return 120.0
    diffs.sort()
    med = diffs[len(diffs) // 2]
    bpm = 60.0 / med
    return max(40.0, min(240.0, bpm))


def _infer_time_signature(note_events: list[dict]) -> tuple[int, int]:
    """
    Infere o time signature mais plausível quando o MIDI não o tem.
    Tenta 4/4, 3/4, 2/4, 6/8 e escolhe o que melhor alinha os onsets aos tempos fortes.
    """
    if not note_events:
        return (4, 4)
    bpm = _estimate_bpm(note_events)
    beat_sec = 60.0 / bpm
    onsets = sorted([float(e["start_time"]) for e in note_events])
    if not onsets:
        return (4, 4)
    duration = max(onsets) - min(onsets)
    if duration < 0.5:
        return (4, 4)
    candidates = [
        (4, 4, 4),
        (3, 4, 3),
        (2, 4, 2),
        (6, 8, 3),
    ]
    best_score = -1.0
    best = (4, 4)
    tolerance = 0.1
    for num, denom, beats_per_measure in candidates:
        measure_sec = beat_sec * beats_per_measure
        if measure_sec < 0.1:
            continue
        on_beat = 0
        for t in onsets:
            pos_in_measure = (t % measure_sec) / measure_sec if measure_sec > 0 else 0
            for b in range(beats_per_measure + 1):
                beat_frac = b / beats_per_measure
                if abs(pos_in_measure - beat_frac) < tolerance:
                    on_beat += 1
                    break
        score = on_beat / len(onsets) if onsets else 0
        if score > best_score:
            best_score = score
            best = (num, denom)
    return best


def transcribe_to_midi(audio_path: str, output_midi_path: str | None = None) -> tuple[bytes, list[dict], tuple[int, int], Optional[float]]:
    """
    Transcreve um ficheiro de áudio para MIDI usando Basic Pitch.

    Args:
        audio_path: Caminho do ficheiro de áudio (wav, mp3, flac, etc.)
        output_midi_path: Opcional. Se dado, grava o MIDI neste caminho.

    Returns:
        Tuplo: (conteúdo binário do MIDI, eventos de nota, time signature (num, denom), bpm ou None).
    """
    from basic_pitch.inference import predict
    import pretty_midi

    _, midi_data, note_events = predict(audio_path)

    if midi_data is None or len(midi_data.instruments) == 0:
        # Criar MIDI vazio se não houver notas
        midi_data = pretty_midi.PrettyMIDI()
        midi_data.instruments.append(pretty_midi.Instrument(0))

    if output_midi_path:
        midi_data.write(output_midi_path)

    normalized = _normalize_note_events(note_events)
    time_sig = _get_time_sig_from_midi(midi_data)
    if time_sig is None:
        time_sig = _infer_time_signature(normalized)

    bpm = _get_bpm_from_midi(midi_data)
    if bpm is None:
        bpm = _estimate_bpm(normalized)

    fd, temp_midi_path = tempfile.mkstemp(suffix=".midi")
    os.close(fd)
    try:
        midi_data.write(temp_midi_path)
        with open(temp_midi_path, "rb") as f:
            return f.read(), normalized, time_sig, bpm
    finally:
        if os.path.exists(temp_midi_path):
            os.unlink(temp_midi_path)
