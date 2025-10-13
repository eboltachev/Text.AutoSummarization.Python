# Auto Summarization Service

Сервис предоставляет REST API для загрузки документов, выполнения анализа текста и управления пользовательскими сессиями в стиле DDD.

## Основные возможности

- Загрузка документов в форматах `txt`, `doc`, `docx`, `pdf`, `odt` с извлечением текста.
- Получение доступных типов анализа из файла `analyze_types.json`, который монтируется в контейнер.
- Автоматическое выполнение анализа при создании сессии с поддержкой универсальной (OpenAI совместимой) и предобученной (HuggingFace) моделей.
- Управление пользователями и сессиями: создание пользователей, сохранение результатов анализа, обновление аннотаций и заголовков.

## Запуск локально

```bash
docker compose up --build
```

### Переменные окружения

Файл `.env` содержит основные настройки:

- `AUTO_SUMMARIZATION_URL_PREFIX` – префикс API (по умолчанию `/v1`).
- `AUTO_SUMMARIZATION_API_HOST` / `AUTO_SUMMARIZATION_API_PORT` – адрес и порт сервиса.
- `AUTO_SUMMARIZATION_DB_*` – параметры подключения к PostgreSQL.
- `AUTO_SUMMARIZATION_SUPPORTED_FORMATS` – список разрешённых форматов документов (можно указывать через запятую или в JSON-массиве).
- `AUTO_SUMMARIZATION_ANALYZE_TYPES_PATH` – путь к конфигурации анализов (монтируется из `analyze_types.json`).
- `AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH` – путь к директории с моделью `joeddav/xlm-roberta-large-xnli` (если монтируется локально).
- `AUTO_SUMMARIZATION_PRETRAINED_MODEL_NAME` – имя модели HuggingFace для предобученной классификации (используется как запасной вариант при отсутствии локального каталога).
- `OPENAI_API_HOST` и `OPENAI_API_KEY` – параметры для универсальной модели.
- `OPENAI_MODEL_NAME` – имя модели, которое будет запрошено у OpenAI-совместимого сервера (по умолчанию `gpt-4o-mini`).

## API

- `POST /v1/analysis/load_document` – загрузка документа, возвращает извлечённый текст.
- `GET /v1/analysis/analyze_types` – список категорий и доступных вариантов анализа.
- `GET /v1/user/get_users` / `POST /v1/user/create_user` / `DELETE /v1/user/delete_user` – управление пользователями.
- `GET /v1/chat_session/fetch_page` / `POST /v1/chat_session/create` / `POST /v1/chat_session/update_summarization` / `POST /v1/chat_session/update_title` / `DELETE /v1/chat_session/delete` – управление сессиями анализа. Эндпоинт создания принимает текст, индекс категории и выбранные варианты анализа, выполняет обработку и возвращает результаты в строковом виде по ключам `entities`, `sentiments`, `classifications`, `short_summary`, `full_summary`.

## Тестирование

```bash
pytest
```

Тесты разворачивают окружение через `docker-compose` и проверяют оба типа моделей анализа, загрузку документов, а также операции с пользователями и сессиями.
