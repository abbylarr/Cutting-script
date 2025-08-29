# Deployment Guide - Filmlist

Руководство по развертыванию системы Filmlist в различных окружениях.

## 📋 Содержание

- [Обзор развертывания](#обзор-развертывания)
- [Требования к системе](#требования-к-системе)
- [Development окружение](#development-окружение)
- [Production окружение](#production-окружение)
- [Конфигурация](#конфигурация)
- [Мониторинг](#мониторинг)
- [Резервное копирование](#резервное-копирование)
- [Устранение неполадок](#устранение-неполадок)

## 🏗 Обзор развертывания

### Архитектура развертывания

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Nginx Proxy   │    │   Frontend      │
│   (Optional)    │◄──►│   (Required)    │◄──►│   (React)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Backend API   │
                       │   (FastAPI)     │
                       └─────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
       ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
       │ PostgreSQL  │ │    Redis    │ │ File Storage│
       │ Database    │ │   Cache     │ │ (Local/S3)  │
       └─────────────┘ └─────────────┘ └─────────────┘
```

### Варианты развертывания

1. **Docker Compose** (рекомендуется для большинства случаев)
2. **Kubernetes** (для высоконагруженных систем)
3. **Ручная установка** (для специфических требований)

## 💻 Требования к системе

### Минимальные требования

#### Development
- **CPU**: 2 ядра
- **RAM**: 4 ГБ
- **Диск**: 20 ГБ свободного места
- **ОС**: Linux, macOS, Windows с WSL2

#### Production (малая нагрузка)
- **CPU**: 4 ядра
- **RAM**: 8 ГБ
- **Диск**: 100 ГБ SSD
- **Сеть**: 100 Мбит/с

#### Production (высокая нагрузка)
- **CPU**: 8+ ядер
- **RAM**: 16+ ГБ
- **Диск**: 500+ ГБ NVMe SSD
- **Сеть**: 1 Гбит/с

### Программные зависимости

- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Python**: 3.11+ (для ручной установки)
- **Node.js**: 18+ (для frontend)
- **PostgreSQL**: 13+
- **Redis**: 6+
- **FFmpeg**: 4.4+

## 🚀 Development окружение

### Быстрый старт

```bash
# Клонирование репозитория
git clone https://github.com/your-org/filmlist.git
cd filmlist

# Настройка переменных окружения
cp .env.template .env
# Отредактируйте .env файл

# Запуск development окружения
make dev

# Или используйте Docker Compose напрямую
docker-compose -f docker-compose.dev.yml up -d
```

### Настройка .env файла

```bash
# Обязательные переменные
OPENAI_API_KEY=sk-your-openai-api-key-here
SECRET_KEY=your-super-secret-key-minimum-32-characters

# Опциональные переменные
HF_TOKEN=hf_your-huggingface-token-here
LOG_LEVEL=DEBUG
```

### Проверка развертывания

```bash
# Проверка статуса сервисов
docker-compose -f docker-compose.dev.yml ps

# Проверка логов
docker-compose -f docker-compose.dev.yml logs -f

# Проверка здоровья
make health
```

### Доступ к сервисам

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## 🏭 Production окружение

### Подготовка сервера

#### Ubuntu/Debian
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Установка дополнительных пакетов
sudo apt install -y nginx certbot python3-certbot-nginx htop iotop
```

#### CentOS/RHEL
```bash
# Обновление системы
sudo yum update -y

# Установка Docker
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Настройка production переменных

```bash
# Создание production .env файла
cp .env.production .env

# Настройка обязательных переменных
export OPENAI_API_KEY="your-production-openai-key"
export SECRET_KEY="$(openssl rand -hex 32)"
export POSTGRES_PASSWORD="$(openssl rand -base64 32)"
export BACKEND_CORS_ORIGINS="https://your-domain.com"

# Сохранение в .env файл
cat > .env << EOF
OPENAI_API_KEY=${OPENAI_API_KEY}
SECRET_KEY=${SECRET_KEY}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_USER=filmlist
POSTGRES_DB=filmlist
BACKEND_CORS_ORIGINS=${BACKEND_CORS_ORIGINS}
LOG_LEVEL=INFO
EOF
```

### SSL сертификаты

#### Использование Let's Encrypt
```bash
# Получение SSL сертификата
sudo certbot certonly --nginx -d your-domain.com -d api.your-domain.com

# Копирование сертификатов для Docker
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem
sudo chown -R $USER:$USER nginx/ssl
```

#### Настройка автообновления сертификатов
```bash
# Создание скрипта обновления
cat > /home/$USER/renew-certs.sh << 'EOF'
#!/bin/bash
sudo certbot renew --quiet
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /home/$USER/filmlist/nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem /home/$USER/filmlist/nginx/ssl/key.pem
sudo chown -R $USER:$USER /home/$USER/filmlist/nginx/ssl
cd /home/$USER/filmlist && docker-compose -f docker-compose.prod.yml restart nginx
EOF

chmod +x /home/$USER/renew-certs.sh

# Добавление в crontab
echo "0 3 * * * /home/$USER/renew-certs.sh" | crontab -
```

### Развертывание production

```bash
# Клонирование на production сервер
git clone https://github.com/your-org/filmlist.git /opt/filmlist
cd /opt/filmlist

# Настройка переменных окружения
cp .env.production .env
# Отредактируйте .env с production значениями

# Запуск production окружения
make prod

# Или используйте скрипт развертывания
./scripts/deploy.sh production
```

### Настройка Nginx (внешний)

Если вы используете внешний Nginx:

```nginx
# /etc/nginx/sites-available/filmlist
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;

    # Безопасность
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Проксирование к Docker Compose
    location / {
        proxy_pass http://localhost:80;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}

# Включение конфигурации
sudo ln -s /etc/nginx/sites-available/filmlist /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## ⚙️ Конфигурация

### Переменные окружения

#### Обязательные переменные
```bash
# API ключи
OPENAI_API_KEY=sk-...                    # OpenAI API ключ
SECRET_KEY=...                           # Секретный ключ для JWT (32+ символа)

# База данных
POSTGRES_DB=filmlist                     # Имя базы данных
POSTGRES_USER=filmlist                   # Пользователь БД
POSTGRES_PASSWORD=...                    # Пароль БД (генерируйте случайно)

# CORS
BACKEND_CORS_ORIGINS=https://domain.com  # Разрешенные домены
```

#### Опциональные переменные
```bash
# HuggingFace (для диаризации)
HF_TOKEN=hf_...                          # HuggingFace токен

# Логирование
LOG_LEVEL=INFO                           # DEBUG, INFO, WARNING, ERROR

# Обработка
RATE_PER_MINUTE=75.0                     # Стоимость за минуту
MIN_SCENE_LENGTH=2.0                     # Минимальная длина сцены
MAX_FILE_SIZE=5368709120                 # Максимальный размер файла (5GB)

# Redis
REDIS_URL=redis://redis:6379             # URL Redis сервера

# Файловое хранилище
UPLOAD_DIR=/app/uploads                  # Директория загрузок
OUTPUT_DIR=/app/output                   # Директория результатов
```

### Настройка ресурсов Docker

#### docker-compose.prod.yml (фрагмент)
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
    restart: unless-stopped
    
  db:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
    restart: unless-stopped
```

### Настройка PostgreSQL

#### Оптимизация производительности
```sql
-- Подключение к базе данных
\c filmlist

-- Настройка параметров производительности
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

-- Перезагрузка конфигурации
SELECT pg_reload_conf();
```

### Настройка Redis

#### redis.conf (production)
```ini
# Память
maxmemory 512mb
maxmemory-policy allkeys-lru

# Персистентность
save 900 1
save 300 10
save 60 10000

# Безопасность
requirepass your-redis-password

# Сеть
bind 0.0.0.0
port 6379
timeout 300

# Логирование
loglevel notice
logfile /var/log/redis/redis-server.log
```

## 📊 Мониторинг

### Health Checks

#### Встроенные проверки
```bash
# Проверка всех сервисов
./scripts/health_check.sh

# Проверка конкретного сервиса
curl -f http://localhost:8000/health
curl -f http://localhost:8000/health/detailed
```

#### Настройка мониторинга с Prometheus

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'filmlist-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']
```

#### Grafana Dashboard

Импортируйте готовый dashboard для мониторинга Filmlist:
- **Dashboard ID**: 12345 (будет доступен после релиза)
- **Метрики**: CPU, память, запросы, ошибки, время обработки

### Логирование

#### Централизованное логирование с ELK Stack

```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.15.0
    environment:
      - discovery.type=single-node
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data

  logstash:
    image: docker.elastic.co/logstash/logstash:7.15.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: docker.elastic.co/kibana/kibana:7.15.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
```

#### Настройка ротации логов

```bash
# /etc/logrotate.d/filmlist
/opt/filmlist/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 filmlist filmlist
    postrotate
        docker-compose -f /opt/filmlist/docker-compose.prod.yml restart backend
    endscript
}
```

## 💾 Резервное копирование

### Автоматическое резервное копирование

#### Настройка cron задач
```bash
# Редактирование crontab
crontab -e

# Добавление задач резервного копирования
# Ежедневный бэкап в 2:00
0 2 * * * /opt/filmlist/scripts/backup.sh

# Еженедельная очистка старых бэкапов в воскресенье в 3:00
0 3 * * 0 find /opt/filmlist/backups -name "*.sql.gz" -mtime +30 -delete
```

#### Скрипт резервного копирования
```bash
#!/bin/bash
# scripts/backup.sh

set -e

# Конфигурация
BACKUP_DIR="/opt/filmlist/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_CONTAINER="filmlist_db_prod"

# Создание директории
mkdir -p $BACKUP_DIR

# Резервное копирование базы данных
docker exec $DB_CONTAINER pg_dump -U filmlist filmlist | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Резервное копирование файлов пользователей
tar -czf $BACKUP_DIR/files_backup_$DATE.tar.gz -C /opt/filmlist uploads output

# Резервное копирование конфигурации
tar -czf $BACKUP_DIR/config_backup_$DATE.tar.gz -C /opt/filmlist .env docker-compose.prod.yml nginx

# Логирование
echo "$(date): Backup completed successfully" >> $BACKUP_DIR/backup.log

# Отправка в облачное хранилище (опционально)
# aws s3 cp $BACKUP_DIR/db_backup_$DATE.sql.gz s3://your-backup-bucket/
```

### Восстановление из резервной копии

```bash
#!/bin/bash
# scripts/restore.sh

BACKUP_FILE=$1
if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

# Остановка сервисов
docker-compose -f docker-compose.prod.yml stop backend

# Восстановление базы данных
gunzip -c $BACKUP_FILE | docker exec -i filmlist_db_prod psql -U filmlist -d filmlist

# Запуск сервисов
docker-compose -f docker-compose.prod.yml start backend

echo "Restore completed successfully"
```

### Тестирование резервных копий

```bash
#!/bin/bash
# scripts/test_backup.sh

# Создание тестового контейнера
docker run --name test_postgres -e POSTGRES_PASSWORD=test -d postgres:13

# Восстановление бэкапа в тестовый контейнер
gunzip -c $1 | docker exec -i test_postgres psql -U postgres -d postgres

# Проверка целостности данных
docker exec test_postgres psql -U postgres -d postgres -c "SELECT COUNT(*) FROM users;"

# Очистка
docker rm -f test_postgres

echo "Backup test completed successfully"
```

## 🔧 Устранение неполадок

### Частые проблемы

#### 1. Контейнеры не запускаются
```bash
# Проверка логов
docker-compose logs

# Проверка ресурсов
docker system df
docker system prune -f

# Пересборка образов
docker-compose build --no-cache
```

#### 2. Ошибки подключения к базе данных
```bash
# Проверка статуса PostgreSQL
docker-compose exec db pg_isready -U filmlist

# Проверка подключения
docker-compose exec backend python -c "
from app.db.base import engine
print(engine.execute('SELECT version()').fetchone())
"

# Применение миграций
docker-compose exec backend alembic upgrade head
```

#### 3. Проблемы с Redis
```bash
# Проверка подключения к Redis
docker-compose exec redis redis-cli ping

# Очистка кэша
docker-compose exec redis redis-cli FLUSHALL

# Проверка использования памяти
docker-compose exec redis redis-cli INFO memory
```

#### 4. Ошибки обработки видео
```bash
# Проверка FFmpeg
docker-compose exec backend ffmpeg -version

# Проверка доступности OpenAI API
docker-compose exec backend python -c "
import openai
openai.api_key = 'your-key'
print(openai.Model.list())
"

# Проверка свободного места
df -h
```

### Диагностические команды

```bash
# Общая информация о системе
docker system info
docker-compose ps
docker stats

# Проверка сетевого подключения
docker network ls
docker network inspect filmlist_network

# Проверка томов
docker volume ls
docker volume inspect filmlist_postgres_data_prod

# Мониторинг ресурсов
htop
iotop
nethogs
```

### Логи и отладка

```bash
# Просмотр логов всех сервисов
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f backend
docker-compose logs -f db

# Подключение к контейнеру для отладки
docker-compose exec backend /bin/bash
docker-compose exec db psql -U filmlist -d filmlist

# Проверка переменных окружения
docker-compose exec backend env | grep -E "(OPENAI|DATABASE|REDIS)"
```

### Производительность

```bash
# Анализ производительности PostgreSQL
docker-compose exec db psql -U filmlist -d filmlist -c "
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
"

# Мониторинг Redis
docker-compose exec redis redis-cli --latency-history

# Анализ использования диска
du -sh /opt/filmlist/*
find /opt/filmlist -type f -size +100M -exec ls -lh {} \;
```

---

## 📞 Поддержка

При возникновении проблем с развертыванием:

1. **Проверьте логи** - большинство проблем видны в логах
2. **Используйте диагностические команды** из этого руководства
3. **Обратитесь в поддержку** с подробным описанием проблемы

**Контакты:**
- 📧 support@filmlist.ru
- 💬 Чат на сайте
- 📞 +7 (495) 123-45-67

Успешного развертывания! 🚀