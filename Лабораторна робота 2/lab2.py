from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


TARGET_URL = "https://www.wtatennis.com/"
OUTPUT_FILE = Path("wta_home.csv")
ALL_DATA_FILE = Path("wta_all_data.json")
FIELDNAMES = ["section", "type", "category", "title", "published", "duration", "url"]
CONTENT_LINK_RE = re.compile(r"/(?:news|videos)/\d+/")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

EXTRACT_JS = r"""
() => {
  const linkRe = /\/(news|videos)\/\d+\//;
  const timeRe = /\b\d+\s?(?:m|h|d|w|mo|y)\s+ago\b/i;
  const durRe  = /^\d{1,2}:\d{2}(?::\d{2})?$/;
  const SECTIONS = ['today in tennis', 'wta spotlight', 'must-watch stories',
                    'exclusive content', 'explore collections'];
  const h2s = [...document.querySelectorAll('h2')].filter(h =>
    SECTIONS.includes(h.innerText.trim().toLowerCase()));
  const out = [];
  const seen = new Set();

  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.href;
    if (!linkRe.test(href)) continue;

    const card = a.closest('li, article') || a.parentElement;
    let section = 'Hero';
    for (const h of h2s) {
      if (h.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING) {
        section = h.innerText.trim() || section;
      }
    }

    const heading = card && card.querySelector('h1, h2, h3, h4');
    const title = (a.getAttribute('title') || (heading && heading.innerText) ||
                   a.innerText || '').trim().replace(/\s+/g, ' ')
                   .replace(/\s*(Read More|Watch Now|Register to view)$/i, '');
    if (!title) continue;

    if (seen.has(href)) continue;
    seen.add(href);

    const text = card ? card.innerText : '';
    const lines = text.split('\n').map(s => s.trim()).filter(Boolean);
    const published = (lines.find(l => timeRe.test(l)) || '').match(timeRe);
    const duration  = lines.find(l => durRe.test(l)) || '';

    // категорія — це інше посилання в картці на /news/<слово> або /videos/<слово>
    let category = '';
    if (card) {
      for (const l of card.querySelectorAll('a[href]')) {
        if (/\/(news|videos)\/[a-z\-]+\/?$/.test(l.href) && l.innerText.trim()) {
          category = l.innerText.trim();
          break;
        }
      }
    }

    out.push({
      section,
      type: href.includes('/videos/') ? 'video' : 'news',
      category,
      title,
      published: published ? published[0] : '',
      duration,
      url: href,
    });
  }
  return out;
}
"""


def count_links_without_js() -> tuple[int, bool, str]:
    req = urllib.request.Request(TARGET_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    urls = set(re.findall(r'href="([^"]*?/(?:news|videos)/\d+/[^"]*)"', html))
    return len(urls), "Loading videos" in html, html


def scroll_to_bottom(page, step: int = 500, pause_ms: int = 350, max_steps: int = 80) -> None:
    for _ in range(max_steps):
        page.mouse.wheel(0, step)
        page.wait_for_timeout(pause_ms)
        at_bottom = page.evaluate(
            "window.innerHeight + window.scrollY >= document.body.scrollHeight - 5"
        )
        if at_bottom:
            break
    page.evaluate("window.scrollTo(0, 0)")


def flatten(obj, prefix: str = "", depth: int = 3) -> dict:
    flat = {}
    if isinstance(obj, dict) and depth > 0:
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                flat.update(flatten(v, key, depth - 1))
            elif isinstance(v, (str, int, float, bool)) or v is None:
                flat[key] = v
    return flat


def find_items(data) -> list[dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("content", "tournaments", "items", "data", "results"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


def scrape_home(limit: int | None, headless: bool, timeout_ms: int = 25000):
    api_calls: list[str] = []
    api_responses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=UA, viewport={"width": 1366, "height": 900})
        def on_response(resp):
            try:
                ctype = resp.headers.get("content-type", "")
                if "json" in ctype and resp.request.resource_type in ("xhr", "fetch"):
                    api_calls.append(resp.url)
                    if "api.wtatennis.com" in resp.url:
                        api_responses.append(resp)
            except Exception:
                pass

        page.on("response", on_response)

        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_selector("h2", timeout=timeout_ms, state="attached")
            print("Сторінку завантажено, заголовки секцій знайдено.")

            scroll_to_bottom(page)
            try:
                page.get_by_text("Must-Watch Stories").first.scroll_into_view_if_needed(timeout=5000)
            except Exception:
                pass
            try:
                page.wait_for_function(
                    "!document.body.innerText.includes('Loading videos')",
                    timeout=15000,
                )
                print(" Заглушка 'Loading videos' зникла — відео підвантажено JS.")
            except PlaywrightTimeoutError:
                print("[WARN] 'Loading videos' не зникла (блок може вимагати видимого вікна: --show-browser).")

            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass

        except PlaywrightTimeoutError:
            print("[WARN] Сторінка не завантажилась за відведений час.")
            browser.close()
            return [], api_calls, {}

        cards = page.evaluate(EXTRACT_JS)
        api_data: dict[str, object] = {}
        for resp in api_responses:
            try:
                api_data[resp.url] = resp.json()
            except Exception:
                pass
        browser.close()

    if limit is not None:
        cards = cards[:limit]
    return cards, api_calls, api_data


def save_to_csv(rows: list[dict], path: Path, fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = []
        for r in rows:
            for k in r:
                if k not in fieldnames:
                    fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
    print(f"Збережено в файл .json")


def save_all_in_one(cards, tournaments, api_data, static_count, raw_has_loading) -> None:
    by_section: dict[str, int] = {}
    for c in cards:
        by_section[c["section"]] = by_section.get(c["section"], 0) + 1

    payload = {
        "meta": {
            "url": TARGET_URL,
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "links_without_js": static_count,
            "cards_with_js": len(cards),
            "loading_placeholder_in_raw_html": raw_has_loading,
            "cards_by_section": by_section,
            "tournaments_count": len(tournaments),
            "api_requests": list(api_data.keys()),
        },
        "cards": cards,
        "tournaments": tournaments,
        "api_raw": api_data,
    }
    ALL_DATA_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Збір даних з головної сторінки WTA")
    parser.add_argument("--limit", type=int, default=None, help="Максимум карток (за замовчуванням — усі).")
    parser.add_argument("--show-browser", action="store_true", help="Показати вікно браузера.")
    args = parser.parse_args()

    print(f"Сторінка: {TARGET_URL}\n")

    has_loading = None
    uniq: list[dict] = []
    raw_html = ""
    try:
        static_count, has_loading, raw_html = count_links_without_js()
        print(f"Посилань на новини/відео в сирому HTML: {static_count}")
    except Exception as e:
        static_count = None
        print(f"Не вдалося отримати сирий HTML: {e}\n")

    # 2) З JS
    cards, api_calls, api_data = scrape_home(limit=args.limit, headless=not args.show_browser)

    if not cards:
        print("Дані не отримано. Перевірте мережу або структуру сторінки.")
        return

    print(f"\nЗібрано карток: {len(cards)}")
    if static_count is not None:
        print(f"Картки новин/відео: без JS {static_count} -> з JS {len(cards)}")

    by_section: dict[str, int] = {}
    for c in cards:
        by_section[c["section"]] = by_section.get(c["section"], 0) + 1
    print("\nКартки за секціями:")
    for name, n in by_section.items():
        print(f"  {name}: {n}")

    unique_api = list(dict.fromkeys(api_calls))
    print(f"\nJSON-запитів (XHR/fetch), які зробила сторінка: {len(unique_api)}")
    for u in unique_api[:10]:
        print("  ", u[:140])
    if api_data:
        tournaments: list[dict] = []
        for url, data in api_data.items():
            if "/tennis/tournaments" in url:
                for item in find_items(data):
                    row = flatten(item)
                    row["_source_url"] = url
                    tournaments.append(row)

        if tournaments:
            uniq, seen = [], set()
            for r in tournaments:
                key = json.dumps({k: v for k, v in r.items() if k != "_source_url"},
                                 sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    uniq.append(r)
            if raw_html:
                name_keys = [k for k in uniq[0] if k.lower().endswith(("title", "name"))]
                if name_keys:
                    nk = name_keys[0]
                    in_html = sum(1 for r in uniq if r.get(nk) and str(r[nk]) in raw_html)
                    print(f" турнірів  у сирому HTML: {in_html} з {len(uniq)}")

    save_all_in_one(cards, uniq, api_data, static_count, has_loading)

    print(f"\nГотово. Карток: {len(cards)}, турнірів: {len(uniq)}")


if __name__ == "__main__":
    main()