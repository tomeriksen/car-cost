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
import sys
import hashlib
import json

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache.json")

def _load_cache() -> dict:
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_cache(cache: dict) -> None:
    with open(_CACHE_FILE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

_cache: dict = _load_cache()

# Flush stdout immediately so logs appear in Render/cloud dashboards
os.environ.setdefault("PYTHONUNBUFFERED", "1")
sys.stdout.reconfigure(line_buffering=True)

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
    content = (data.get("content") or "").strip()
    mode    = data.get("mode", "blocket")

    if not content:
        return jsonify({"error": "Inget innehåll angivet."}), 400

    from datetime import date
    current_year = date.today().year

    try:
        if mode == "blocket" and content.startswith(("http://", "https://")):
            listing_text = fetch_blocket(content)
            prompt = f"Aktuellt år: {current_year}\n\nBlocket-annons:\n{listing_text}"
        else:
            # manuell eller klistrad annonstext
            prompt = f"Aktuellt år: {current_year}\n\n{content}"

        cache_key = hashlib.md5(prompt.encode()).hexdigest()
        if cache_key in _cache:
            print(f">>> cache hit {cache_key[:8]}", flush=True)
            return jsonify(_cache[cache_key])

        provider = get_provider()
        result = provider.analyze_car(prompt)
        _cache[cache_key] = result
        _save_cache(_cache)
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




if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=True
    )