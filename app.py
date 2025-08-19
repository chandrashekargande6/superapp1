from flask import Flask, jsonify, request
from main import scrape_city  # import your scraper
from pathlib import Path
import threading

app = Flask(__name__)

@app.route("/scrape", methods=["GET"])
def scrape():
    city = request.args.get("city", "hyderabad")
    pages = int(request.args.get("pages", 2))

    # Run scraper in a thread to prevent blocking (optional)
    def run_scraper():
        data = scrape_city(city_slug=city, pages=pages, headless=True)
        # Save to CSV
        save_path = Path(f"data/zomato_{city}_names.csv")
        from main import save_to_csv
        save_to_csv(data, save_path)

    thread = threading.Thread(target=run_scraper)
    thread.start()

    return jsonify({
        "status": "Scraper started",
        "city": city,
        "pages": pages
    })

@app.route("/data/<city>", methods=["GET"])
def get_data(city):
    csv_path = Path(f"data/zomato_{city}_names.csv")
    if not csv_path.exists():
        return jsonify({"error": "Data not found. Please run /scrape first."}), 404

    import csv
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return jsonify(rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
