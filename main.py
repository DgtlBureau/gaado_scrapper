"""
FastAPI application for Facebook scraping using Playwright
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import sys
import os
from datetime import datetime
from dotenv import load_dotenv
from facebook.facebook_client import FacebookScraperClient

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True
)
logger = logging.getLogger(__name__)
logging.getLogger('facebook.facebook_client').setLevel(logging.DEBUG)

app = FastAPI(
    title="Facebook Scraper API",
    description="API for scraping Facebook posts and comments using Playwright",
    version="1.0.0"
)


def get_c_user_from_cookies() -> str:
    """
    Извлекает значение c_user из файла facebook/cookies.txt
    
    Returns:
        Значение c_user или "none" если не найдено
    """
    cookies_file = os.getenv("FACEBOOK_COOKIES_FILE", "facebook/cookies.txt")
    
    if not os.path.exists(cookies_file):
        return "none"
    
    try:
        with open(cookies_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split('\t')
                    if len(parts) >= 7 and parts[5] == 'c_user':
                        return parts[6] if len(parts) > 6 else "none"
    except Exception as e:
        logger.error(f"Ошибка при чтении cookies: {e}")
        return "none"
    
    return "none"


def get_facebook_client() -> FacebookScraperClient:
    """
    Создает экземпляр FacebookScraperClient с cookies из переменной окружения или файла
    
    Проверяет:
    1. Переменную окружения FACEBOOK_COOKIES_FILE (путь к файлу cookies)
    2. Файл facebook/cookies.txt в папке facebook
    
    Поддерживает выбор браузера через переменные окружения:
    - FACEBOOK_BROWSER_CHANNEL: канал браузера ("chrome", "msedge", "chrome-beta", и т.д.)
    - FACEBOOK_BROWSER_PATH: путь к исполняемому файлу браузера
    
    Returns:
        FacebookScraperClient с настроенными cookies (если найдены)
    """
    cookies_file = os.getenv("FACEBOOK_COOKIES_FILE", "facebook/cookies.txt")
    browser_channel = os.getenv("FACEBOOK_BROWSER_CHANNEL")
    browser_executable_path = os.getenv("FACEBOOK_BROWSER_PATH")
    
    # Параметры для создания клиента
    client_kwargs = {}
    
    # Добавляем настройки браузера, если указаны
    if browser_channel:
        client_kwargs["browser_channel"] = browser_channel
        logger.info(f"Используется браузер: {browser_channel}")
    
    if browser_executable_path:
        client_kwargs["browser_executable_path"] = browser_executable_path
        logger.info(f"Используется браузер из: {browser_executable_path}")
    
    # Проверяем переменную окружения с путем к файлу
    if cookies_file and os.path.exists(cookies_file):
        logger.info(f"Используются cookies из файла: {cookies_file}")
        return FacebookScraperClient(cookies=cookies_file, **client_kwargs)
    
    # Проверяем файл cookies.txt в папке facebook
    if os.path.exists("facebook/cookies.txt"):
        logger.info("Используются cookies из файла: facebook/cookies.txt")
        return FacebookScraperClient(cookies="facebook/cookies.txt", **client_kwargs)
    
    # Если cookies не найдены, создаем клиент без них
    logger.warning("Cookies не найдены. Facebook scraper может работать с ограничениями.")
    logger.info("Для улучшения работы создайте файл facebook/cookies.txt или установите FACEBOOK_COOKIES_FILE")
    return FacebookScraperClient(**client_kwargs)


class HTMLParseRequest(BaseModel):
    """Model for HTML parsing request"""
    html_content: str = Field(..., description="HTML content containing Facebook comments")
    limit: Optional[int] = Field(default=100, ge=1, le=1000, description="Maximum number of comments to extract")


class URLParseRequest(BaseModel):
    """Model for URL parsing request"""
    url: str = Field(..., description="URL of Facebook page with comments")
    limit: Optional[int] = Field(default=100, ge=1, le=1000, description="Maximum number of comments to extract")
    use_browser: Optional[bool] = Field(default=True, description="Use browser rendering (Playwright) for JavaScript-heavy pages")
    wait_time: Optional[int] = Field(default=5, ge=1, le=30, description="Wait time in seconds for page to load (only for browser mode)")


class FacebookPostScrapeRequest(BaseModel):
    """Model for simplified Facebook post scraping request"""
    account_name: str = Field(..., description="Facebook account/page name (e.g., 'premierbankso')")
    post_id: str = Field(..., description="Post ID or full post URL")
    limit: Optional[int] = Field(default=100, ge=1, le=1000, description="Maximum number of comments to extract")
    wait_time: Optional[int] = Field(default=10, ge=1, le=60, description="Wait time in seconds for page to load")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Main page with Facebook scraper interface"""
    c_user = get_c_user_from_cookies()
    
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Facebook Scraper API</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                max-width: 800px;
                width: 100%;
                padding: 40px;
            }
            h1 {
                color: #667eea;
                font-size: 2.5em;
                margin-bottom: 10px;
                text-align: center;
            }
            .subtitle {
                color: #666;
                text-align: center;
                margin-bottom: 30px;
                font-size: 1.1em;
            }
            .status {
                display: inline-block;
                background: #10b981;
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 0.9em;
                margin-bottom: 30px;
            }
            .info-card {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                border-left: 4px solid #667eea;
                margin-bottom: 20px;
            }
            .info-card h3 {
                color: #333;
                font-size: 0.9em;
                margin-bottom: 10px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .info-card p {
                color: #667eea;
                font-size: 1.5em;
                font-weight: bold;
            }
            .scraper-section {
                margin-top: 30px;
                padding: 25px;
                background: #f8f9fa;
                border-radius: 10px;
                border: 2px solid #667eea;
            }
            .scraper-section h2 {
                color: #667eea;
                margin-bottom: 20px;
                font-size: 1.5em;
            }
            .scraper-form {
                display: flex;
                flex-direction: column;
                gap: 10px;
                margin-bottom: 20px;
            }
            .scraper-form input {
                padding: 12px;
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                font-size: 1em;
                font-family: inherit;
            }
            .scraper-form input:focus {
                outline: none;
                border-color: #667eea;
            }
            .scraper-form button {
                padding: 12px 30px;
                background: #667eea;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 1em;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .scraper-form button:hover {
                background: #5568d3;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            .scraper-form button:disabled {
                background: #9ca3af;
                cursor: not-allowed;
                transform: none;
            }
            .result-container {
                margin-top: 20px;
                padding: 20px;
                background: white;
                border-radius: 10px;
                border-left: 4px solid #10b981;
                display: none;
            }
            .result-container.show {
                display: block;
            }
            .result-container.error {
                border-left-color: #ef4444;
            }
            .result-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }
            .result-header h3 {
                color: #333;
                margin: 0;
            }
            .result-stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }
            .stat-item {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
            }
            .stat-item .stat-label {
                font-size: 0.85em;
                color: #666;
                margin-bottom: 5px;
            }
            .stat-item .stat-value {
                font-size: 1.5em;
                font-weight: bold;
                color: #667eea;
            }
            .comments-list {
                max-height: 400px;
                overflow-y: auto;
                margin-top: 15px;
            }
            .comment-item {
                background: white;
                padding: 12px;
                border-radius: 6px;
                margin-bottom: 10px;
                border-left: 3px solid #667eea;
            }
            .comment-author {
                font-weight: bold;
                color: #667eea;
                margin-bottom: 5px;
            }
            .comment-text {
                color: #333;
                margin-bottom: 5px;
            }
            .comment-meta {
                font-size: 0.85em;
                color: #666;
            }
            .loading {
                display: none;
                text-align: center;
                padding: 20px;
                color: #667eea;
            }
            .loading.show {
                display: block;
            }
            .spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                animation: spin 1s linear infinite;
                margin: 0 auto 10px;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .links {
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                margin-top: 30px;
            }
            .link {
                display: inline-block;
                padding: 12px 24px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                transition: all 0.3s ease;
                font-weight: 500;
            }
            .link:hover {
                background: #5568d3;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            .link.secondary {
                background: #6b7280;
            }
            .link.secondary:hover {
                background: #4b5563;
            }
        </style>
        <script>
            function formatDate(dateValue) {
                if (!dateValue) return 'Дата не указана';
                try {
                    const date = new Date(dateValue);
                    if (isNaN(date.getTime())) return 'Неверная дата';
                    return date.toLocaleString('ru-RU');
                } catch (e) {
                    console.error('Ошибка форматирования даты:', e, dateValue);
                    return 'Ошибка даты';
                }
            }
            
            async function scrapeFacebookPost() {
                const accountName = document.getElementById('fb-account-name').value.trim();
                const postId = document.getElementById('fb-post-id').value.trim();
                const button = document.getElementById('scrape-btn');
                const loading = document.getElementById('loading');
                const resultContainer = document.getElementById('result-container');
                
                if (!accountName) {
                    alert('Пожалуйста, введите название аккаунта');
                    return;
                }
                
                if (!postId) {
                    alert('Пожалуйста, введите ID поста или ссылку на пост');
                    return;
                }
                
                button.disabled = true;
                loading.classList.add('show');
                resultContainer.classList.remove('show');
                
                try {
                    const response = await fetch('/facebook/scrape-post', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ 
                            account_name: accountName,
                            post_id: postId,
                            limit: 100,
                            wait_time: 10
                        })
                    });
                    
                    if (!response.ok) {
                        const errorText = await response.text();
                        console.error('HTTP Error:', response.status, errorText);
                        showError(`Ошибка сервера (${response.status}): ${errorText}`);
                        return;
                    }
                    
                    const data = await response.json();
                    console.log('Response data:', data);
                    
                    if (data.success) {
                        displayPostResult(data);
                    } else {
                        showError(data.error || 'Произошла ошибка при скраппинге');
                    }
                } catch (error) {
                    console.error('Request error:', error);
                    showError('Ошибка соединения: ' + error.message);
                } finally {
                    button.disabled = false;
                    loading.classList.remove('show');
                }
            }
            
            function displayPostResult(data) {
                const container = document.getElementById('result-container');
                const result = data.result || {};
                const comments = result.comments || [];
                
                let html = `
                    <div class="result-header">
                        <h3>📄 Результаты скраппинга</h3>
                        <span style="color: #666; font-size: 0.9em;">${data.fetched_at ? formatDate(data.fetched_at) : 'Только что'}</span>
                    </div>
                    <div class="result-stats">
                        <div class="stat-item">
                            <div class="stat-label">Всего комментариев</div>
                            <div class="stat-value">${result.total_count || comments.length || 0}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Извлечено</div>
                            <div class="stat-value">${comments.length}</div>
                        </div>
                    </div>
                `;
                
                if (comments.length > 0) {
                    html += '<h4 style="margin: 20px 0 10px 0; color: #333;">Комментарии:</h4><div class="comments-list">';
                    comments.forEach((comment, index) => {
                        html += `
                            <div class="comment-item">
                                <div class="comment-author">${escapeHtml(comment.author || 'Аноним')} ${comment.author_id ? `(${comment.author_id})` : ''}</div>
                                <div class="comment-text">${escapeHtml(comment.text || '')}</div>
                                <div class="comment-meta">❤️ ${comment.likes || 0}${comment.time ? ' • ' + escapeHtml(comment.time) : ''}</div>
                            </div>
                        `;
                    });
                    html += '</div>';
                } else {
                    html += '<p style="color: #666; margin-top: 20px;">Комментарии не найдены. Возможно, нужно увеличить время ожидания загрузки страницы.</p>';
                }
                
                container.innerHTML = html;
                container.classList.add('show');
                container.classList.remove('error');
            }
            
            function showError(message) {
                const container = document.getElementById('result-container');
                container.innerHTML = `
                    <div class="result-header">
                        <h3 style="color: #ef4444;">❌ Ошибка</h3>
                    </div>
                    <p style="color: #ef4444;">${escapeHtml(message)}</p>
                `;
                container.classList.add('show', 'error');
            }
            
            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            
            document.addEventListener('DOMContentLoaded', function() {
                const accountInput = document.getElementById('fb-account-name');
                const postInput = document.getElementById('fb-post-id');
                if (accountInput) {
                    accountInput.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            postInput.focus();
                        }
                    });
                }
                if (postInput) {
                    postInput.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            scrapeFacebookPost();
                        }
                    });
                }
            });
        </script>
    </head>
    <body>
        <div class="container">
            <h1>📱 Facebook Scraper</h1>
            <p class="subtitle">Scrape Facebook posts and comments using Playwright</p>
            <div style="text-align: center;">
                <span class="status">● Online</span>
            </div>
            
            <div class="info-card">
                <h3>Cookies Status</h3>
                <p>""" + (c_user if c_user != "none" else "none") + """</p>
            </div>
            
            <div class="scraper-section">
                <h2>📱 Facebook Post Scraper</h2>
                <div class="scraper-form">
                    <input 
                        type="text" 
                        id="fb-account-name" 
                        placeholder="Название аккаунта (например: premierbankso)" 
                        value="premierbankso"
                    />
                    <input 
                        type="text" 
                        id="fb-post-id" 
                        placeholder="ID поста или ссылка (например: pfbid0johseZFG8y6RNuNbE1wfiMr1Gr5KhmF8VnH73iV4FsJoHxPiFm2jzN9n3cSGV3Ngl)" 
                        value=""
                    />
                    <button id="scrape-btn" onclick="scrapeFacebookPost()">Скрапить комментарии</button>
                </div>
                <div id="loading" class="loading">
                    <div class="spinner"></div>
                    <p>Загрузка данных...</p>
                </div>
                <div id="result-container" class="result-container"></div>
            </div>
            
            <div class="links">
                <a href="/docs" class="link">📚 API Documentation</a>
                <a href="/redoc" class="link secondary">📖 ReDoc</a>
                <a href="/health" class="link secondary">❤️ Health Check</a>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Facebook Scraper API"
    }


@app.post("/facebook/parse-html")
async def parse_comments_from_html(request: HTMLParseRequest):
    """
    Парсинг комментариев напрямую из HTML-структуры Facebook
    
    Этот эндпоинт позволяет извлечь комментарии из HTML-кода страницы Facebook,
    когда стандартный скраппер не работает из-за изменений в структуре Facebook.
    
    Args:
        request: Запрос с HTML-контентом и опциональным лимитом комментариев
        
    Returns:
        Список извлеченных комментариев с авторами, текстом, временем и лайками
    """
    try:
        client = get_facebook_client()
        result = client.parse_comments_from_html(request.html_content, limit=request.limit)
        
        return {
            "success": True,
            "data": result,
            "parsed_at": datetime.now().isoformat()
        }
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"BeautifulSoup не установлен. Установите: pip install beautifulsoup4"
        )
    except Exception as e:
        logger.error(f"Ошибка при парсинге HTML: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при парсинге HTML: {str(e)}"
        )


@app.post("/facebook/scrape-post")
async def scrape_facebook_post_simple(request: FacebookPostScrapeRequest):
    """
    Упрощенный эндпоинт для скраппинга комментариев конкретного поста Facebook
    
    Принимает название аккаунта и ID поста, собирает полный URL и использует Playwright
    для скраппинга комментариев.
    
    Args:
        request: Запрос с названием аккаунта и ID поста
        
    Returns:
        Результат скраппинга с комментариями
    """
    import re
    
    try:
        # Извлекаем post_id из строки (может быть полный URL или только ID)
        post_id = request.post_id.strip()
        
        # Если это полный URL, извлекаем ID
        if 'facebook.com' in post_id or 'http' in post_id:
            # Извлекаем ID из URL вида: .../posts/pfbid... или .../permalink/...
            match = re.search(r'/posts/([^/?]+)|/permalink/([^/?]+)', post_id)
            if match:
                post_id = match.group(1) or match.group(2)
            else:
                # Пытаемся извлечь последнюю часть URL
                post_id = post_id.split('/')[-1].split('?')[0]
        
        # Собираем полный URL поста
        account_name = request.account_name.strip().replace('@', '')
        post_url = f"https://www.facebook.com/{account_name}/posts/{post_id}"
        
        logger.info(f"🔍 Скраппинг поста: {post_url}")
        logger.info(f"   Account: {account_name}")
        logger.info(f"   Post ID: {post_id}")
        
        client = get_facebook_client()
        
        # Используем браузер для скраппинга (обязательно, так как комментарии загружаются через JS)
        logger.info(f"🌐 Используем Playwright для рендеринга JavaScript")
        result = await client.fetch_and_parse_comments_with_browser(
            post_url, 
            limit=request.limit,
            wait_time=request.wait_time
        )
        
        return {
            "success": True,
            "result": result,
            "url": post_url,
            "account_name": account_name,
            "post_id": post_id,
            "fetched_at": datetime.now().isoformat()
        }
        
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        raise HTTPException(
            status_code=500,
            detail="Playwright не установлен. Установите: pip install playwright && playwright install chromium"
        )
    except ValueError as e:
        logger.error(f"Ошибка валидации: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Ошибка при скраппинге поста: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обработке поста: {str(e)}"
        )


@app.post("/facebook/parse-url")
async def fetch_and_parse_comments_from_url(request: URLParseRequest):
    """
    Загрузить HTML со страницы Facebook и распарсить комментарии
    
    Этот эндпоинт загружает HTML со страницы Facebook по URL и извлекает комментарии.
    Использует cookies из файла (если доступны) для доступа к странице.
    
    Если use_browser=True, использует Playwright для рендеринга JavaScript,
    что позволяет извлекать комментарии, загружаемые динамически.
    
    Args:
        request: Запрос с URL страницы и опциональными параметрами
        
    Returns:
        Результат с данными и статусом выполнения
    """
    try:
        client = get_facebook_client()
        
        if request.use_browser:
            logger.info(f"Используем браузер для рендеринга JavaScript")
            result = await client.fetch_and_parse_comments_with_browser(
                request.url, 
                limit=request.limit,
                wait_time=request.wait_time
            )
        else:
            logger.info(f"Используем простой HTTP запрос")
            result = await client.fetch_and_parse_comments_from_url(request.url, limit=request.limit)
        
        return {
            "success": True,
            "data": result,
            "status": result.get("status", "completed"),
            "message": f"Скрапинг завершен. Найдено {result.get('total_count', 0)} комментариев."
        }
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        error_msg = "Необходимые библиотеки не установлены."
        if request.use_browser:
            error_msg += " Для браузера установите: pip install playwright && playwright install chromium"
        else:
            error_msg += " Установите: pip install httpx beautifulsoup4"
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )
    except ValueError as e:
        logger.error(f"Ошибка валидации: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Ошибка при загрузке и парсинге URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обработке URL: {str(e)}"
        )


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )
