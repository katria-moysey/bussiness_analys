import scrapy

from tutorial.items import DivisionItem, HeritageItem


class HeritagesSpider(scrapy.Spider):
    name = "heritages"
    allowed_domains = ["en.wikipedia.org", "wikimedia.org"]

    start_urls = [
        "https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Northern_Europe",
        "https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Western_Europe",
        "https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Eastern_Europe",
        "https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Southern_Europe",
    ]

    MAX_ITEMS_PER_DIVISION = 5
    _printed_static_proof = False

    def parse(self, response):
        if not HeritagesSpider._printed_static_proof:
            self.logger.info(
                response.url, response.text[:1000],
            )
            HeritagesSpider._printed_static_proof = True

        division_name = "".join(response.css("h1#firstHeading ::text").getall()).strip()
        if not division_name:
            division_name = response.url.rsplit("/", 1)[-1].replace("_", " ")

        yield DivisionItem(name=division_name, url=response.url)

        yield from self._parse_items(response, division_name)

    def _parse_items(self, response, division):


        rows = None
        for table in response.css("table.wikitable"):
            trs = table.xpath("./tbody/tr") or table.xpath("./tr") or table.css("tr")
            if not trs:
                continue
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

            cells = tr.css("th, td")
            if len(cells) < 2:
                continue 

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
