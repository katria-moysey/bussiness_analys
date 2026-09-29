# Scrapy settings for tutorial project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "tutorial"

# ВИПРАВЛЕНО: реальна назва пакету проєкту - "tutorial" (див. scrapy.cfg),
# а не "heritage".
SPIDER_MODULES = ["tutorial.spiders"]
NEWSPIDER_MODULE = "tutorial.spiders"

ADDONS = {}


# Wikipedia просить ідентифікувати бота описовим User-Agent
# (https://meta.wikimedia.org/wiki/User-Agent_policy). Замініть e-mail на свій.
USER_AGENT = "EducationalScrapingProject/1.0 (student assignment; contact: your_email@example.com)"

# Поважаємо robots.txt Вікіпедії
ROBOTSTXT_OBEY = True

# Ввічлива пауза між запитами (не навантажуємо сервери Wikipedia)
DOWNLOAD_DELAY = 1

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
#DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
#}

# Enable or disable spider middlewares
#SPIDER_MIDDLEWARES = {
#    "tutorial.middlewares.TutorialSpiderMiddleware": 543,
#}

# Enable or disable downloader middlewares
#DOWNLOADER_MIDDLEWARES = {
#    "tutorial.middlewares.TutorialDownloaderMiddleware": 543,
#}

# Enable or disable extensions
#EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
#}

# ВИПРАВЛЕНО: правильні шляхи "tutorial.pipelines...." + правильний порядок:
# 1) ImagesPipeline (100) качає картинки і заповнює item["images"]
# 2) ExportPipeline (200) вже бачить завантажені картинки -> пише .txt/.xml/.json/.csv
# 3) SqlitePipeline (300) пише все у базу даних, включно зі шляхами картинок
ITEM_PIPELINES = {
    "scrapy.pipelines.images.ImagesPipeline": 100,
    "tutorial.pipelines.ExportPipeline": 200,
    "tutorial.pipelines.SqlitePipeline": 300,
}

# Куди ImagesPipeline зберігає завантажені зображення (пункт 5 завдання)
IMAGES_STORE = "output/images"
IMAGES_EXPIRES = 0

# Enable and configure the AutoThrottle extension (disabled by default)
#AUTOTHROTTLE_ENABLED = True
#AUTOTHROTTLE_START_DELAY = 5
#AUTOTHROTTLE_MAX_DELAY = 60
#AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
#AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = "httpcache"
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
