# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

from dataclasses import dataclass, field


@dataclass
class DivisionItem:
    """Підрозділ (пункт 3 завдання) — регіон зі списком об'єктів спадщини."""
    name: str = ""
    url: str = ""


@dataclass
class HeritageItem:
    """Об'єкт всередині підрозділу (пункт 4 завдання) — аналог "працівника"."""
    division: str = ""
    title: str = ""
    location: str = ""
    criteria: str = ""
    year: str = ""
    description: str = ""
    page_url: str = ""

    # Ці два поля використовує вбудований scrapy.pipelines.images.ImagesPipeline:
    # image_urls - що качати, images - куди пайплайн запише результат завантаження
    image_urls: list = field(default_factory=list)
    images: list = field(default_factory=list)
