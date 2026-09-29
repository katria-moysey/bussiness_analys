"""
ДЖЕРЕЛО ДАНИХ (як вимагає п.1 завдання):
    https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Northern_Europe
    https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Western_Europe
    https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Eastern_Europe
    https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Southern_Europe

Це чотири статичні статті Вікіпедії, кожна з яких - готовий "підрозділ"
(регіон Європи) з таблицею об'єктів Всесвітньої спадщини ЮНЕСКО (назва,
зображення, розташування, критерії, рік, опис).

ЧОМУ САМЕ ТАК (а не через "хаб"-сторінку зі списком посилань):
    Стаття "Lists_of_World_Heritage_Sites_in_Europe", яка мала б бути
    хабом, останнім часом стала вікі-редиректом на ЗОВСІМ ІНШУ статтю -
    загальний перелік з ~190 посиланнями на КОЖНУ окрему країну світу,
    без гарантії, що в перших країнах за абеткою (Angola, Benin...)
    взагалі є таблиця об'єктів (у деяких країн 0 об'єктів спадщини).
    Тому для стабільності беремо одразу перевірені сторінки регіонів,
    де таблиця гарантовано є і має однакову структуру.

    - "Підрозділи" -> регіони Європи (Northern/Western/Eastern/Southern Europe)
    - "Об'єкти підрозділу" (аналог викладачів) -> пам'ятки Всесвітньої спадщини
"""

import scrapy

from tutorial.items import DivisionItem, HeritageItem


class HeritagesSpider(scrapy.Spider):
    name = "heritages"
    # Сторінки статей - на en.wikipedia.org, але самі файли зображень
    # (мініатюри), на які посилається <img src="...">, роздаються з
    # ОКРЕМОГО хосту thumb.wikimedia.org / upload.wikimedia.org.
    # Без цього домену OffsiteMiddleware мовчки відкидає всі запити
    # ImagesPipeline на завантаження картинок (звідси 0 зображень).
    allowed_domains = ["en.wikipedia.org", "wikimedia.org"]

    start_urls = [
        "https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Northern_Europe",
        "https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Western_Europe",
        "https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Eastern_Europe",
        "https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Southern_Europe",
    ]

    # 5 об'єктів на кожен підрозділ (регіон) - за проханням користувача.
    MAX_ITEMS_PER_DIVISION = 5

    # щоб вивести "перші 1000 символів" (пункт 2) лише один раз, а не 4 рази
    _printed_static_proof = False

    def parse(self, response):
        """Кожна стартова сторінка ОДНОЧАСНО є:
        - підрозділом (пункт 3) - беремо її заголовок і URL;
        - джерелом об'єктів (пункт 4) - парсимо таблицю на цій же сторінці.
        Окремого запиту на "хаб" більше не робимо - це і є фікс нестабільності.
        """
        if not HeritagesSpider._printed_static_proof:
            self.logger.info(
                "ПУНКТ 2: перші 1000 символів HTML (%s):\n%s",
                response.url, response.text[:1000],
            )
            HeritagesSpider._printed_static_proof = True

        # Назва підрозділу - заголовок статті (h1#firstHeading), стабільний
        # елемент для будь-якої сторінки Вікіпедії.
        division_name = "".join(response.css("h1#firstHeading ::text").getall()).strip()
        if not division_name:
            division_name = response.url.rsplit("/", 1)[-1].replace("_", " ")

        yield DivisionItem(name=division_name, url=response.url)

        yield from self._parse_items(response, division_name)

    def _parse_items(self, response, division):
        """ПУНКТ 4: знаходимо потрібну таблицю (Site/Image/Location/...) і
        віддаємо HeritageItem на кожен рядок."""

        rows = None
        for table in response.css("table.wikitable"):
            # ВАЖЛИВО: беремо тільки ПРЯМІ рядки цієї таблиці
            # (table > tbody > tr), а не всі "tr" усередині table.
            # Простий table.css("tr") також ловить рядки будь-якої
            # вкладеної/дочірньої таблиці всередині клітинки - через це
            # заголовок міг братись не з того рядка і всі індекси стовпців
            # (location/criteria/year/description) з'їжджали на 1-2 позиції.
            trs = table.xpath("./tbody/tr") or table.xpath("./tr") or table.css("tr")
            if not trs:
                continue
            # ВАЖЛИВО: заголовок читаємо через "th, td" - і рядки з даними
            # НИЖЧЕ теж читаємо через "th, td" (а не тільки "td"). Раніше
            # заголовок будувався з "th, td", а дані - тільки з "td"; якщо
            # хоч один рядок таблиці мав клітинку як <th> замість <td>
            # (або навпаки), кількість клітинок відрізнялась від кількості
            # заголовків і всі поля (location/criteria/year/description)
            # зсувались одне відносно одного - саме це було видно в логах:
            # location='Natural: (ix)' замість переліку країн і т.д.
            header_texts = [
                "".join(th.css("::text").getall()).strip().lower()
                for th in trs[0].css("th, td")
            ]
            has_site = any("site" in h for h in header_texts)
            has_location = any("location" in h for h in header_texts)
            if has_site and has_location:
                rows = trs
                break

        if not rows:
            self.logger.warning("Таблицю об'єктів не знайдено на %s", response.url)
            return

        headers = [
            "".join(th.css("::text").getall()).strip().lower()
            for th in rows[0].css("th, td")
        ]

        def col(keyword):
            for i, h in enumerate(headers):
                if keyword in h:
                    return i
            return None

        idx_site = col("site")
        idx_image = col("image")
        idx_location = col("location")
        idx_criteria = col("criteria")
        idx_year = col("year")
        idx_description = col("description")

        if idx_site is None:
            idx_site = 0

        n = 0
        for tr in rows[1:]:
            if n >= self.MAX_ITEMS_PER_DIVISION:
                break

            # Та сама зміна: "th, td" замість тільки "td", щоб кількість
            # клітинок завжди відповідала кількості заголовків.
            cells = tr.css("th, td")
            if len(cells) < 2:
                continue  # службові рядки (напр. заголовки трансграничних сайтів)

            title = "".join(cells[idx_site].css("::text").getall()).strip() if idx_site < len(cells) else ""
            if not title:
                continue

            image_url = ""
            if idx_image is not None and idx_image < len(cells):
                src = cells[idx_image].css("img::attr(src)").get()
                if src:
                    image_url = ("https:" + src) if src.startswith("//") else src

            def cell_text(idx):
                if idx is not None and idx < len(cells):
                    return " ".join(cells[idx].css("::text").getall()).strip()
                return ""

            n += 1
            yield HeritageItem(
                division=division,
                title=title,
                location=cell_text(idx_location),
                criteria=cell_text(idx_criteria),
                year=cell_text(idx_year),
                description=cell_text(idx_description),
                page_url=response.url,
                image_urls=[image_url] if image_url else [],
            )

        self.logger.info("[%s] зібрано об'єктів: %d", division, n)
