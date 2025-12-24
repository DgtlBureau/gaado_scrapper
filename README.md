# Facebook Scraper Project

Отдельный проект для скраппинга Facebook с использованием Playwright.

## Структура проекта

```
scraper_project/
├── facebook/
│   ├── __init__.py
│   ├── facebook_client.py    # Основной клиент для скраппинга Facebook
│   └── cookies.txt            # Файл с cookies для авторизации
├── screenshots/               # Скриншоты процесса скраппинга
│   ├── 01_initial_load.png
│   ├── 02_scroll_*.png
│   └── 03_final_state.png
├── env.example               # Пример файла с переменными окружения
└── README.md
```

## Установка

1. Установите зависимости:
```bash
pip install playwright beautifulsoup4 python-dotenv httpx
playwright install chromium
```

2. Скопируйте `env.example` в `.env` и заполните необходимые значения:
```bash
cp env.example .env
```

3. Настройте файл с cookies (`facebook/cookies.txt`) для авторизации в Facebook.

## Использование

```python
from facebook.facebook_client import FacebookScraperClient

# Инициализация клиента
client = FacebookScraperClient(
    cookies="facebook/cookies.txt",
    browser_channel="chrome"  # или "msedge", "chrome-beta" и т.д.
)

# Скраппинг комментариев через браузер
result = await client.fetch_and_parse_comments_with_browser(
    url="https://www.facebook.com/...",
    limit=100
)

print(f"Найдено комментариев: {result['total_count']}")
```

## Переменные окружения

См. `env.example` для полного списка переменных окружения.

Основные:
- `FACEBOOK_COOKIES_FILE` - путь к файлу с cookies
- `FACEBOOK_BROWSER_CHANNEL` - канал браузера (chrome, msedge, и т.д.)

