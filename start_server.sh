#!/bin/bash
# Скрипт для правильного запуска сервера из виртуального окружения

set -e

# Переходим в директорию проекта
cd "$(dirname "$0")"

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    echo "❌ Виртуальное окружение не найдено!"
    echo "Создаю виртуальное окружение..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
source venv/bin/activate

# Проверяем установлены ли зависимости
if ! python -c "import fastapi" 2>/dev/null; then
    echo "📦 Устанавливаю зависимости..."
    pip install -r requirements.txt
fi

# Проверяем установлен ли Playwright
if ! python -c "from playwright.async_api import async_playwright" 2>/dev/null; then
    echo "📦 Устанавливаю Playwright..."
    pip install playwright
    echo "🌐 Устанавливаю браузер Chromium для Playwright..."
    python -m playwright install chromium
fi

# Дополнительная проверка: убеждаемся, что браузеры установлены
echo "🔍 Проверяю установку браузеров Playwright..."
# Проверяем наличие директории с браузерами Playwright
PLAYWRIGHT_BROWSERS_PATH="$HOME/.cache/ms-playwright"
if [ ! -d "$PLAYWRIGHT_BROWSERS_PATH/chromium-*" ] 2>/dev/null; then
    echo "🌐 Браузеры не найдены, устанавливаю Chromium..."
    python -m playwright install chromium
else
    echo "✅ Браузеры Playwright найдены"
fi

# Проверяем, что импорт работает перед запуском
echo "✅ Проверяю импорт Playwright..."
if ! python -c "from playwright.async_api import async_playwright; print('Playwright OK')" 2>/dev/null; then
    echo "❌ Ошибка: Playwright не может быть импортирован!"
    echo "   Попробуйте вручную: pip install playwright && python -m playwright install chromium"
    exit 1
fi

# Запускаем сервер используя тот же Python, что и проверки
echo "🚀 Запускаю сервер..."
echo "   Сервер будет доступен на: http://localhost:8000"
echo "   Python: $(which python)"
echo ""
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

