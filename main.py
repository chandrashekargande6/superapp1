import csv
import json
import random
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def get_driver(headless=True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=opts)
    return driver


def extract_from_obj(obj):
    """
    Extract restaurant details from one JSON-LD object (dict).
    """
    out = []
    if not isinstance(obj, dict):
        return out

    # Case 1: itemListElement container
    if "itemListElement" in obj and isinstance(obj["itemListElement"], list):
        for el in obj["itemListElement"]:
            if isinstance(el, dict):
                item = el.get("item")
                if isinstance(item, dict) and item.get("@type") in ("Restaurant", "LocalBusiness", "Place"):
                    out.append({
                        "name": item.get("name"),
                        "url": item.get("url"),
                        "address": (
                            item.get("address", {}).get("streetAddress")
                            if isinstance(item.get("address"), dict)
                            else item.get("address")
                        ),
                        "rating": item.get("aggregateRating", {}).get("ratingValue")
                            if isinstance(item.get("aggregateRating"), dict)
                            else None,
                        "reviewCount": item.get("aggregateRating", {}).get("reviewCount")
                            if isinstance(item.get("aggregateRating"), dict)
                            else None,
                        #"priceRange": item.get("priceRange")
                    })

    # Case 2: standalone Restaurant object
    if obj.get("@type") == "Restaurant":
        out.append({
            "name": obj.get("name"),
            "url": obj.get("url"),
            "address": (
                obj.get("address", {}).get("streetAddress")
                if isinstance(obj.get("address"), dict)
                else obj.get("address")
            ),
            "rating": obj.get("aggregateRating", {}).get("ratingValue")
                if isinstance(obj.get("aggregateRating"), dict)
                else None,
            "reviewCount": obj.get("aggregateRating", {}).get("reviewCount")
                if isinstance(obj.get("aggregateRating"), dict)
                else None,
            #"priceRange": obj.get("priceRange")
        })

    return out


def parse_restaurants_from_html(html):
    """
    Parse all <script type="application/ld+json"> blocks for restaurants.
    """
    soup = BeautifulSoup(html, "lxml")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    found = []

    for tag in scripts:
        text = (tag.string or tag.text or "").strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, list):
            for part in payload:
                found.extend(extract_from_obj(part))
        else:
            found.extend(extract_from_obj(payload))

    # De-duplicate
    seen = set()
    unique = []
    for r in found:
        key = (r.get("name"), r.get("url"))
        if key not in seen and r.get("name"):
            seen.add(key)
            unique.append(r)
    return unique


def scrape_city(city_slug: str, pages: int = 1, headless: bool = True):
    """
    Scrape restaurant details from Zomato city listing pages.
    """
    driver = get_driver(headless=headless)
    wait = WebDriverWait(driver, 20)
    all_rows = []
    base = "https://www.zomato.com"

    try:
        for p in range(1, pages + 1):
            url = f"https://www.zomato.com/{city_slug}/restaurants?page={p}"
            print(f"Loading: {url}")
            driver.get(url)

            # Wait until JSON-LD is present
            wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'script[type="application/ld+json"]'))
            )
            time.sleep(random.uniform(1.5, 3.0))

            rows = parse_restaurants_from_html(driver.page_source)
            for r in rows:
                if r.get("url", "").startswith("/"):
                    r["url"] = base + r["url"]
                r["city"] = city_slug
                r["page"] = p

            print(f"Page {p}: found {len(rows)} restaurants")
            all_rows.extend(rows)

            time.sleep(random.uniform(2.0, 4.0))
    finally:
        driver.quit()

    return all_rows


def save_to_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["city", "page", "name", "url", "address", "rating", "reviewCount"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows → {path.resolve()}")


from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/scrape", methods=["POST"])
def scrape_endpoint():
    payload = request.get_json(force=True)
    city = payload.get("city", "hyderabad")
    pages = int(payload.get("pages", 1))
    headless = bool(payload.get("headless", True))
    data = scrape_city(city_slug=city, pages=pages, headless=headless)
    return jsonify(data)

if __name__ == "__main__":
    # For local testing only
    app.run(host="0.0.0.0", port=8000)
