# Filmlist - Автоматическое создание монтажных листов

![Filmlist Logo](https://via.placeholder.com/150x50/4CAF50/FFFFFF?text=Filmlist)

Веб-сервис для автоматического создания монтажных листов из видеофайлов в соответствии с требованиями Госфильмфонда РФ. Система обрабатывает видео через комплексный пайплайн: анализ сцен, транскрипцию аудио, диаризацию спикеров, визуальный анализ кадров и формирование итогового документа в формате DOCX.

## 🚀 Возможности

- **Автоматическая обработка видео**: Загрузите видеофайл и получите готовый монтажный лист
- **Поддержка SRT файлов**: Используйте готовые субтитры или автоматическую транскрипцию
- **Визуальный анализ**: ИИ-анализ кадров с определением типов планов и описанием сцен
- **Диаризация спикеров**: Автоматическое определение и разделение голосов
- **Интерактивное редактирование**: Веб-интерфейс для корректировки результатов
- **Соответствие стандартам**: Формат документов по требованиям Госфильмфонда
- **Гибкие настройки таймкодов**: Поддержка различных стандартов и стартовых точек

## 📋 Содержание

- [Быстрый старт](#быстрый-старт)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Развертывание](#развертывание)
- [API документация](#api-документация)
- [Архитектура](#архитектура)
- [Разработка](#разработка)
- [Тестирование](#тестирование)
- [Устранение неполадок](#устранение-неполадок)

## ⚡ Быстрый старт

### С помощью Docker (рекомендуется)

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd filmlist

# Скопируйте и настройте переменные окружения
cp .env.template .env
# Отредактируйте .env файл, установите OPENAI_API_KEY

# Запустите development окружение
make dev

# Или используйте скрипт развертывания
./scripts/deploy.sh development
```

Приложение будет доступно по адресу:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Ручная установка

```bash
# Создайте виртуальное окружение
python3.11 -m venv venv311
source venv311/bin/activate

# Установите зависимости
pip install -r requirements.txt

# Настройте базу данных
createdb filmlist
alembic upgrade head

# Запустите Redis
redis-server

# Запустите приложение
uvicorn app.main:app --reload
```

## 🛠 Установка

### Системные требования

- **Python**: 3.11+
- **Node.js**: 18+ (для frontend)
- **PostgreSQL**: 13+
- **Redis**: 6+
- **FFmpeg**: Последняя версия
- **Docker & Docker Compose**: Для контейнеризации (рекомендуется)

### Установка зависимостей

#### macOS
```bash
# Установите Homebrew (если не установлен)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Установите зависимости
brew install python@3.11 postgresql redis ffmpeg
brew install --cask docker
```

#### Ubuntu/Debian
```bash
# Обновите пакеты
sudo apt update

# Установите зависимости
sudo apt install python3.11 python3.11-venv postgresql redis-server ffmpeg
sudo apt install docker.io docker-compose

# Запустите службы
sudo systemctl start postgresql redis-server docker
sudo systemctl enable postgresql redis-server docker
```

#### Windows
```powershell
# Установите через Chocolatey
choco install python311 postgresql redis ffmpeg docker-desktop

# Или скачайте и установите вручную:
# - Python 3.11: https://www.python.org/downloads/
# - PostgreSQL: https://www.postgresql.org/download/windows/
# - Redis: https://github.com/microsoftarchive/redis/releases
# - FFmpeg: https://ffmpeg.org/download.html
# - Docker Desktop: https://www.docker.com/products/docker-desktop
```

## ⚙️ Конфигурация

### Переменные окружения

Скопируйте `.env.template` в `.env` и настройте следующие параметры:

#### Обязательные параметры
```bash
# OpenAI API ключ (обязательно)
OPENAI_API_KEY=sk-your-openai-api-key-here

# База данных
DATABASE_URL=postgresql://filmlist:filmlist@localhost/filmlist

# Redis
REDIS_URL=redis://localhost:6379

# Безопасность
SECRET_KEY=your-super-secret-key-minimum-32-characters-long
```

#### Опциональные параметры
```bash
# HuggingFace токен для диаризации спикеров
HF_TOKEN=hf_your-huggingface-token-here

# Настройки обработки
RATE_PER_MINUTE=75.0
MIN_SCENE_LENGTH=2.0
MAX_FILE_SIZE=5368709120

# CORS настройки
BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# Логирование
LOG_LEVEL=INFO
```

### Настройка базы данных

```bash
# Создайте пользователя и базу данных PostgreSQL
sudo -u postgres psql
CREATE USER filmlist WITH PASSWORD 'filmlist';
CREATE DATABASE filmlist OWNER filmlist;
GRANT ALL PRIVILEGES ON DATABASE filmlist TO filmlist;
\q

# Примените миграции
alembic upgrade head
```

### Настройка Redis

```bash
# Для production создайте конфигурационный файл
sudo cp redis.conf /etc/redis/redis.conf
sudo systemctl restart redis
```

## 🐳 Развертывание

### Development окружение

```bash
# Используйте Makefile
make dev

# Или напрямую через Docker Compose
docker-compose -f docker-compose.dev.yml up -d

# Или через скрипт развертывания
./scripts/deploy.sh development
```

### Production окружение

```bash
# Настройте production переменные
cp .env.production .env
# Отредактируйте .env с production настройками

# Разверните production окружение
make prod

# Или через скрипт
./scripts/deploy.sh production
```

### Полезные команды

```bash
# Просмотр логов
make logs

# Проверка здоровья сервисов
make health

# Создание бэкапа базы данных
make backup

# Остановка всех сервисов
make stop

# Очистка контейнеров и volumes
make clean
```

## 📚 API документация

### Автоматическая документация

После запуска сервера документация доступна по адресам:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Основные эндпоинты

#### Загрузка и обработка
```http
POST /api/v1/upload
Content-Type: multipart/form-data

# Загрузка видеофайла для обработки
```

#### Статус обработки
```http
GET /api/v1/status/{task_id}

# Получение статуса обработки задачи
```

#### Редактирование монтажного листа
```http
PATCH /api/v1/montage/{task_id}
Content-Type: application/json

# Обновление строк монтажного листа
```

#### Скачивание результата
```http
GET /api/v1/download/{task_id}

# Скачивание готового DOCX файла
```

Подробная документация с примерами запросов доступна в Swagger UI.

## 🏗 Архитектура

### Структура проекта

```
filmlist/
├── app/                          # Backend приложение
│   ├── main.py                   # Точка входа FastAPI
│   ├── core/                     # Основные компоненты
│   │   ├── config.py            # Конфигурация
│   │   ├── auth.py              # Аутентификация
│   │   ├── cache.py             # Кэширование
│   │   ├── logging.py           # Логирование
│   │   └── exceptions.py        # Обработка ошибок
│   ├── api/v1/                  # API endpoints
│   │   ├── api.py               # Главный роутер
│   │   └── endpoints/           # Модули эндпоинтов
│   ├── models/                  # SQLAlchemy модели
│   ├── schemas/                 # Pydantic схемы
│   ├── services/                # Бизнес-логика
│   │   ├── video_processor.py   # Обработка видео
│   │   ├── transcription.py     # Транскрипция
│   │   ├── visual_analysis.py   # Визуальный анализ
│   │   └── docx_generator.py    # Генерация документов
│   └── db/                      # База данных
├── frontend/                    # React приложение
│   ├── src/
│   │   ├── components/          # React компоненты
│   │   ├── services/            # API клиенты
│   │   └── types/               # TypeScript типы
│   └── public/
├── alembic/                     # Миграции БД
├── tests/                       # Тесты
├── scripts/                     # Скрипты развертывания
├── nginx/                       # Конфигурация Nginx
├── docker-compose.*.yml         # Docker Compose файлы
└── Dockerfile                   # Docker образы
```

### Пайплайн обработки

```mermaid
graph TD
    A[Загрузка видео] --> B[Валидация файла]
    B --> C[Извлечение аудио]
    C --> D[Детекция сцен]
    D --> E[Транскрипция]
    E --> F[Диаризация спикеров]
    F --> G[Обработка текста]
    G --> H[Извлечение ключевых кадров]
    H --> I[Визуальный анализ]
    I --> J[Сборка монтажного листа]
    J --> K[Генерация DOCX]
```

### Технологический стек

#### Backend
- **FastAPI**: Веб-фреймворк
- **SQLAlchemy**: ORM для работы с БД
- **Alembic**: Миграции БД
- **Redis**: Кэширование и очереди задач
- **OpenAI API**: Транскрипция и анализ
- **FFmpeg**: Обработка видео/аудио
- **python-docx**: Генерация документов

#### Frontend
- **React**: UI библиотека
- **TypeScript**: Типизированный JavaScript
- **Axios**: HTTP клиент
- **Material-UI**: Компоненты интерфейса

#### Infrastructure
- **Docker**: Контейнеризация
- **Nginx**: Reverse proxy
- **PostgreSQL**: База данных
- **Redis**: Кэш и брокер сообщений

## 👨‍💻 Разработка

### Настройка среды разработки

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd filmlist

# Создайте виртуальное окружение
python3.11 -m venv venv311
source venv311/bin/activate

# Установите зависимости для разработки
pip install -r requirements.txt

# Установите pre-commit hooks
pre-commit install

# Запустите development сервер
make dev
```

### Стиль кода

```bash
# Форматирование кода
black app/ tests/
isort app/ tests/

# Линтинг
flake8 app/ tests/
mypy app/

# Проверка безопасности
bandit -r app/
```

### Структура коммитов

Используйте [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: добавить новую функцию
fix: исправить ошибку
docs: обновить документацию
style: изменения форматирования
refactor: рефакторинг кода
test: добавить тесты
chore: обновить зависимости
```

### Добавление новых функций

1. Создайте ветку: `git checkout -b feature/new-feature`
2. Напишите тесты для новой функции
3. Реализуйте функцию
4. Убедитесь, что все тесты проходят
5. Создайте Pull Request

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# Тесты с покрытием
pytest --cov=app --cov-report=html

# Конкретный модуль
pytest tests/test_video_processor.py

# Интеграционные тесты
pytest tests/test_api_*.py

# Производительность
pytest tests/test_performance_*.py
```

### Типы тестов

- **Unit тесты**: Тестирование отдельных компонентов
- **Integration тесты**: Тестирование взаимодействия компонентов
- **API тесты**: Тестирование HTTP эндпоинтов
- **End-to-end тесты**: Полный цикл обработки
- **Performance тесты**: Нагрузочное тестирование

### Тестовые данные

```bash
# Создание тестовых данных
python tests/fixtures/create_test_data.py

# Очистка тестовых данных
python tests/fixtures/cleanup_test_data.py
```

## 🔧 Устранение неполадок

### Частые проблемы

#### 1. Ошибка подключения к OpenAI API
```bash
# Проверьте API ключ
echo $OPENAI_API_KEY

# Проверьте подключение
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
```

#### 2. Проблемы с FFmpeg
```bash
# Проверьте установку FFmpeg
ffmpeg -version

# Проверьте кодеки
ffmpeg -codecs | grep h264
```

#### 3. Ошибки базы данных
```bash
# Проверьте подключение
psql $DATABASE_URL -c "SELECT version();"

# Примените миграции
alembic upgrade head

# Проверьте статус миграций
alembic current
```

#### 4. Проблемы с Redis
```bash
# Проверьте подключение
redis-cli ping

# Проверьте конфигурацию
redis-cli config get "*"
```

### Логи и мониторинг

```bash
# Просмотр логов приложения
tail -f logs/filmlist.log

# Логи Docker контейнеров
docker-compose logs -f

# Мониторинг ресурсов
docker stats

# Проверка здоровья сервисов
./scripts/health_check.sh
```

### Производительность

```bash
# Профилирование Python кода
python -m cProfile -o profile.stats app/main.py

# Анализ использования памяти
mprof run python app/main.py
mprof plot

# Нагрузочное тестирование API
ab -n 1000 -c 10 http://localhost:8000/health
```

## 📊 Мониторинг и метрики

### Health checks

Система предоставляет несколько эндпоинтов для мониторинга:

- `/health` - Базовая проверка здоровья
- `/health/detailed` - Детальная информация о сервисах
- `/metrics` - Метрики Prometheus (если настроен)

### Логирование

Логи структурированы в JSON формате и включают:
- Уровень логирования
- Временную метку
- Контекст запроса
- Трассировку ошибок

### Бэкапы

```bash
# Автоматический бэкап (настроен в cron)
make backup

# Восстановление из бэкапа
make restore BACKUP_FILE=/path/to/backup.sql.gz

# Проверка целостности бэкапа
pg_restore --list /path/to/backup.sql.gz
```

## 🤝 Участие в разработке

Мы приветствуем участие в развитии проекта! Пожалуйста:

1. Форкните репозиторий
2. Создайте ветку для вашей функции
3. Добавьте тесты для новой функциональности
4. Убедитесь, что все тесты проходят
5. Создайте Pull Request

### Код поведения

Пожалуйста, следуйте нашему [Кодексу поведения](CODE_OF_CONDUCT.md) при участии в проекте.

## 📄 Лицензия

Этот проект является проприетарным программным обеспечением. Все права защищены.

## 📞 Поддержка

Если у вас есть вопросы или проблемы:

1. Проверьте [FAQ](docs/FAQ.md)
2. Просмотрите [Issues](https://github.com/your-org/filmlist/issues)
3. Создайте новый Issue с подробным описанием проблемы

---

**Filmlist** - Делаем создание монтажных листов простым и автоматизированным! 🎬