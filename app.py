"""
Bilkalkyl backend — Flask server

Miljövariabler (.env):
  LLM_PROVIDER      openai (default) | anthropic
  LLM_MODEL         override model, t.ex. gpt-4o eller gpt-4o-mini
  OPENAI_API_KEY    krävs för openai
  ANTHROPIC_API_KEY krävs för anthropic

Starta:
  pip install -r requirements.txt
  cp .env.example .env   # och fyll i API-nyckel
  python app.py
"""

import os
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

from llm_providers import get_provider

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@app.route("/")
def index():
    return send_file("bilkalkyl.html")


@app.route("/api/analyze-car", methods=["POST"])
def analyze_car():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "blocket")
    content = (data.get("content") or "").strip()
    miltal = data.get("miltal")

    if not content:
        return jsonify({"error": "Inget innehåll angivet."}), 400

    from datetime import date
    current_year = date.today().year
    miltal_str = f"\n\nMiltal (angivet av användaren): {miltal} mil" if miltal else ""

    try:
        if mode == "regnummer":
            regnr = re.sub(r"[\s\-]", "", content).upper()
            vehicle_text = fetch_vehicle_info(regnr)
            prompt = f"Aktuellt år: {current_year}\n\nRegistreringsnummer: {regnr}\n\nFordonsinformation:\n{vehicle_text}{miltal_str}"
        else:
            if content.startswith(("http://", "https://")):
                listing_text = fetch_blocket(content)
            else:
                listing_text = content
            prompt = f"Aktuellt år: {current_year}\n\nBlocket-annons:\n{listing_text}{miltal_str}"

        provider = get_provider()
        result = provider.analyze_car(prompt)
        return jsonify(result)

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def fetch_blocket(url: str) -> str:
    """Fetch a Blocket listing page and return relevant text."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header", "svg"]):
            tag.decompose()

        # Prefer <main> or <article> over full page
        content = soup.find("main") or soup.find("article") or soup
        lines = content.get_text(separator="\n", strip=True).splitlines()

        # Deduplicate while preserving order, keep non-empty lines
        seen, result_lines = set(), []
        for line in lines:
            s = line.strip()
            if s and s not in seen:
                seen.add(s)
                result_lines.append(s)

        result = "\n".join(result_lines)
        print(">>> EXTRACTED TEXT SENT TO LLM:\n", result[:3000])
        return result[:7000]

    except Exception as exc:
        return f"Kunde inte hämta Blocket-annons ({exc}). Klistra in annonstexten manuellt."




def fetch_vehicle_info(regnr: str) -> str:
    """Fetch Swedish vehicle data from biluppgifter.se."""
    try:
        url = f"https://biluppgifter.se/fordon/{regnr}"
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:4000]
    except Exception as exc:
        return f"Kunde inte hämta fordonsdata ({exc}). Uppskattar baserat på registreringsnumret."


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=True
    )