# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import csv
import json
import sqlite3
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

from itemadapter import ItemAdapter

from tutorial.items import DivisionItem, HeritageItem

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


class ExportPipeline:
    """ПУНКТИ 3, 4, 5 (текстова частина завдання):
    збирає підрозділи/об'єкти/зображення в пам'яті і в кінці роботи павука
    зберігає їх у .txt, .xml, .json, .csv.

    ВАЖЛИВО: у ITEM_PIPELINES цей пайплайн має мати БІЛЬШИЙ номер, ніж
    scrapy.pipelines.images.ImagesPipeline, щоб на момент обробки тут
    поле item['images'] вже було заповнене результатами завантаження.
    """

    def open_spider(self, spider):
        self.divisions = []
        self.items = []
        self.images = []

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        if isinstance(item, DivisionItem):
            self.divisions.append({"name": adapter["name"], "url": adapter["url"]})

        elif isinstance(item, HeritageItem):
            data = {
                "division": adapter["division"],
                "title": adapter["title"],
                "location": adapter["location"],
                "criteria": adapter["criteria"],
                "year": adapter["year"],
                "description": adapter["description"],
                "page_url": adapter["page_url"],
            }
            self.items.append(data)

            for img in adapter.get("images", []):
                self.images.append({
                    "division": data["division"],
                    "title": data["title"],
                    "image_url": img.get("url", ""),
                    "local_path": str(Path(spider.settings.get("IMAGES_STORE", "")) / img.get("path", "")),
                })

        return item

    def close_spider(self, spider):
        # --- підрозділи: .txt та .xml ---
        with open(OUTPUT_DIR / "divisions.txt", "w", encoding="utf-8") as f:
            for d in self.divisions:
                f.write(f"{d['name']}\t{d['url']}\n")

        root = ET.Element("divisions")
        for d in self.divisions:
            el = ET.SubElement(root, "division")
            ET.SubElement(el, "name").text = d["name"]
            ET.SubElement(el, "url").text = d["url"]
        pretty_xml = minidom.parseString(ET.tostring(root, encoding="utf-8")).toprettyxml(indent="  ")
        with open(OUTPUT_DIR / "divisions.xml", "w", encoding="utf-8") as f:
            f.write(pretty_xml)

        # --- об'єкти: .txt та .json ---
        with open(OUTPUT_DIR / "items.txt", "w", encoding="utf-8") as f:
            for it in self.items:
                f.write(f"{it['division']} | {it['title']} | {it['location']} | {it['year']}\n")
        with open(OUTPUT_DIR / "items.json", "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)

        # --- зображення: .txt та .csv ---
        with open(OUTPUT_DIR / "images.txt", "w", encoding="utf-8") as f:
            for img in self.images:
                f.write(f"{img['title']} | {img['image_url']} | {img['local_path']}\n")
        with open(OUTPUT_DIR / "images.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["division", "title", "image_url", "local_path"])
            writer.writeheader()
            writer.writerows(self.images)

        spider.logger.info(
            "Збережено: %d підрозділів, %d об'єктів, %d зображень",
            len(self.divisions), len(self.items), len(self.images),
        )


class SqlitePipeline:
    """ПУНКТ 6: зберігає всі зібрані дані у базу даних SQLite
    (три пов'язані таблиці: divisions, items, images)."""

    def open_spider(self, spider):
        self.connection = sqlite3.connect(OUTPUT_DIR / "database.sqlite3")
        self.cursor = self.connection.cursor()
        self.cursor.executescript("""
            DROP TABLE IF EXISTS images;
            DROP TABLE IF EXISTS items;
            DROP TABLE IF EXISTS divisions;

            CREATE TABLE divisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE
            );
            CREATE TABLE items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                division_id INTEGER,
                title TEXT NOT NULL,
                location TEXT,
                criteria TEXT,
                year TEXT,
                description TEXT,
                FOREIGN KEY (division_id) REFERENCES divisions(id)
            );
            CREATE TABLE images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                image_url TEXT,
                local_path TEXT,
                FOREIGN KEY (item_id) REFERENCES items(id)
            );
        """)
        self.connection.commit()
        self.division_ids = {}
        spider.logger.info("SQLite: базу даних ініціалізовано (%s)", OUTPUT_DIR / "database.sqlite3")

    def close_spider(self, spider):
        self.connection.commit()
        self.connection.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        if isinstance(item, DivisionItem):
            self.cursor.execute(
                "INSERT OR IGNORE INTO divisions (name, url) VALUES (?, ?)",
                (adapter["name"], adapter["url"]),
            )
            self.connection.commit()
            self.cursor.execute("SELECT id FROM divisions WHERE url = ?", (adapter["url"],))
            row = self.cursor.fetchone()
            if row:
                self.division_ids[adapter["name"]] = row[0]

        elif isinstance(item, HeritageItem):
            division_id = self.division_ids.get(adapter["division"])
            self.cursor.execute(
                """INSERT INTO items (division_id, title, location, criteria, year, description)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (division_id, adapter["title"], adapter["location"], adapter["criteria"],
                 adapter["year"], adapter["description"]),
            )
            item_id = self.cursor.lastrowid

            for img in adapter.get("images", []):
                self.cursor.execute(
                    "INSERT INTO images (item_id, image_url, local_path) VALUES (?, ?, ?)",
                    (item_id, img.get("url", ""), img.get("path", "")),
                )
            self.connection.commit()

        return item
