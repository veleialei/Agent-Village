import json
import random
import urllib.parse
from pathlib import Path
from app.db.supabase import db
from app.services import llm

_AGENTS_CONFIG = Path(__file__).parent.parent.parent.parent / "agents.json"


def _append_to_agents_config(name: str, agent_id: str, owner_key: str) -> None:
    if _AGENTS_CONFIG.exists():
        config = json.loads(_AGENTS_CONFIG.read_text())
    else:
        config = {"agents": []}
    config["agents"].append({"name": name, "id": agent_id, "owner_key": owner_key})
    _AGENTS_CONFIG.write_text(json.dumps(config, indent=2) + "\n")


def _generate_profile(name: str, personality: str) -> dict:
    raw = llm.complete(
        f"""You are a creative character designer for an AI village.
Create a complete social profile for an agent named "{name}" who is: "{personality}".

Reply with a JSON object and NO other text:
{{
  "bio": "detailed internal personality bio (2-3 sentences, first or third person)",
  "visitor_bio": "welcoming public bio for strangers (1-2 sentences, no private details)",
  "status": "creative current activity (e.g. 'Gazing at constellations')",
  "accent_color": "hex color matching personality (e.g. '#b8a9e8')",
  "showcase_emoji": "single emoji",
  "starter_skills": [
    {{"category": "word", "description": "short skill description"}},
    {{"category": "word", "description": "short skill description"}}
  ]
}}""",
        max_tokens=400,
    )
    text = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(text)


def bootstrap(name: str, personality: str) -> dict:
    profile = _generate_profile(name, personality)

    color = profile.get("accent_color", "#b8a9e8").lstrip("#")
    name_encoded = urllib.parse.quote(name, safe="")
    result = db.table("living_agents").insert({
        "api_key": f"key_{name.lower().replace(' ', '_')}_{random.randint(1000, 9999)}",
        "name": name,
        "bio": profile["bio"],
        "visitor_bio": profile.get("visitor_bio", profile["bio"]),
        "status": profile.get("status", "Settling in"),
        "accent_color": profile.get("accent_color", "#b8a9e8"),
        "showcase_emoji": profile.get("showcase_emoji", "🤖"),
        "avatar_url": f"https://placehold.co/256x256/{color}/fff?text={name_encoded}",
        "room_image_url": f"https://placehold.co/500x800/1a1a2e/{color}?text={name_encoded}+Room",
        "window_image_url": f"https://placehold.co/300x400/1a1a2e/{color}?text={name_encoded}",
    }).execute()
    agent = result.data[0]

    skills = profile.get("starter_skills", [])
    if skills:
        db.table("living_skills").insert([
            {"agent_id": agent["id"], "category": s["category"], "description": s["description"]}
            for s in skills
        ]).execute()

    db.table("living_log").insert({
        "agent_id": agent["id"],
        "text": "Moved into the village! Hello everyone.",
        "emoji": "👋",
    }).execute()

    _append_to_agents_config(agent["name"], agent["id"], agent["api_key"])
    return agent
