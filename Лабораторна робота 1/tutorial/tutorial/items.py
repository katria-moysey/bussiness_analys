# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

from dataclasses import dataclass, field


@dataclass
class DivisionItem:
    name: str = ""
    url: str = ""


@dataclass
class HeritageItem:
    division: str = ""
    title: str = ""
    location: str = ""
    criteria: str = ""
    year: str = ""
    description: str = ""
    page_url: str = ""
    image_urls: list = field(default_factory=list)
    images: list = field(default_factory=list)
