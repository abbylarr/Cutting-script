# Локальный автономный запуск Filmlist

Прототип поднимается **без OpenAI / HF ключей**: все AI-шаги уходят в offline fallback.

## Быстрый старт

```bash
cd Cutting-script
cp .env.template .env   # уже настроен AUTONOMOUS_MODE=true

# зависимости (минимум)
pip install -r requirements.txt
# или облегчённый набор:
# pip install fastapi uvicorn pydantic-settings sqlalchemy python-jose passlib bcrypt \
#   python-multipart aiofiles openai redis alembic python-docx scenedetect opencv-python

# нужен FFmpeg в PATH
ffmpeg -version

# запуск API
uvicorn app.main:app --reload --port 8000
```

Открыть: http://localhost:8000/api/v1/docs

- `GET /` — `autonomous_mode`, `openai_enabled`
- `GET /health` — статус

## Что работает автономно

| Шаг | Без ключа |
|-----|-----------|
| Транскрипция | fallback-сегменты |
| Диаризация | эвристика спикеров |
| Текст | базовая очистка |
| Vision | rule-based описание / средний план |
| Музыка | быстрый heuristic fallback |
| Сцены | scenedetect или тайм-чанки по 30с |
| DOCX | реальная генерация |

При наличии `OPENAI_API_KEY` в `.env` включаются Whisper / GPT text / GPT vision.

## Frontend

```bash
cd frontend
npm install
REACT_APP_API_URL=http://localhost:8000/api/v1 npm start
```

При регистрации в autonomous-режиме баланс = `INITIAL_USER_BALANCE` (10000), биллинг пропускается.

## Smoke

```bash
# после генерации тестового ролика:
# ffmpeg -y -f lavfi -i color=c=blue:s=320x240:d=8 -f lavfi -i sine=f=440:d=8 \
#   -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest tests/fixtures/smoke_video.mp4
python scripts/smoke_offline.py
```
