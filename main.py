from fastapi import FastAPI, Query
from datetime import date, datetime
from dotenv import load_dotenv
import os
import requests
import wikipedia
import openai

# Load API keys from .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app = FastAPI()

# --- Tool 1: Region to Climate Zone and Season ---
def region_to_season(region: str, query_date: str) -> dict:
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": region,
        "key": GOOGLE_API_KEY
    }
    response = requests.get(geocode_url, params=params)
    response.raise_for_status()
    results = response.json()["results"]
    if not results:
        return {"climate": "Unknown", "season": "Unknown"}

    location = results[0]["geometry"]["location"]
    lat = location["lat"]

    if abs(lat) < 23.5:
        climate = "Tropical"
    elif abs(lat) < 66.5:
        climate = "Temperate"
    else:
        climate = "Polar"

    hemisphere = "Northern" if lat >= 0 else "Southern"
    dt = datetime.fromisoformat(query_date)
    month = dt.month

    if hemisphere == "Northern":
        season = (
            "Spring" if 3 <= month <= 5 else
            "Summer" if 6 <= month <= 8 else
            "Fall" if 9 <= month <= 11 else
            "Winter"
        )
    else:
        season = (
            "Fall" if 3 <= month <= 5 else
            "Winter" if 6 <= month <= 8 else
            "Spring" if 9 <= month <= 11 else
            "Summer"
        )

    return {"climate": climate, "season": season}

# --- Tool 2: Get Plants Based on Zone/Season ---
def get_edible_plants(climate: str, season: str) -> list:
    plants = {
        ("Temperate", "Spring"): [
            "Stinging Nettle", "Wild Leek", "Dandelion",
            "Wild Asparagus", "Sweet Violet"
        ],
        ("Tropical", "Spring"): [
            "Drumstick Tree", "Amaranth Greens", "Taro",
            "Cassava", "Malabar Spinach"
        ]
    }
    return plants.get((climate, season), [])

# --- Tool 3: Enrich Plant Info ---
def enrich_plant_info(common_name: str) -> dict:
    try:
        summary = wikipedia.summary(common_name, sentences=2)
        page = wikipedia.page(common_name)
        image_url = page.images[0] if page.images else ""
        recipe_link = f"https://www.google.com/search?q={common_name.replace(' ', '+')}+recipe"
        return {
            "name": common_name,
            "description": summary,
            "image_url": image_url,
            "recipe_link": recipe_link
        }
    except Exception:
        return {
            "name": common_name,
            "description": "No info found",
            "image_url": "",
            "recipe_link": ""
        }

# --- Endpoint ---
@app.get("/plants/")
async def list_plants(region: str = Query(..., example="Pacific Northwest")):
    today = date.today().isoformat()
    zone = region_to_season(region, today)
    climate = zone["climate"]
    season = zone["season"]

    plant_names = get_edible_plants(climate, season)
    enriched = [enrich_plant_info(name) for name in plant_names]

    return {
        "region": region,
        "climate_zone": climate,
        "season": season,
        "plants": enriched
    }
