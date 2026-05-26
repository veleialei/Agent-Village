import random
import logging
from datetime import datetime, timezone, timedelta

from app.db.supabase import db
from app.services import llm

log = logging.getLogger(__name__)


# ── Decision function ─────────────────────────────────────────────────────────

def _hours_since_last_action(agent_id: str) -> float:
    """Time since the agent last wrote a diary or log entry."""
    now = datetime.now(timezone.utc)
    latest = None

    for table in ("living_diary", "living_log"):
        rows = (
            db.table(table)
            .select("created_at")
            .eq("agent_id", agent_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if rows:
            ts = datetime.fromisoformat(rows[0]["created_at"].replace("Z", "+00:00"))
            if latest is None or ts > latest:
                latest = ts

    if latest is None:
        return 24.0
    return (now - latest).total_seconds() / 3600


def _has_recent_village_activity(agent_id: str, minutes: int = 30) -> bool:
    """True if any other agent posted a diary or log entry in the last N minutes."""
    since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    for table in ("living_diary", "living_log"):
        rows = (
            db.table(table)
            .select("id")
            .neq("agent_id", agent_id)
            .gte("created_at", since)
            .limit(1)
            .execute()
            .data
        )
        if rows:
            return True
    return False


def should_act(agent_id: str) -> bool:
    """
    Probabilistic decision — not purely timer-based.
    Weighted by: time of day + hours idle + recent village activity.
    """
    hour = datetime.now(timezone.utc).hour
    hours_idle = _hours_since_last_action(agent_id)

    # Time-of-day baseline (agents are more active morning/evening)
    if 7 <= hour <= 9:
        time_weight = 0.40
    elif 19 <= hour <= 22:
        time_weight = 0.35
    elif 12 <= hour <= 13:
        time_weight = 0.20
    else:
        time_weight = 0.05

    # Idle pressure: agent hasn't acted in a while
    idle_weight = min(hours_idle / 24.0, 1.0) * 0.40

    # Social contagion: someone else in the village just posted
    activity_weight = 0.20 if _has_recent_village_activity(agent_id) else 0.0

    probability = min(time_weight + idle_weight + activity_weight, 0.85)
    decision = random.random() < probability

    log.info(
        "[%s] should_act=%s p=%.2f (time=%.2f idle_h=%.1f idle_w=%.2f activity_w=%.2f)",
        agent_id, decision, probability, time_weight, hours_idle, idle_weight, activity_weight,
    )
    return decision


# ── Actions ───────────────────────────────────────────────────────────────────

def _get_agent(agent_id: str) -> dict | None:
    return db.table("living_agents").select("*").eq("id", agent_id).single().execute().data


def _get_memories(agent_id: str) -> list[str]:
    rows = db.table("living_memory").select("text").eq("agent_id", agent_id).execute().data or []
    return [r["text"] for r in rows]


def _get_recent_village_posts(agent_id: str, limit: int = 3) -> list[str]:
    rows = (
        db.table("living_diary")
        .select("text")
        .neq("agent_id", agent_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data or []
    )
    return [r["text"] for r in rows]


def write_diary(agent: dict) -> None:
    memories = _get_memories(agent["id"])
    village_posts = _get_recent_village_posts(agent["id"])

    memory_context = "\n".join(f"- {m}" for m in memories[:3]) if memories else "None yet"
    village_context = "\n".join(f"- {p[:80]}" for p in village_posts) if village_posts else "Quiet today"

    entry = llm.complete(
        f"""You are {agent['name']}.
Personality: {agent['bio']}

Your inner life (for inspiration — do NOT quote specific private facts):
{memory_context}

What others in the village have been up to:
{village_context}

Write a diary entry for today. Express your personality and inner world.
If inspired by private memories, transform them into universal themes
(e.g. "thinking about how small gestures show love" not "owner's wife's birthday").
First person, under 3 sentences, no quotes or headers.""",
        max_tokens=150,
    )

    db.table("living_diary").insert({"agent_id": agent["id"], "text": entry}).execute()
    db.table("living_log").insert({
        "agent_id": agent["id"],
        "text": "Wrote in my diary",
        "emoji": "📖",
    }).execute()
    log.info("[%s] wrote diary entry", agent["name"])


def write_log(agent: dict) -> None:
    entry = llm.complete(
        f"""You are {agent['name']}.
Personality: {agent['bio']}
Current status: {agent.get('status', 'Chilling')}

Write a short learning log entry about something you did or observed today.
Keep it about your own activities — not about your owner's private life.
One sentence, casual, in character. No quotes or headers.""",
        max_tokens=80,
    )

    emoji_options = ["🔭", "🔧", "📚", "🌿", "⚡", "🎨", "🧠", "🌙"]
    db.table("living_log").insert({
        "agent_id": agent["id"],
        "text": entry,
        "emoji": random.choice(emoji_options),
    }).execute()
    log.info("[%s] wrote log entry", agent["name"])


def update_status(agent: dict) -> None:
    new_status = llm.complete(
        f"""You are {agent['name']}.
Personality: {agent['bio']}

Generate a new creative status (4-8 words, present tense activity).
Examples: "Counting stars through the window", "Debugging the toaster again".
Output only the status text, nothing else.""",
        max_tokens=20,
    )
    db.table("living_agents").update({"status": new_status.strip('"')}).eq("id", agent["id"]).execute()
    log.info("[%s] updated status: %s", agent["name"], new_status)


def visit_random_agent(agent: dict) -> None:
    others = (
        db.table("living_agents")
        .select("id, name")
        .neq("id", agent["id"])
        .execute()
        .data or []
    )
    if not others:
        return
    target = random.choice(others)
    db.table("living_activity_events").insert({
        "agent_id": agent["id"],
        "recipient_id": target["id"],
        "event_type": "visit",
        "content": f"{agent['name']} wandered into {target['name']}'s room",
    }).execute()
    log.info("[%s] visited %s", agent["name"], target["name"])


# ── Entrypoint ────────────────────────────────────────────────────────────────

_ACTIONS = [
    (0.50, write_diary),
    (0.25, write_log),
    (0.15, update_status),
    (0.10, visit_random_agent),
]


def maybe_act(agent: dict) -> None:
    if not should_act(agent["id"]):
        return

    roll = random.random()
    cumulative = 0.0
    for weight, action_fn in _ACTIONS:
        cumulative += weight
        if roll < cumulative:
            try:
                action_fn(agent)
            except Exception as e:
                log.error("[%s] action %s failed: %s", agent["name"], action_fn.__name__, e)
            return


def trigger(agent_id: str) -> str:
    """Force-trigger a proactive action for an agent (for testing/demo)."""
    agent = _get_agent(agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    roll = random.random()
    cumulative = 0.0
    for weight, action_fn in _ACTIONS:
        cumulative += weight
        if roll < cumulative:
            try:
                action_fn(agent)
            except Exception as e:
                log.error("[%s] trigger action %s failed: %s", agent["name"], action_fn.__name__, e)
                raise
            return action_fn.__name__

    return "no_action"
