# Áudio → MIDI

Sistema em Python + Flask para transcrever áudio em ficheiros MIDI usando **Basic Pitch**.

- Funciona com qualquer instrumento, polifónico.
- No Windows usa ONNX por defeito (não precisa de TensorFlow para correr).
- Aceita **ficheiro local** ou **URL YouTube**.

## Instalação

```bash
cd "c:\Users\miguel.villamediana\OneDrive - IHS Towers\Área de Trabalho\NoteAI"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Executar

```bash
python app.py
```

Abre no browser: **http://127.0.0.1:5000**

1. Escolhe uma das opções de entrada:
   - carregar ficheiro de áudio (WAV, MP3, FLAC, OGG, M4A), ou
   - colar uma URL do YouTube.
2. Clica em **Transcrever e descarregar MIDI** e guarda o `.mid` gerado.
3. Após a transcrição, a interface mostra:
   - player do áudio original,
   - player de pré-escuta do MIDI,
   - botão para baixar o arquivo MIDI.

## Estrutura do projeto

```
NoteAI/
├── app.py                 # App Flask
├── requirements.txt
├── README.md
├── transcribe/
│   ├── __init__.py
│   └── basic_pitch_module.py   # Basic Pitch
└── templates/
    ├── base.html
    └── index.html
```

## Notas

- **Basic Pitch**: funciona logo após `pip install basic-pitch`.
- **Upload local**: máximo 100 MB por ficheiro.
- **YouTube URL**: o servidor descarrega o áudio temporariamente usando `yt-dlp`.
- **Pré-escuta**: os resultados ficam disponíveis por tempo limitado (limpeza automática de ficheiros temporários).
