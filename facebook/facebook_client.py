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
    PLAYWRIGHT_AVAILABLE = True
except ImportError as e:
    logger.error(f"Playwright не установлен. Ошибка импорта: {e}")
    logger.error("Установите: pip install playwright && python -m playwright install chromium")
    async_playwright = None
    Browser = None
    Page = None
    PLAYWRIGHT_AVAILABLE = False


class FacebookScraperClient:
    """Клиент для работы с Facebook через Playwright скрейпинг"""
    
    def __init__(self, cookies: Optional[str] = None, user_agent: Optional[str] = None, 
                 browser_channel: Optional[str] = None, browser_executable_path: Optional[str] = None,
                 user_data_dir: Optional[str] = None):
        """
        Инициализация клиента
        
        Args:
            cookies: Путь к файлу с cookies (опционально, для обхода ограничений)
            user_agent: User-Agent для запросов (опционально)
            browser_channel: Канал браузера для использования (например, "chrome", "msedge", "chrome-beta")
                           Доступные варианты: "chrome", "chrome-beta", "msedge", "msedge-beta", "msedge-dev"
                           Если не указан и используется user_data_dir, по умолчанию будет "chrome"
            browser_executable_path: Путь к исполняемому файлу браузера (если нужно использовать конкретный браузер)
            user_data_dir: Путь к директории профиля браузера (user data directory)
                          Позволяет использовать существующий профиль Chrome со всеми cookies и настройками
                          Например: "~/Library/Application Support/Google/Chrome/Default" для macOS
                          Если указан, будет использован persistent context
        """
        self.cookies = cookies
        self.browser_channel = browser_channel
        self.browser_executable_path = browser_executable_path
        self.user_data_dir = user_data_dir
        
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
    
    def _get_launch_options(self) -> Dict[str, Any]:
        """
        Получить настройки для запуска браузера (используется только в обычном режиме, не для persistent context)
        
        Returns:
            Словарь с настройками запуска браузера
        """
        launch_options = {"headless": False}
        
        # browser_channel и browser_executable_path взаимоисключающие
        # Приоритет у browser_executable_path, если указан
        if self.browser_executable_path:
            launch_options["executable_path"] = self.browser_executable_path
        elif self.browser_channel:
            launch_options["channel"] = self.browser_channel
        
        return launch_options
    
    def _get_context_options(self, for_persistent_context: bool = False) -> Dict[str, Any]:
        """
        Получить настройки для контекста браузера
        
        Args:
            for_persistent_context: Если True, добавляет channel для persistent context
        
        Returns:
            Словарь с настройками контекста браузера
        """
        # headless не передается в context_options, только в launch_options
        context_options = {
            "user_agent": self.user_agent,
            "viewport": {"width": 1920, "height": 1080}
        }
        
        # Для persistent context добавляем канал браузера
        # В обычном режиме channel не нужен в context_options (он в launch_options)
        if for_persistent_context:
            if self.browser_channel:
                context_options["channel"] = self.browser_channel
            else:
                # По умолчанию используем Chrome для persistent context
                context_options["channel"] = "chrome"
        
        return context_options
    
    async def initialize_browser(self, playwright_instance) -> tuple:
        """
        Инициализировать браузер с настройками из клиента
        
        Args:
            playwright_instance: Экземпляр Playwright
            
        Returns:
            Кортеж (browser, context, page) или (None, context, page) для persistent context
        """
        if not PLAYWRIGHT_AVAILABLE or async_playwright is None:
            raise ImportError("Playwright не установлен")
        
        playwright_cookies = self._load_cookies_for_playwright()
        
        if self.user_data_dir:
            # Используем persistent context
            user_data_path = os.path.expanduser(self.user_data_dir)
            context_options = self._get_context_options(for_persistent_context=True)
            
            # Для persistent context headless передается отдельно (не в context_options)
            # Используем headless=False по умолчанию (headed режим)
            context_options["headless"] = False
            
            logger.info(f"🌐 Запускаем persistent context с профилем: {user_data_path}")
            logger.info(f"🌐 Браузер: {context_options.get('channel', 'chromium')}")
            
            context = await playwright_instance.chromium.launch_persistent_context(
                user_data_path,
                **context_options
            )
            
            # Добавляем дополнительные cookies из файла
            if playwright_cookies:
                await context.add_cookies(playwright_cookies)
            
            # Получаем первую страницу или создаем новую
            pages = context.pages
            if pages:
                page = pages[0]
            else:
                page = await context.new_page()
            
            return None, context, page
        else:
            # Обычный режим
            launch_options = self._get_launch_options()
            context_options = self._get_context_options(for_persistent_context=False)
            
            if self.browser_executable_path:
                logger.info(f"🌐 Используем браузер из: {self.browser_executable_path}")
            elif self.browser_channel:
                logger.info(f"🌐 Используем браузер: {self.browser_channel}")
            
            browser = await playwright_instance.chromium.launch(**launch_options)
            context = await browser.new_context(**context_options)
            
            if playwright_cookies:
                await context.add_cookies(playwright_cookies)
            
            page = await context.new_page()
            await page.mouse.move(x=500, y=500)

            return browser, context, page
    
    async def open_facebook(self, page: Page, wait_time: int = 3) -> None:
        """
        Открыть Facebook в указанной странице
        
        Args:
            page: Страница Playwright
            wait_time: Время ожидания после загрузки в секундах
        """
        logger.info("🌐 Открываем Facebook...")
        await page.goto("https://www.facebook.com", timeout=30000)
        logger.info("✅ Facebook открыт")
    
    async def fetch_and_parse_comments_with_browser(self, url: str, limit: int = 100, wait_time: int = 5, 
                                                     page: Optional[Page] = None, playwright_instance = None) -> Dict[str, Any]:
        """
        Загрузить страницу через браузер (Playwright) с рендерингом JavaScript и распарсить комментарии
        
        Использует инкрементальный скраппинг: парсит комментарии после каждого скролла,
        собирая уникальные комментарии до достижения лимита.
        
        Args:
            url: URL страницы Facebook с комментариями
            limit: Максимальное количество комментариев для извлечения
            wait_time: Время ожидания загрузки страницы в секундах
            page: Существующая страница Playwright (опционально, если не указана - создается новая)
            playwright_instance: Экземпляр Playwright (опционально, используется только если page не указана)
            

        """
        if not PLAYWRIGHT_AVAILABLE or async_playwright is None:
            import sys
            python_exe = sys.executable
            error_msg = (
                "Playwright не установлен или не может быть импортирован.\n"
                f"Python интерпретатор: {python_exe}\n"
                "Для установки выполните:\n"
                f"  {python_exe} -m pip install playwright\n"
                f"  {python_exe} -m playwright install chromium\n"
                "\nИли убедитесь, что вы используете правильное виртуальное окружение."
            )
            logger.error(error_msg)
            raise ImportError(error_msg)
        
        start_time = datetime.now()
        status = "started"
        
        try:
            logger.info(f"Начало скраппинга: {url} (лимит: {limit})")
            
            # Пробуем мобильную версию
            # mobile_url = url
            mobile_url = url.replace("www.facebook.com", "m.facebook.com")
            logger.info(f"Запустились по адресу {mobile_url}")

            all_comments = []  # Хранилище для всех уникальных комментариев
            seen_comment_ids = set()  # Для отслеживания уникальности
            
            # Если передана существующая страница, используем её
            use_existing_page = page is not None
            
            # if use_existing_page:
            #     logger.info("🔄 Используем существующую страницу браузера")
            #     p = None
            #     browser = None
            #     context = None
            # else:
                # Используем переданный экземпляр Playwright или создаем новый
            if playwright_instance:
                p = playwright_instance
                logger.info("🔄 Используем переданный экземпляр Playwright")
            else:
                p = async_playwright()
                await p.__aenter__()
                logger.info("🆕 Создаем новый экземпляр Playwright")
            
            try:
                if not use_existing_page:
                    status = "initializing_browser"
                    # Используем метод инициализации браузера
                    browser, context, page = await self.initialize_browser(p)
                
                try:
                    # Создаем директорию для скриншотов если её нет
                    screenshots_dir = "screenshots"
                    os.makedirs(screenshots_dir, exist_ok=True)
                    
                    # Загружаем страницу
                    await page.goto(mobile_url, timeout=60000)
                    await page.wait_for_timeout(wait_time * 1000)
                    
                    # Делаем скриншот после загрузки страницы
                    screenshot_path = f"{screenshots_dir}/01_initial_load.png"
                    await page.screenshot(path=screenshot_path, full_page=False)
                    logger.info(f"📸 Скриншот сохранен: {screenshot_path}")
                    
                    # Простой скраппинг: скроллим каждые 5 секунд и парсим комментарии
                    status = "scrolling_and_collecting"
                    
                    scroll_interval = 1000  # 1 секунд между скроллами
                    max_scrolls = 100  # Максимум 100 скролла
                    no_new_comments_count = 0  # Счетчик скроллов без новых комментариев
                    max_no_new_comments = 4  # Останавливаемся после 2 скроллов без новых комментариев
                    
                    for i in range(max_scrolls):
                        logger.info(f"🔄 Скролл #{i+1}/{max_scrolls}")
                        
                        # Получаем позицию до скролла
                        prev_scroll_y = await page.evaluate("window.pageYOffset || window.scrollY || document.documentElement.scrollTop || document.body.scrollTop || 0")
                        
                        # Скролл: скриншот -> к середине -> к последнему -1
                        try:
                            # Ищем все возможные селекторы комментариев Facebook
                            comment_selectors = [
                                '[data-testid="UFI2Comment/root"]',
                                '[role="article"]',
                                '[data-pagelet="CommentList"] [role="article"]',
                                '.userContentWrapper',
                                '[data-ft*="top_level_post_id"]'
                            ]
                            
                            comments = None
                            selector_used = None
                            for selector in comment_selectors:
                                try:
                                    found_comments = await page.query_selector_all(selector)
                                    if found_comments:
                                        comments = found_comments
                                        selector_used = selector
                                        logger.debug(f"Найдено {len(comments)} комментариев через селектор: {selector}")
                                        break
                                except:
                                    continue
                            
                            if comments and len(comments) > 0:
                                # 1. Скриншот вначале (только при первом скролле)
                                if i == 0:
                                    screenshot_path = f"{screenshots_dir}/02_scroll_01_initial.png"
                                    await page.screenshot(path=screenshot_path, full_page=False)
                                    logger.info(f"📸 Скриншот после первого скролла: {screenshot_path}")
                                
                                # 2. Скроллим к середине списка комментариев
                                middle_index = len(comments) // 2
                                if middle_index < len(comments):
                                    middle_comment = comments[middle_index]
                                    await middle_comment.scroll_into_view_if_needed()
                                    await page.wait_for_timeout(scroll_interval)
                                    logger.debug(f"Скролл к середине выполнен (комментарий {middle_index}/{len(comments)})")
                                
                                # 3. Скроллим к последнему -1 элементу (предпоследний)
                                if len(comments) >= 2:
                                    second_last_comment = comments[-2]
                                    await second_last_comment.scroll_into_view_if_needed()
                                    await page.wait_for_timeout(scroll_interval)
                                    logger.debug(f"Скролл к предпоследнему комментарию выполнен ({len(comments)-2}/{len(comments)})")
                            else:
                                # Если не нашли комментарии, ждем
                                logger.debug("Комментарии не найдены, ждем загрузки")
                                await page.wait_for_timeout(scroll_interval)
                        except Exception as e:
                            logger.debug(f"Ошибка при скролле: {e}")
                            await page.wait_for_timeout(scroll_interval)
                        
                        # Дополнительный скролл через body.scrollTop (для некоторых случаев)
                        # await page.evaluate("""
                        #     if (document.body) {
                        #         document.body.scrollTop += 1000;
                        #     }
                        #     if (document.documentElement) {
                        #         document.documentElement.scrollTop += 1000;
                        #     }
                        # """)
                        
                        # Ждем загрузки контента
                        await page.wait_for_timeout(scroll_interval)
                        
                        # Проверяем результат
                        # final_scroll_y = await page.evaluate("window.pageYOffset || window.scrollY || document.documentElement.scrollTop || document.body.scrollTop || 0")
                        # document_height = await page.evaluate("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight, document.documentElement.clientHeight)")
                        # logger.info(f"Скролл: {prev_scroll_y}px -> {final_scroll_y}px, высота: {document_height}px")

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
                    # Закрываем страницу только если мы её создали
                    if not use_existing_page:
                        if page and not page.is_closed():
                            await page.close()
                        
                        # Закрываем context
                        # В случае persistent context закрываем его, в обычном режиме закрываем context и browser
                        if self.user_data_dir:
                            # Для persistent context закрываем только context
                            if context:
                                await context.close()
                        else:
                            # Для обычного режима закрываем context и browser
                            if context:
                                await context.close()
                            if browser:
                                await browser.close()
                        
                        # Закрываем экземпляр Playwright только если мы его создали
                        if p and not playwright_instance:
                            await p.__aexit__(None, None, None)
            except Exception as inner_e:
                # Если произошла ошибка при создании браузера, закрываем ресурсы
                logger.error(f"Ошибка при создании браузера: {inner_e}")
                if not use_existing_page:
                    if 'page' in locals() and page and not page.is_closed():
                        await page.close()
                    if 'context' in locals() and context:
                        await context.close()
                    if 'browser' in locals() and browser:
                        await browser.close()
                    if 'p' in locals() and p and not playwright_instance:
                        await p.__aexit__(None, None, None)
                raise
            
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

    def _load_cookies_for_playwright(self) -> List[Dict[str, Any]]:
        """
        Загрузить cookies из файла в формате для Playwright
        Формат файла: имя_куки значение (через пробел)
        
        Returns:
            Список словарей с cookies для Playwright
        """
        playwright_cookies = []
        
        if not self.cookies:
            logger.debug("Cookies не указаны, работаем без авторизации")
            return playwright_cookies
        
        logger.info(f"📂 Загрузка cookies из файла: {self.cookies}")
        
        try:
            if not os.path.exists(self.cookies):
                logger.warning(f"⚠️  Файл cookies не найден: {self.cookies}")
                return playwright_cookies
            
            with open(self.cookies, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split(None, 1)  # Разделить по первому пробелу
                    if len(parts) == 2:
                        name, value = parts
                        cookie = {
                            "name": name,
                            "value": value,
                            "domain": ".facebook.com",
                            "path": "/",
                            "secure": True,
                        }
                        playwright_cookies.append(cookie)
                        logger.debug(f"   ✅ Загружен cookie: {name}")
            
            logger.info(f"✅ Загружено {len(playwright_cookies)} cookies")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке cookies: {e}", exc_info=True)
        
        return playwright_cookies

    """ **** Parsing methods **** """
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