import os
import sys
import uuid
import time
import shutil
import tempfile
import subprocess
from pathlib import Path

import gradio as gr


APP_NAME = "Minus Maker"
PORT = int(os.environ.get("PORT", "7860"))
BASE_DIR = Path(os.environ.get("WORK_DIR", tempfile.gettempdir())) / "minus_maker_jobs"
BASE_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "80"))

MODES = {
    "Быстро": {
        "model": "htdemucs",
        "shifts": "1",
        "overlap": "0.25",
        "mp3": True,
        "desc": "Быстрее, качество нормальное."
    },
    "Качественно": {
        "model": "htdemucs_ft",
        "shifts": "2",
        "overlap": "0.50",
        "mp3": True,
        "desc": "Лучший баланс для Render."
    },
    "Супер качество": {
        "model": "htdemucs_ft",
        "shifts": "4",
        "overlap": "0.75",
        "mp3": False,
        "desc": "Чище, но дольше и требует больше RAM."
    },
}


HTML_CSS = """
<style>
body, .gradio-container {
  background: radial-gradient(circle at top, #1f2b58 0%, #090b12 45%, #05060a 100%) !important;
  color: #f4f7ff !important;
}
.gradio-container {
  max-width: 980px !important;
  margin: auto !important;
}
h1 {
  text-align: center;
  font-size: 42px !important;
  letter-spacing: -1px;
}
.main-card {
  border: 1px solid rgba(255,255,255,.14);
  border-radius: 26px;
  padding: 22px;
  background: rgba(255,255,255,.07);
  box-shadow: 0 24px 80px rgba(0,0,0,.35);
  backdrop-filter: blur(18px);
}
button.primary, button[variant="primary"] {
  border-radius: 16px !important;
  font-weight: 800 !important;
}
textarea, input {
  border-radius: 16px !important;
}
footer {display:none !important;}
</style>
"""


def cleanup_old_jobs(max_age_hours: int = 4) -> None:
    now = time.time()
    max_age = max_age_hours * 3600
    for item in BASE_DIR.iterdir():
        try:
            if item.is_dir() and now - item.stat().st_mtime > max_age:
                shutil.rmtree(item, ignore_errors=True)
        except Exception:
            pass


def get_upload_path(uploaded_file) -> Path:
    if uploaded_file is None:
        raise gr.Error("Сначала загрузи музыку.")

    if isinstance(uploaded_file, str):
        path = Path(uploaded_file)
    elif hasattr(uploaded_file, "name"):
        path = Path(uploaded_file.name)
    else:
        raise gr.Error("Не получилось прочитать файл. Загрузи другой формат.")

    if not path.exists():
        raise gr.Error("Файл не найден. Попробуй загрузить заново.")

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise gr.Error(f"Файл слишком большой: {size_mb:.1f} MB. Лимит сейчас: {MAX_FILE_MB} MB.")

    return path


def run_command(cmd, error_title: str, timeout: int = 3600) -> str:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        log = ((result.stderr or "") + "\n" + (result.stdout or ""))[-3500:]
        raise gr.Error(f"{error_title}\n\n{log}")
    return ((result.stderr or "") + "\n" + (result.stdout or ""))[-2000:]


def to_wav(input_path: Path, output_wav: Path) -> None:
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-vn",
            "-ar", "44100",
            "-ac", "2",
            "-sample_fmt", "s16",
            str(output_wav),
        ],
        "FFmpeg не смог прочитать этот аудиофайл. Попробуй MP3/WAV/M4A/FLAC.",
        timeout=1200,
    )


def wav_to_mp3(input_wav: Path, output_mp3: Path) -> None:
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i", str(input_wav),
            "-codec:a", "libmp3lame",
            "-b:a", "320k",
            str(output_mp3),
        ],
        "FFmpeg не смог создать MP3.",
        timeout=900,
    )


def create_minus(uploaded_file, mode):
    cleanup_old_jobs()

    mode = mode or "Качественно"
    settings = MODES.get(mode, MODES["Качественно"])

    source = get_upload_path(uploaded_file)
    job_id = uuid.uuid4().hex[:12]
    job_dir = BASE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    safe_original = job_dir / ("original" + source.suffix.lower())
    input_wav = job_dir / "input_44100.wav"
    out_dir = job_dir / "separated"

    shutil.copy2(source, safe_original)
    to_wav(safe_original, input_wav)

    command = [
        sys.executable,
        "-m", "demucs",
        "--two-stems", "vocals",
        "-n", settings["model"],
        "--shifts", settings["shifts"],
        "--overlap", settings["overlap"],
        "-o", str(out_dir),
        str(input_wav),
    ]

    log_tail = run_command(command, "Demucs не смог обработать файл. На Render может не хватить RAM.", timeout=7200)

    result_dir = out_dir / settings["model"] / input_wav.stem
    minus_wav_src = result_dir / "no_vocals.wav"
    vocals_wav_src = result_dir / "vocals.wav"

    if not minus_wav_src.exists():
        raise gr.Error("Файл минусовки не найден после обработки. Попробуй режим «Быстро».")

    minus_wav = job_dir / "minus_no_vocals.wav"
    vocals_wav = job_dir / "vocals.wav"
    shutil.copy2(minus_wav_src, minus_wav)

    if vocals_wav_src.exists():
        shutil.copy2(vocals_wav_src, vocals_wav)
    else:
        vocals_wav = None

    minus_download = minus_wav
    vocals_download = vocals_wav

    # Для телефона MP3 удобнее. В режиме супер качества оставляем WAV.
    if settings["mp3"]:
        minus_mp3 = job_dir / "minus_no_vocals_320kbps.mp3"
        wav_to_mp3(minus_wav, minus_mp3)
        minus_download = minus_mp3

        if vocals_wav:
            vocals_mp3 = job_dir / "vocals_320kbps.mp3"
            wav_to_mp3(vocals_wav, vocals_mp3)
            vocals_download = vocals_mp3

    status = (
        "Готово ✅\n\n"
        f"Режим: {mode}\n"
        f"Модель: {settings['model']}\n"
        f"Формат минусовки: {minus_download.suffix.upper().replace('.', '')}\n\n"
        "Совет: если слышны остатки голоса, попробуй «Супер качество». "
        "Если Render выдаёт ошибку RAM, используй «Быстро» или уменьши файл."
    )

    return str(minus_download), str(vocals_download) if vocals_download else None, status


with gr.Blocks(title=APP_NAME, css="footer{display:none !important}") as demo:
    gr.HTML(HTML_CSS)
    gr.Markdown(
        """
# 🎧 Minus Maker

<div class="main-card">

Загрузи музыку — сайт сделает **минусовку без вокала** и отдельно сохранит **вокал**.

Работает с популярными форматами: MP3, WAV, M4A, FLAC, OGG, AAC.  
Для Render лучше начинать с режима **Быстро** или **Качественно**.

</div>
        """
    )

    with gr.Row():
        with gr.Column():
            audio = gr.File(label="Музыка из файлов", file_types=["audio"])
            mode = gr.Radio(
                choices=list(MODES.keys()),
                value="Качественно",
                label="Режим",
                info="Чем выше качество, тем больше времени и RAM нужно серверу.",
            )
            button = gr.Button("Сделать минусовку", variant="primary")

        with gr.Column():
            status = gr.Textbox(label="Статус", lines=8)
            minus_file = gr.File(label="Скачать минусовку")
            vocals_file = gr.File(label="Скачать вокал")

    button.click(
        fn=create_minus,
        inputs=[audio, mode],
        outputs=[minus_file, vocals_file, status],
    )

demo.queue(max_size=3).launch(
    server_name="0.0.0.0",
    server_port=PORT,
)
