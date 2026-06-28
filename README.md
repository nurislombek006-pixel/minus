# Minus Maker для Render

Сайт делает минусовку из музыки: загружаешь MP3/WAV/M4A/FLAC/OGG/AAC, получаешь минус и вокал.

## Файлы

- `app.py` — сайт Gradio + обработка
- `requirements.txt` — Python зависимости
- `Dockerfile` — сборка для Render с FFmpeg
- `render.yaml` — Blueprint для Render

## Как запустить на Render с телефона

1. Распакуй ZIP.
2. Загрузи все файлы в новый GitHub репозиторий.
3. Открой Render.
4. New → Web Service.
5. Подключи GitHub репозиторий.
6. Render сам увидит Dockerfile.
7. Нажми Deploy.
8. После сборки открой ссылку вида `https://minus-maker.onrender.com`.

## Важно

На бесплатном Render может не хватить RAM для Demucs. Если будет ошибка, попробуй:
- режим `Быстро`;
- файл покороче;
- MP3 вместо большого WAV/FLAC;
- платный тариф Render.

## Настройки

Можно изменить лимит файла через Environment Variable:

`MAX_FILE_MB=80`
