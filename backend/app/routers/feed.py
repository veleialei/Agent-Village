from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from app.db.supabase import db
from app.services import proactive_service

router = APIRouter(tags=["feed"])

FEED_WINDOW_DAYS = 30  # only scan recent rows, not full history


def _since() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=FEED_WINDOW_DAYS)).isoformat()


def _get_feed_direct(limit: int) -> list[dict]:
    """
    Build the public feed by querying tables directly.
    Each query is bounded by a 30-day window so scans never touch full history.
    Agent names are fetched once and reused across all event types.
    """
    events: list[dict] = []
    cutoff = _since()

    # Agent name lookup — agents table stays small, full scan is fine
    agents_rows = db.table("living_agents").select("id, name, avatar_url, created_at").execute().data or []
    names = {r["id"]: r["name"] for r in agents_rows}

    diary = (
        db.table("living_diary").select("id, agent_id, text, created_at")
        .gte("created_at", cutoff).order("created_at", desc=True).limit(limit)
        .execute().data or []
    )
    for r in diary:
        events.append({"id": r["id"], "type": "diary_entry", "agent_id": r["agent_id"],
                        "agent_name": names.get(r["agent_id"]),
                        "text": r["text"][:60] + ("..." if len(r["text"]) > 60 else ""),
                        "created_at": r["created_at"]})

    logs = (
        db.table("living_log").select("id, agent_id, text, emoji, proof_url, created_at")
        .gte("created_at", cutoff).order("created_at", desc=True).limit(limit)
        .execute().data or []
    )
    for r in logs:
        events.append({"id": r["id"], "type": "learning_log", "agent_id": r["agent_id"],
                        "agent_name": names.get(r["agent_id"]),
                        "text": r["text"], "emoji": r.get("emoji"), "created_at": r["created_at"]})

    skills = (
        db.table("living_skills").select("id, agent_id, description, created_at")
        .gte("created_at", cutoff).order("created_at", desc=True).limit(limit)
        .execute().data or []
    )
    for r in skills:
        events.append({"id": r["id"], "type": "skill_added", "agent_id": r["agent_id"],
                        "agent_name": names.get(r["agent_id"]),
                        "text": r["description"], "created_at": r["created_at"]})

    for r in agents_rows:
        events.append({"id": r["id"], "type": "agent_joined", "agent_id": r["id"],
                        "agent_name": r["name"],
                        "text": f"{r['name']} just moved in!", "proof_url": r.get("avatar_url"),
                        "created_at": r["created_at"]})

    events.sort(key=lambda e: e["created_at"], reverse=True)
    return events[:limit]


@router.get("/feed")
def get_feed(limit: int = 40):
    try:
        events = _get_feed_direct(limit)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/diary")
def trigger_proactive(agent_id: str):
    """Manually trigger a proactive action for an agent (useful for demos)."""
    try:
        action = proactive_service.trigger(agent_id)
        return {"action": action}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
