"""
Facebook Scraper Client
Для получения данных с публичных страниц Facebook через Playwright
Использует только Playwright для скраппинга (без facebook-scraper)
"""
import asyncio
import logging
import os
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:
    logger.warning("BeautifulSoup не установлен. Парсинг HTML может не работать. Установите: pip install beautifulsoup4")
    BeautifulSoup = None

try:
    from playwright.async_api import async_playwright, Browser, Page
except ImportError:
    logger.error("Playwright не установлен. Установите: pip install playwright && playwright install chromium")
    async_playwright = None


class FacebookScraperClient:
    """Клиент для работы с Facebook через Playwright скрейпинг"""
    
    def __init__(self, cookies: Optional[str] = None, user_agent: Optional[str] = None, 
                 browser_channel: Optional[str] = None, browser_executable_path: Optional[str] = None):
        """
        Инициализация клиента
        
        Args:
            cookies: Путь к файлу с cookies (опционально, для обхода ограничений)
            user_agent: User-Agent для запросов (опционально)
            browser_channel: Канал браузера для использования (например, "chrome", "msedge", "chrome-beta")
                           Доступные варианты: "chrome", "chrome-beta", "msedge", "msedge-beta", "msedge-dev"
            browser_executable_path: Путь к исполняемому файлу браузера (если нужно использовать конкретный браузер)
        """
        self.cookies = cookies
        self.browser_channel = browser_channel
        self.browser_executable_path = browser_executable_path
        # Используем современный User-Agent по умолчанию, если не указан
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        # self.user_agent = user_agent or (
        #     "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X)" 
        #     "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        #     "Version/17.4 Mobile/15E148 Safari/604.1"
        # )
    
    def _load_cookies_for_playwright(self) -> List[Dict[str, Any]]:
        """
        Загрузить cookies из файла в формате для Playwright
        
        Returns:
            Список словарей с cookies для Playwright
        """
        playwright_cookies = []
        
        if not self.cookies:
            logger.debug("Cookies не указаны, работаем без авторизации")
            return playwright_cookies
        
        logger.info(f"📂 Шаг 1: Загрузка cookies из файла: {self.cookies}")
        
        try:
            if not os.path.exists(self.cookies):
                logger.warning(f"⚠️  Файл cookies не найден: {self.cookies}")
                return playwright_cookies
            
            with open(self.cookies, 'r') as f:
                lines = f.readlines()
                logger.debug(f"   Прочитано {len(lines)} строк из файла cookies")
                
                for line_num, line in enumerate(lines, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain = parts[0].lstrip('.')
                        path = parts[2]
                        secure = parts[3] == 'TRUE'
                        expiration = int(parts[4]) if parts[4] != '0' else None
                        name = parts[5]
                        value = parts[6] if len(parts) > 6 else ''
                        
                        cookie = {
                            "name": name,
                            "value": value,
                            "domain": domain,
                            "path": path,
                            "secure": secure,
                        }
                        
                        if expiration:
                            cookie["expires"] = expiration
                        
                        playwright_cookies.append(cookie)
                        logger.debug(f"   ✅ Загружен cookie: {name} для домена {domain}")
                    else:
                        logger.debug(f"   ⚠️  Пропущена строка {line_num}: неверный формат (ожидается 7+ полей)")
            
            logger.info(f"✅ Шаг 1 завершен: Загружено {len(playwright_cookies)} cookies")
            if playwright_cookies:
                cookie_names = [c.get('name', 'unknown') for c in playwright_cookies]
                logger.info(f"   Cookie names: {', '.join(cookie_names)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке cookies: {e}", exc_info=True)
        
        return playwright_cookies
    
    def parse_comments_from_html(self, html_content: str, limit: int = 100) -> Dict[str, Any]:
        """
        Парсинг комментариев напрямую из HTML-структуры Facebook
        
        Args:
            html_content: HTML-строка с комментариями Facebook
            limit: Максимальное количество комментариев для извлечения
            
        Returns:
            Словарь с отформатированными комментариями
        """
        if BeautifulSoup is None:
            raise ImportError("BeautifulSoup не установлен. Установите: pip install beautifulsoup4")
        
        if not html_content or not html_content.strip():
            logger.warning("Получена пустая HTML-структура")
            return {
                "comments": [],
                "total_count": 0
            }
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            comments = []
            
            # Различные селекторы для поиска комментариев в Facebook HTML
            # Facebook использует разные структуры, попробуем несколько вариантов
            
            # Вариант 1: Поиск по data-ft атрибутам (старая структура)
            comment_elements = soup.find_all(attrs={"data-ft": re.compile(r".*top_level_post_id.*")})
            
            # Вариант 2: Поиск по классам комментариев
            if not comment_elements:
                comment_elements = soup.find_all('div', class_=re.compile(r'.*comment.*', re.I))
            
            # Вариант 3: Поиск по структуре с userContentWrapper
            if not comment_elements:
                comment_elements = soup.find_all('div', attrs={"data-testid": re.compile(r".*comment.*", re.I)})
            
            # Вариант 4: Поиск по структуре с role="article" (часто используется для комментариев)
            if not comment_elements:
                comment_elements = soup.find_all('div', role="article")
            
            # Вариант 5: Поиск по структуре с data-sigil (используется в мобильной версии)
            if not comment_elements:
                comment_elements = soup.find_all(attrs={"data-sigil": re.compile(r".*comment.*", re.I)})
            
            logger.info(f"Найдено {len(comment_elements)} потенциальных элементов комментариев")
            
            for idx, element in enumerate(comment_elements[:limit]):
                try:
                    comment_data = self._extract_comment_data(element)
                    if comment_data and comment_data.get("text"):
                        comments.append(comment_data)
                except Exception as e:
                    logger.debug(f"Ошибка при извлечении комментария #{idx}: {e}")
                    continue
            
            logger.info(f"Успешно извлечено {len(comments)} комментариев из HTML")
            
            return {
                "comments": comments,
                "total_count": len(comments)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге HTML комментариев: {e}", exc_info=True)
            return {
                "comments": [],
                "total_count": 0,
                "error": str(e)
            }
    
    def _extract_comment_data(self, element) -> Optional[Dict[str, Any]]:
        """
        Извлечь данные одного комментария из HTML-элемента
        
        Args:
            element: BeautifulSoup элемент с комментарием
            
        Returns:
            Словарь с данными комментария или None
        """
        try:
            comment_data = {}
            
            # Извлечение текста комментария
            # Пробуем разные селекторы для текста
            text_selectors = [
                'div[data-testid="comment"]',
                '.userContent',
                '[data-sigil="comment-body"]',
                '.comment-body',
                'span[dir="auto"]',
            ]
            
            text = None
            for selector in text_selectors:
                text_elem = element.select_one(selector)
                if text_elem:
                    text = text_elem.get_text(strip=True)
                    if text:
                        break
            
            # Если не нашли через селекторы, пробуем найти любой текст внутри
            if not text:
                # Ищем все текстовые узлы, но пропускаем ссылки и кнопки
                text_parts = []
                for text_node in element.find_all(string=True):
                    parent = text_node.parent
                    if parent and parent.name not in ['a', 'button', 'script', 'style']:
                        text_part = text_node.strip()
                        if text_part:
                            text_parts.append(text_part)
                text = ' '.join(text_parts).strip()
            
            comment_data["text"] = text or ""
            
            # Извлечение имени автора
            author_selectors = [
                'a[role="link"]',
                'strong a',
                'h3 a',
                '[data-hovercard-prefer-more-content-show="1"]',
                'a[href*="/user/"]',
                'a[href*="/profile.php"]',
            ]
            
            author = None
            author_id = None
            for selector in author_selectors:
                author_elem = element.select_one(selector)
                if author_elem:
                    author = author_elem.get_text(strip=True)
                    href = author_elem.get('href', '')
                    # Извлекаем ID из ссылки
                    if '/user/' in href:
                        author_id = href.split('/user/')[-1].split('/')[0].split('?')[0]
                    elif 'profile.php?id=' in href:
                        author_id = href.split('profile.php?id=')[-1].split('&')[0]
                    if author:
                        break
            
            comment_data["author"] = author or ""
            comment_data["author_id"] = author_id or ""
            
            # Извлечение времени комментария
            time_selectors = [
                'a[href*="/comment/"]',
                'a abbr',
                '[data-tooltip-content]',
                'a[title]',
            ]
            
            time_str = None
            for selector in time_selectors:
                time_elem = element.select_one(selector)
                if time_elem:
                    time_str = time_elem.get('title') or time_elem.get('data-tooltip-content') or time_elem.get_text(strip=True)
                    if time_str:
                        break
            
            comment_data["time"] = time_str or ""
            
            # Извлечение количества лайков
            likes_selectors = [
                '[aria-label*="Like"]',
                '[data-sigil="reactions-count"]',
                '.like-count',
            ]
            
            likes = 0
            for selector in likes_selectors:
                likes_elem = element.select_one(selector)
                if likes_elem:
                    likes_text = likes_elem.get_text(strip=True)
                    # Пытаемся извлечь число из текста
                    likes_match = re.search(r'(\d+)', likes_text.replace(',', '').replace('.', ''))
                    if likes_match:
                        try:
                            likes = int(likes_match.group(1))
                            break
                        except ValueError:
                            pass
            
            comment_data["likes"] = likes
            
            # Извлечение ID комментария
            comment_id = element.get('id') or element.get('data-ft', '')
            if comment_id and isinstance(comment_id, str):
                # Пытаемся извлечь ID из data-ft JSON
                if 'top_level_post_id' in comment_id:
                    try:
                        import json
                        # data-ft может быть JSON строкой
                        ft_data = json.loads(comment_id) if comment_id.startswith('{') else {}
                        comment_id = ft_data.get('top_level_post_id', '')
                    except:
                        # Если не JSON, пытаемся извлечь через regex
                        id_match = re.search(r'top_level_post_id["\']?\s*:\s*["\']?(\d+)', comment_id)
                        if id_match:
                            comment_id = id_match.group(1)
            
            comment_data["comment_id"] = str(comment_id) if comment_id else ""
            
            # Извлечение ответов (replies) - упрощенная версия
            replies = []
            reply_elements = element.find_all('div', class_=re.compile(r'.*reply.*', re.I))
            for reply_elem in reply_elements[:5]:  # Ограничиваем количество ответов
                reply_data = self._extract_comment_data(reply_elem)
                if reply_data:
                    replies.append(reply_data)
            
            comment_data["replies"] = replies
            
            return comment_data
            
        except Exception as e:
            logger.debug(f"Ошибка при извлечении данных комментария: {e}")
            return None
    
    async def fetch_and_parse_comments_with_browser(self, url: str, limit: int = 100, wait_time: int = 5) -> Dict[str, Any]:
        """
        Загрузить страницу через браузер (Playwright) с рендерингом JavaScript и распарсить комментарии
        
        Использует инкрементальный скраппинг: парсит комментарии после каждого скролла,
        собирая уникальные комментарии до достижения лимита.
        
        Args:
            url: URL страницы Facebook с комментариями
            limit: Максимальное количество комментариев для извлечения
            wait_time: Время ожидания загрузки страницы в секундах
            
        Returns:
            Словарь с отформатированными комментариями и метаданными
        """
        if async_playwright is None:
            raise ImportError(
                "Playwright не установлен. Установите: pip install playwright && playwright install chromium"
            )
        
        start_time = datetime.now()
        status = "started"
        
        try:
            logger.info(f"Начало скраппинга: {url} (лимит: {limit})")
            
            # Загружаем cookies
            playwright_cookies = self._load_cookies_for_playwright()
            
            # Пробуем мобильную версию
            mobile_url = url.replace("www.facebook.com", "m.facebook.com")
            
            all_comments = []  # Хранилище для всех уникальных комментариев
            seen_comment_ids = set()  # Для отслеживания уникальности
            
            async with async_playwright() as p:
                status = "initializing_browser"
                
                # Настройка параметров запуска браузера
                launch_options = {"headless": False}
                
                # Используем конкретный канал браузера, если указан
                if self.browser_channel:
                    launch_options["channel"] = self.browser_channel
                    logger.info(f"🌐 Используем браузер: {self.browser_channel}")
                
                # Или используем конкретный исполняемый файл, если указан
                elif self.browser_executable_path:
                    launch_options["executable_path"] = self.browser_executable_path
                    logger.info(f"🌐 Используем браузер из: {self.browser_executable_path}")
                
                browser = await p.chromium.launch(**launch_options)
                context = await browser.new_context(
                    user_agent=self.user_agent,
                    viewport={"width": 1920, "height": 1080}
                )
                
                if playwright_cookies:
                    await context.add_cookies(playwright_cookies)
                
                page = await context.new_page()
                
                try:
                    # Создаем директорию для скриншотов если её нет
                    screenshots_dir = "screenshots"
                    os.makedirs(screenshots_dir, exist_ok=True)
                    
                    # Загружаем страницу
                    await page.goto(mobile_url, wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(wait_time * 1000)
                    
                    # Делаем скриншот после загрузки страницы
                    screenshot_path = f"{screenshots_dir}/01_initial_load.png"
                    await page.screenshot(path=screenshot_path, full_page=False)
                    logger.info(f"📸 Скриншот сохранен: {screenshot_path}")
                    
                    # Простой скраппинг: скроллим каждые 5 секунд и парсим комментарии
                    status = "scrolling_and_collecting"
                    
                    scroll_interval = 5000  # 5 секунд между скроллами
                    max_scrolls = 3  # Максимум 3 скролла
                    no_new_comments_count = 0  # Счетчик скроллов без новых комментариев
                    max_no_new_comments = 2  # Останавливаемся после 2 скроллов без новых комментариев
                    
                    for i in range(max_scrolls):
                        logger.info(f"🔄 Скролл #{i+1}/{max_scrolls}")
                        
                        # Используем нативные методы Playwright для скролла
                        # Получаем размеры экрана для расчета скролла
                        viewport_size = page.viewport_size
                        if viewport_size:
                            scroll_height = viewport_size['height']
                        else:
                            scroll_height = await page.evaluate("window.innerHeight")
                        
                        # Скроллим колесом мыши (нативный метод Playwright)
                        # Делаем несколько скроллов для надежности
                        # await page.mouse.move(x=500, y=500)
                        # await page.wait_for_timeout(200)
                        # await page.mouse.wheel(0, 2500)
                        # await page.wait_for_timeout(2000)
                        # await page.mouse.wheel(0, 2500)  # Дополнительный скролл
                        # await page.keyboard.press("PageDown")
                        # await page.keyboard.press("PageDown")
                        await page.keyboard.press("PageDown")
                        await page.evaluate("window.scrollBy(0, 1200)")
                        
                        # Альтернативно можно использовать клавиатуру
                        # await page.keyboard.press('PageDown')
                        # Ждем 5 секунд для загрузки новых комментариев
                        await page.wait_for_timeout(scroll_interval)
                        
                        # Парсим комментарии после каждого скролла (сократили итерации)
                        html_content = await page.content()
                        parsed_result = self.parse_comments_from_html(html_content, limit=limit)
                        new_comments = parsed_result.get('comments', [])
                        
                        # Логируем примеры найденных комментариев
                        if new_comments:
                            logger.info(f"Скролл #{i+1}: найдено {len(new_comments)} комментариев в HTML")
                            # Показываем первые 2 комментария как примеры (сократили с 3 до 2)
                            for idx, comment in enumerate(new_comments[:2], 1):
                                author = comment.get('author', 'Аноним') or 'Аноним'
                                text = comment.get('text', '') or ''
                                text_preview = text[:100] + '...' if len(text) > 100 else text
                                logger.info(f"  Пример #{idx}: Автор='{author}' | Текст='{text_preview}'")
                        
                        # Добавляем только уникальные комментарии (сократили итерации)
                        new_count = 0
                        comments_to_process = new_comments[:limit]  # Ограничиваем обработку
                        for comment in comments_to_process:
                            comment_key = f"{comment.get('author', '')}_{comment.get('text', '')[:50]}"
                            comment_id = comment.get('comment_id', '') or comment_key
                            
                            if comment_id not in seen_comment_ids and comment.get('text'):
                                seen_comment_ids.add(comment_id)
                                all_comments.append(comment)
                                new_count += 1
                                
                                if len(all_comments) >= limit:
                                    break
                        
                        if new_count > 0:
                            logger.info(f"Добавлено {new_count} новых уникальных комментариев (всего: {len(all_comments)})")
                            # Делаем скриншот при каждом скролле с новыми комментариями
                            screenshot_path = f"{screenshots_dir}/02_scroll_{i+1:02d}_found_{new_count}_comments.png"
                            await page.screenshot(path=screenshot_path, full_page=False)
                            logger.info(f"📸 Скриншот сохранен: {screenshot_path}")
                            no_new_comments_count = 0
                        else:
                            no_new_comments_count += 1
                            logger.info(f"Новых комментариев не найдено ({no_new_comments_count}/{max_no_new_comments})")
                        
                        # Останавливаемся если достигли лимита или нет новых комментариев
                        if len(all_comments) >= limit:
                            logger.info(f"Достигнут лимит комментариев: {limit}")
                            break
                        
                        if no_new_comments_count >= max_no_new_comments:
                            logger.info(f"Нет новых комментариев {max_no_new_comments} раза подряд, останавливаем скроллинг")
                            break
                    
                    # Финальный скриншот
                    screenshot_path = f"{screenshots_dir}/03_final_state.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    logger.info(f"📸 Финальный скриншот сохранен: {screenshot_path}")
                    
                    # Финальный парсинг для сбора всех комментариев
                    html_content = await page.content()
                    parsed_result = self.parse_comments_from_html(html_content, limit=limit)
                    final_comments = parsed_result.get('comments', [])
                    
                    # Добавляем оставшиеся уникальные комментарии (сократили итерации)
                    comments_to_process = final_comments[:limit]  # Ограничиваем обработку
                    for comment in comments_to_process:
                        comment_key = f"{comment.get('author', '')}_{comment.get('text', '')[:50]}"
                        comment_id = comment.get('comment_id', '') or comment_key
                        
                        if comment_id not in seen_comment_ids and comment.get('text'):
                            seen_comment_ids.add(comment_id)
                            all_comments.append(comment)
                            
                            if len(all_comments) >= limit:
                                break
                    
                    # Ограничиваем до лимита
                    all_comments = all_comments[:limit]
                    
                    result = {
                        "comments": all_comments,
                        "total_count": len(all_comments)
                    }
                    
                finally:
                    await page.close()
                    await context.close()
                    await browser.close()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            comments_count = result.get('total_count', 0)
            comments = result.get('comments', [])
            status = "completed" if comments_count > 0 else "completed_no_comments"
            
            
            # Добавляем метаданные и статус
            result["url"] = url
            result["fetched_at"] = end_time.isoformat()
            result["started_at"] = start_time.isoformat()
            result["duration_seconds"] = round(duration, 2)
            result["method"] = "browser_rendering_incremental"
            result["status"] = status
            result["success"] = True
            
            logger.info(f"Скраппинг завершен: найдено {comments_count} комментариев за {duration:.2f} сек")
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            status = "failed"
            
            logger.error(f"Ошибка скраппинга: {str(e)}")
            
            return {
                "url": url,
                "status": status,
                "success": False,
                "error": str(e),
                "started_at": start_time.isoformat(),
                "fetched_at": end_time.isoformat(),
                "duration_seconds": round(duration, 2),
                "comments": [],
                "total_count": 0
            }
    
    async def fetch_and_parse_comments_from_url(self, url: str, limit: int = 100) -> Dict[str, Any]:
        """
        Загрузить HTML со страницы Facebook через HTTP и распарсить комментарии
        (без использования браузера, только HTTP запрос)
        
        Args:
            url: URL страницы Facebook с комментариями
            limit: Максимальное количество комментариев для извлечения
            
        Returns:
            Словарь с отформатированными комментариями и метаданными
        """
        import httpx
        
        start_time = datetime.now()
        status = "started"
        
        try:
            logger.info(f"Загрузка HTML через HTTP: {url}")
            
            # Загружаем cookies если есть
            cookies_dict = {}
            if self.cookies:
                try:
                    with open(self.cookies, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith('#'):
                                continue
                            parts = line.split('\t')
                            if len(parts) >= 7:
                                domain = parts[0].lstrip('.')
                                name = parts[5]
                                value = parts[6] if len(parts) > 6 else ''
                                if 'facebook.com' in domain:
                                    cookies_dict[name] = value
                except Exception as e:
                    logger.debug(f"Could not load cookies: {e}")
            
            # Пробуем мобильную версию
            mobile_url = url.replace("www.facebook.com", "m.facebook.com")
            
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # headers = {
                #     "User-Agent": self.user_agent,
                #     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                #     "Accept-Language": "en-US,en;q=0.5",
                # }
                headers = {         # Самое важное: свежий User-Agent от iPhone
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                }
                
                try:
                    response = await client.get(mobile_url, headers=headers, cookies=cookies_dict)
                except Exception:
                    # Если мобильная не работает, пробуем обычную
                    try:
                        response = await client.get(url, headers=headers, cookies=cookies_dict)
                    except Exception:
                        response = await client.get(url, headers=headers)
                
                response.raise_for_status()
                html_content = response.text
            
            status = "parsing_comments"
            logger.info("Парсинг комментариев из HTML...")
            result = self.parse_comments_from_html(html_content, limit=limit)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            comments_count = result.get('total_count', 0)
            status = "completed" if comments_count > 0 else "completed_no_comments"
            
            # Добавляем метаданные
            result["url"] = url
            result["fetched_at"] = end_time.isoformat()
            result["started_at"] = start_time.isoformat()
            result["duration_seconds"] = round(duration, 2)
            result["html_size"] = len(html_content)
            result["method"] = "http_request"
            result["status"] = status
            result["success"] = True
            
            logger.info(f"HTTP скрапинг завершен: найдено {comments_count} комментариев за {duration:.2f} сек")
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            status = "failed"
            
            logger.error(f"Ошибка при HTTP скрапинге: {e}")
            
            return {
                "url": url,
                "status": status,
                "success": False,
                "error": str(e),
                "started_at": start_time.isoformat(),
                "fetched_at": end_time.isoformat(),
                "duration_seconds": round(duration, 2),
                "comments": [],
                "total_count": 0
            }
    
