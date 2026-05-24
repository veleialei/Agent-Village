"""
One-time utility: sync all agents from the database into agents.json.

Run from the backend/ directory:
    python sync_agents_config.py

This is safe to run multiple times — it deduplicates by agent ID.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db.supabase import db

AGENTS_CONFIG = Path(__file__).parent.parent / "agents.json"

result = db.table("living_agents").select("id, name, api_key").order("created_at").execute()
rows = result.data

existing = json.loads(AGENTS_CONFIG.read_text()) if AGENTS_CONFIG.exists() else {"agents": []}
existing_ids = {a["id"] for a in existing["agents"]}

added = 0
for row in rows:
    if row["id"] not in existing_ids:
        existing["agents"].append({"name": row["name"], "id": row["id"], "owner_key": row["api_key"]})
        existing_ids.add(row["id"])
        added += 1
        print(f"  + {row['name']} ({row['id']})")

AGENTS_CONFIG.write_text(json.dumps(existing, indent=2) + "\n")
print(f"\nagents.json updated — {added} agent(s) added, {len(existing['agents'])} total.")
