# API Reference - Filmlist

Полная документация по REST API сервиса Filmlist для автоматического создания монтажных листов.

## 📋 Содержание

- [Обзор API](#обзор-api)
- [Аутентификация](#аутентификация)
- [Эндпоинты](#эндпоинты)
- [Схемы данных](#схемы-данных)
- [Коды ошибок](#коды-ошибок)
- [Примеры использования](#примеры-использования)
- [SDK и библиотеки](#sdk-и-библиотеки)

## 🌐 Обзор API

### Базовый URL
```
Production: https://api.filmlist.ru/api/v1
Development: http://localhost:8000/api/v1
```

### Версионирование
API использует версионирование через URL. Текущая версия: `v1`

### Формат данных
- **Запросы**: JSON, multipart/form-data (для загрузки файлов)
- **Ответы**: JSON
- **Кодировка**: UTF-8
- **Временные зоны**: UTC

### Rate Limiting
- **Общие запросы**: 100 запросов в минуту
- **Загрузка файлов**: 5 запросов в минуту
- **Аутентификация**: 10 попыток в минуту

## 🔐 Аутентификация

### JWT токены

API использует JWT (JSON Web Tokens) для аутентификации.

#### Получение токена
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Ответ:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### Использование токена
Включайте токен в заголовок Authorization для всех защищенных эндпоинтов:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Обновление токена
```http
POST /auth/refresh
Authorization: Bearer <your_token>
```

## 📡 Эндпоинты

### Аутентификация

#### POST /auth/register
Регистрация нового пользователя.

**Параметры:**
```json
{
  "email": "string",
  "password": "string",
  "confirm_password": "string"
}
```

**Ответ (201):**
```json
{
  "id": "uuid",
  "email": "string",
  "created_at": "datetime"
}
```

#### POST /auth/login
Вход в систему.

**Параметры:**
```json
{
  "email": "string",
  "password": "string"
}
```

**Ответ (200):**
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### POST /auth/logout
Выход из системы (аннулирование токена).

**Заголовки:**
```
Authorization: Bearer <token>
```

**Ответ (200):**
```json
{
  "message": "Successfully logged out"
}
```

### Загрузка и обработка

#### POST /upload
Загрузка видеофайла для обработки.

**Параметры (multipart/form-data):**
- `file`: Видеофайл (обязательно)
- `use_srt`: boolean (опционально, по умолчанию false)
- `project_metadata`: JSON строка с метаданными проекта

**Пример запроса:**
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@video.mp4" \
  -F "use_srt=false" \
  -F "project_metadata={\"title\":\"Мой фильм\",\"year\":2024}" \
  http://localhost:8000/api/v1/upload
```

**Ответ (200):**
```json
{
  "task_id": "uuid",
  "status": "pending",
  "estimated_cost": 750.0,
  "estimated_duration": "10 minutes"
}
```

#### POST /upload_srt/{task_id}
Загрузка SRT файла для существующей задачи.

**Параметры:**
- `task_id`: UUID задачи (в URL)
- `file`: SRT файл (multipart/form-data)

**Ответ (200):**
```json
{
  "task_id": "uuid",
  "status": "processing",
  "message": "SRT file uploaded successfully"
}
```

### Статус и результаты

#### GET /status/{task_id}
Получение статуса обработки задачи.

**Параметры:**
- `task_id`: UUID задачи

**Ответ (200):**
```json
{
  "task_id": "uuid",
  "status": "processing",
  "progress": 0.65,
  "current_step": "visual_analysis",
  "estimated_completion": "2024-01-15T14:30:00Z",
  "error": null,
  "result": null
}
```

**Возможные статусы:**
- `pending` - Задача в очереди
- `processing` - Обработка в процессе
- `completed` - Обработка завершена
- `failed` - Произошла ошибка
- `cancelled` - Задача отменена

#### GET /result/{task_id}
Получение результата обработки.

**Ответ (200):**
```json
{
  "task_id": "uuid",
  "montage_rows": [
    {
      "number": 1,
      "start_timecode": "01:00:00:00",
      "end_timecode": "01:00:05:12",
      "shot_type": "Общий",
      "description": "Мужчина входит в комнату",
      "dialogue": "Привет, как дела?",
      "speaker": "Спикер 1",
      "has_music": false
    }
  ],
  "metadata": {
    "total_scenes": 45,
    "total_duration": "01:23:45",
    "processing_time": "00:15:30"
  }
}
```

### Редактирование

#### PATCH /montage/{task_id}
Обновление строк монтажного листа.

**Параметры:**
```json
{
  "rows": [
    {
      "number": 1,
      "shot_type": "Крупный",
      "description": "Обновленное описание",
      "dialogue": "Исправленный текст",
      "speaker": "Иван Петров"
    }
  ]
}
```

**Ответ (200):**
```json
{
  "task_id": "uuid",
  "updated_rows": 1,
  "message": "Montage updated successfully"
}
```

#### POST /save/{task_id}
Сохранение изменений проекта.

**Параметры:**
```json
{
  "project_name": "string",
  "montage_rows": [...],
  "metadata": {...}
}
```

**Ответ (200):**
```json
{
  "project_id": "uuid",
  "message": "Project saved successfully"
}
```

### Скачивание

#### GET /download/{task_id}
Скачивание готового DOCX файла.

**Параметры:**
- `task_id`: UUID задачи
- `format`: string (опционально, по умолчанию "docx")

**Ответ (200):**
```
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename="montage_list.docx"

[binary data]
```

### Управление проектами

#### GET /projects
Получение списка проектов пользователя.

**Параметры запроса:**
- `page`: int (по умолчанию 1)
- `limit`: int (по умолчанию 20, максимум 100)
- `status`: string (фильтр по статусу)
- `search`: string (поиск по названию)

**Ответ (200):**
```json
{
  "projects": [
    {
      "id": "uuid",
      "name": "string",
      "status": "completed",
      "created_at": "datetime",
      "updated_at": "datetime",
      "duration": "01:23:45",
      "task_id": "uuid"
    }
  ],
  "total": 15,
  "page": 1,
  "limit": 20,
  "pages": 1
}
```

#### GET /projects/{project_id}
Получение детальной информации о проекте.

**Ответ (200):**
```json
{
  "id": "uuid",
  "name": "string",
  "metadata": {...},
  "montage_rows": [...],
  "status": "completed",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### PUT /projects/{project_id}
Обновление проекта.

**Параметры:**
```json
{
  "name": "string",
  "metadata": {...}
}
```

#### DELETE /projects/{project_id}
Удаление проекта.

**Ответ (204):** Нет содержимого

### Биллинг

#### GET /billing/balance
Получение текущего баланса.

**Ответ (200):**
```json
{
  "balance": 1500.00,
  "currency": "RUB",
  "available_minutes": 20
}
```

#### POST /billing/topup
Пополнение баланса.

**Параметры:**
```json
{
  "amount": 1000.00,
  "payment_method": "sbp"
}
```

**Ответ (200):**
```json
{
  "payment_id": "uuid",
  "amount": 1000.00,
  "qr_code": "data:image/png;base64,...",
  "payment_url": "https://...",
  "expires_at": "datetime"
}
```

#### GET /billing/transactions
История транзакций.

**Параметры запроса:**
- `page`: int
- `limit`: int
- `type`: string ("payment" | "charge")

**Ответ (200):**
```json
{
  "transactions": [
    {
      "id": "uuid",
      "type": "charge",
      "amount": -75.00,
      "description": "Video processing",
      "created_at": "datetime"
    }
  ],
  "total": 25,
  "page": 1,
  "limit": 20
}
```

## 📊 Схемы данных

### ProcessingTask
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "status": "pending|processing|completed|failed|cancelled",
  "video_filename": "string",
  "video_path": "string",
  "srt_path": "string|null",
  "progress": "float",
  "current_step": "string",
  "error_message": "string|null",
  "result": "object|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### MontageRow
```json
{
  "number": "integer",
  "start_timecode": "string",
  "end_timecode": "string",
  "shot_type": "Дальний|Общий|Средний|Крупный|Деталь",
  "description": "string",
  "dialogue": "string",
  "speaker": "string|null",
  "has_music": "boolean"
}
```

### FilmMetadata
```json
{
  "title": "string",
  "production_company": "string",
  "year": "integer",
  "country": "string",
  "screenwriters": ["string"],
  "copyright_holders": ["string"],
  "duration": "string",
  "episodes_count": "integer",
  "format": "string",
  "color_type": "Цветной|Черно-белый",
  "media_carrier": "string",
  "original_language": "string",
  "subtitle_language": "string",
  "audio_language": "string"
}
```

### ProjectSettings
```json
{
  "timecode_start": "01:00:00:00|00:00:00:00",
  "standard": "ГФФ|Красногорский",
  "fps": "float"
}
```

## ⚠️ Коды ошибок

### HTTP статус коды

- **200 OK** - Успешный запрос
- **201 Created** - Ресурс создан
- **204 No Content** - Успешно, нет содержимого
- **400 Bad Request** - Неверный запрос
- **401 Unauthorized** - Не авторизован
- **403 Forbidden** - Доступ запрещен
- **404 Not Found** - Ресурс не найден
- **409 Conflict** - Конфликт данных
- **413 Payload Too Large** - Файл слишком большой
- **415 Unsupported Media Type** - Неподдерживаемый тип файла
- **422 Unprocessable Entity** - Ошибка валидации
- **429 Too Many Requests** - Превышен лимит запросов
- **500 Internal Server Error** - Внутренняя ошибка сервера
- **503 Service Unavailable** - Сервис недоступен

### Формат ошибок

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": {
      "field": "email",
      "reason": "Invalid email format"
    },
    "timestamp": "2024-01-15T12:00:00Z",
    "request_id": "uuid"
  }
}
```

### Коды ошибок приложения

#### Аутентификация (AUTH_*)
- `AUTH_INVALID_CREDENTIALS` - Неверные учетные данные
- `AUTH_TOKEN_EXPIRED` - Токен истек
- `AUTH_TOKEN_INVALID` - Недействительный токен
- `AUTH_USER_NOT_FOUND` - Пользователь не найден

#### Валидация (VALIDATION_*)
- `VALIDATION_ERROR` - Ошибка валидации данных
- `VALIDATION_FILE_TOO_LARGE` - Файл слишком большой
- `VALIDATION_UNSUPPORTED_FORMAT` - Неподдерживаемый формат
- `VALIDATION_MISSING_FIELD` - Отсутствует обязательное поле

#### Обработка (PROCESSING_*)
- `PROCESSING_FAILED` - Ошибка обработки
- `PROCESSING_TIMEOUT` - Превышено время обработки
- `PROCESSING_INSUFFICIENT_BALANCE` - Недостаточно средств
- `PROCESSING_QUEUE_FULL` - Очередь обработки переполнена

#### Биллинг (BILLING_*)
- `BILLING_INSUFFICIENT_FUNDS` - Недостаточно средств
- `BILLING_PAYMENT_FAILED` - Ошибка платежа
- `BILLING_INVALID_AMOUNT` - Неверная сумма

#### Внешние сервисы (EXTERNAL_*)
- `EXTERNAL_OPENAI_ERROR` - Ошибка OpenAI API
- `EXTERNAL_OPENAI_RATE_LIMIT` - Превышен лимит OpenAI
- `EXTERNAL_SERVICE_UNAVAILABLE` - Внешний сервис недоступен

## 💡 Примеры использования

### Python

```python
import requests
import json

class FilmlistAPI:
    def __init__(self, base_url, token=None):
        self.base_url = base_url
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers.update({
                'Authorization': f'Bearer {token}'
            })
    
    def login(self, email, password):
        response = self.session.post(
            f'{self.base_url}/auth/login',
            json={'email': email, 'password': password}
        )
        response.raise_for_status()
        data = response.json()
        self.token = data['access_token']
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}'
        })
        return data
    
    def upload_video(self, video_path, metadata=None):
        with open(video_path, 'rb') as f:
            files = {'file': f}
            data = {}
            if metadata:
                data['project_metadata'] = json.dumps(metadata)
            
            response = self.session.post(
                f'{self.base_url}/upload',
                files=files,
                data=data
            )
        response.raise_for_status()
        return response.json()
    
    def get_status(self, task_id):
        response = self.session.get(f'{self.base_url}/status/{task_id}')
        response.raise_for_status()
        return response.json()
    
    def download_result(self, task_id, output_path):
        response = self.session.get(f'{self.base_url}/download/{task_id}')
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)

# Использование
api = FilmlistAPI('http://localhost:8000/api/v1')
api.login('user@example.com', 'password')

# Загрузка видео
result = api.upload_video('video.mp4', {
    'title': 'Мой фильм',
    'year': 2024
})
task_id = result['task_id']

# Отслеживание прогресса
import time
while True:
    status = api.get_status(task_id)
    print(f"Status: {status['status']}, Progress: {status['progress']}")
    
    if status['status'] == 'completed':
        api.download_result(task_id, 'montage_list.docx')
        break
    elif status['status'] == 'failed':
        print(f"Error: {status['error']}")
        break
    
    time.sleep(30)
```

### JavaScript/Node.js

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

class FilmlistAPI {
    constructor(baseURL) {
        this.baseURL = baseURL;
        this.client = axios.create({ baseURL });
    }

    async login(email, password) {
        const response = await this.client.post('/auth/login', {
            email,
            password
        });
        
        this.token = response.data.access_token;
        this.client.defaults.headers.common['Authorization'] = 
            `Bearer ${this.token}`;
        
        return response.data;
    }

    async uploadVideo(videoPath, metadata = {}) {
        const form = new FormData();
        form.append('file', fs.createReadStream(videoPath));
        form.append('project_metadata', JSON.stringify(metadata));

        const response = await this.client.post('/upload', form, {
            headers: form.getHeaders()
        });

        return response.data;
    }

    async getStatus(taskId) {
        const response = await this.client.get(`/status/${taskId}`);
        return response.data;
    }

    async downloadResult(taskId, outputPath) {
        const response = await this.client.get(`/download/${taskId}`, {
            responseType: 'stream'
        });

        const writer = fs.createWriteStream(outputPath);
        response.data.pipe(writer);

        return new Promise((resolve, reject) => {
            writer.on('finish', resolve);
            writer.on('error', reject);
        });
    }
}

// Использование
async function main() {
    const api = new FilmlistAPI('http://localhost:8000/api/v1');
    
    await api.login('user@example.com', 'password');
    
    const result = await api.uploadVideo('video.mp4', {
        title: 'Мой фильм',
        year: 2024
    });
    
    const taskId = result.task_id;
    
    // Отслеживание прогресса
    while (true) {
        const status = await api.getStatus(taskId);
        console.log(`Status: ${status.status}, Progress: ${status.progress}`);
        
        if (status.status === 'completed') {
            await api.downloadResult(taskId, 'montage_list.docx');
            break;
        } else if (status.status === 'failed') {
            console.error(`Error: ${status.error}`);
            break;
        }
        
        await new Promise(resolve => setTimeout(resolve, 30000));
    }
}

main().catch(console.error);
```

### cURL примеры

#### Аутентификация
```bash
# Вход в систему
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  http://localhost:8000/api/v1/auth/login

# Сохраните токен из ответа
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### Загрузка видео
```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@video.mp4" \
  -F "project_metadata={\"title\":\"Мой фильм\",\"year\":2024}" \
  http://localhost:8000/api/v1/upload
```

#### Проверка статуса
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/status/TASK_ID
```

#### Скачивание результата
```bash
curl -H "Authorization: Bearer $TOKEN" \
  -o montage_list.docx \
  http://localhost:8000/api/v1/download/TASK_ID
```

## 📚 SDK и библиотеки

### Официальные SDK

#### Python SDK
```bash
pip install filmlist-python
```

```python
from filmlist import FilmlistClient

client = FilmlistClient(api_key='your_api_key')
task = client.upload_video('video.mp4')
result = client.wait_for_completion(task.id)
```

#### JavaScript SDK
```bash
npm install filmlist-js
```

```javascript
import { FilmlistClient } from 'filmlist-js';

const client = new FilmlistClient({ apiKey: 'your_api_key' });
const task = await client.uploadVideo('video.mp4');
const result = await client.waitForCompletion(task.id);
```

### Неофициальные библиотеки

- **filmlist-go** - Go клиент
- **filmlist-php** - PHP SDK
- **filmlist-ruby** - Ruby gem

### Webhook интеграция

Для получения уведомлений о завершении обработки настройте webhook:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://your-app.com/webhook","events":["task.completed","task.failed"]}' \
  http://localhost:8000/api/v1/webhooks
```

Формат webhook уведомления:
```json
{
  "event": "task.completed",
  "task_id": "uuid",
  "timestamp": "datetime",
  "data": {
    "status": "completed",
    "result_url": "https://..."
  }
}
```

---

Для получения актуальной интерактивной документации посетите `/docs` эндпоинт вашего API сервера. 📖