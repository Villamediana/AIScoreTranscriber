"""
Transcrição áudio -> MIDI usando Basic Pitch (Spotify).
Funciona com qualquer instrumento, polifónico.
"""
import os
import tempfile


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


def transcribe_to_midi(audio_path: str, output_midi_path: str | None = None) -> tuple[bytes, list[dict]]:
    """
    Transcreve um ficheiro de áudio para MIDI usando Basic Pitch.

    Args:
        audio_path: Caminho do ficheiro de áudio (wav, mp3, flac, etc.)
        output_midi_path: Opcional. Se dado, grava o MIDI neste caminho.

    Returns:
        Tuplo contendo: conteúdo binário do MIDI e eventos de nota.
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

    fd, temp_midi_path = tempfile.mkstemp(suffix=".midi")
    os.close(fd)
    try:
        midi_data.write(temp_midi_path)
        with open(temp_midi_path, "rb") as f:
            return f.read(), _normalize_note_events(note_events)
    finally:
        if os.path.exists(temp_midi_path):
            os.unlink(temp_midi_path)
