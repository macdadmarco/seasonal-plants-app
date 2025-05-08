from fastapi import FastAPI, Query
from openai_agents import Agent, Tool, OpenAI
from datetime import date, datetime
from dotenv import load_dotenv
import os
import requests
import wikipedia

load_dotenv()

app = FastAPI()
openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def region_to_season(region: str, query_date: str) -> str:
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": region,
        "key": os.getenv("GOOGLE_API_KEY")
    }
    response = requests.get(geocode_url, params=params)
    response.raise_for_status()
    results = response.json()["results"]
    if not results:
        return "Unknown region"

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
        if 3 <= month <= 5:
            season = "Spring"
        elif 6 <= month <= 8:
            season = "Summer"
        elif 9 <= month <= 11:
            season = "Fall"
        else:
            season = "Winter"
    else:
        if 3 <= month <= 5:
            season = "Fall"
        elif 6 <= month <= 8:
            season = "Winter"
        elif 9 <= month <= 11:
            season = "Spring"
        else:
            season = "Summer"

    return f"{climate} zone, {season}"

region_mapper = Tool(
    name="region_mapper",
    func=region_to_season,
    description="Given a region string and date, returns the climate zone and current season."
)

def get_edible_plants(climate_zone: str, season: str) -> list:
    plants = {
        ("Temperate", "Spring"): [
            {"name": "Urtica dioica", "common": "Stinging Nettle"},
            {"name": "Allium tricoccum", "common": "Wild Leek"},
            {"name": "Taraxacum officinale", "common": "Dandelion"},
            {"name": "Asparagus officinalis", "common": "Wild Asparagus"},
            {"name": "Viola odorata", "common": "Sweet Violet"},
        ],
        ("Tropical", "Spring"): [
            {"name": "Moringa oleifera", "common": "Drumstick Tree"},
            {"name": "Amaranthus spp.", "common": "Amaranth Greens"},
            {"name": "Colocasia esculenta", "common": "Taro"},
            {"name": "Manihot esculenta", "common": "Cassava"},
            {"name": "Basella alba", "common": "Malabar Spinach"},
        ]
    }
    return plants.get((climate_zone, season), [])

plant_finder = Tool(
    name="plant_finder",
    func=get_edible_plants,
    description="Given a climate zone and season, returns a list of edible plants in season."
)

SYSTEM_PROMPT = """
You are a foraging assistant. When given a region and a date, you must:
1. Call the 'region_mapper' tool to get climate zone & season.
2. Call the 'plant_finder' tool with the zone and season.
3. Return a JSON array of the plants: [{name, common_name}...].
"""

agent = Agent(
    name="ForagingAgent",
    tools=[region_mapper, plant_finder],
    llm=openai.chat.completions,
    system_message=SYSTEM_PROMPT,
)

def enrich_plant_info(common_name: str) -> dict:
    try:
        summary = wikipedia.summary(common_name, sentences=2)
        page = wikipedia.page(common_name)
        image_url = page.images[0] if page.images else ""
        recipe_link = f"https://www.google.com/search?q={common_name}+recipe"
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

@app.get("/plants/")
async def list_plants(region: str = Query(..., example="Pacific Northwest, USA")):
    today = date.today().isoformat()
    response = await agent.run({
        "region": region,
        "date": today
    })

    enriched_plants = []
    for plant in response:
        enriched = enrich_plant_info(plant.get("common", plant.get("name")))
        enriched_plants.append(enriched)

    return enriched_plants
