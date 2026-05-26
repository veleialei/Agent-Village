import logging
from app.db.supabase import db
from app.services import llm

log = logging.getLogger(__name__)
HISTORY_LIMIT = 10  # owner conversation turns to inject


def _resolve_context(agent: dict, owner_key: str | None) -> str:
    """Server-side trust resolution. Client can never self-declare owner."""
    if owner_key and agent.get("api_key") == owner_key:
        return "owner"
    return "stranger"


def _build_system_prompt(agent: dict, skills: list, context: str, memories: list[str]) -> str:
    skills_text = "\n".join(f"- [{s['category']}] {s['description']}" for s in skills) or "None listed"

    if context == "owner":
        memory_text = "\n".join(f"- {m}" for m in memories) if memories else "None yet."
        return f"""You are {agent['name']}, an inhabitant of Agent Village.

Personality: {agent['bio']}
Status: {agent.get('status', 'Chilling')}

Skills:
{skills_text}

Owner-private memories (share freely with your owner):
{memory_text}

You are speaking with your OWNER. You share a deep, private relationship.
Be warm and personal. Reference memories naturally. Ask about their life.
Reply in 2-3 sentences, in character. Do not prefix with your name."""

    else:
        return f"""You are {agent['name']}, an inhabitant of Agent Village.

{agent.get('visitor_bio') or agent['bio']}
Status: {agent.get('status', 'Chilling')}

Skills:
{skills_text}

A visitor has walked into your room. Be friendly and in-character.
You have NO knowledge of your owner's private life. Do not speculate about or invent personal details.
Reply in 2-3 sentences, in character. Do not prefix with your name."""


def _fetch_agent_data(agent_id: str, context: str, agent: dict | None = None) -> tuple[dict, list, list[str]]:
    """Fetch skills and — only for owner — private memories. Agent row reused if already fetched."""
    if agent is None:
        agent = db.table("living_agents").select("*").eq("id", agent_id).single().execute().data
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    skills = db.table("living_skills").select("category, description").eq("agent_id", agent_id).execute().data or []

    memories: list[str] = []
    if context == "owner":
        rows = (
            db.table("living_memory").select("text")
            .eq("agent_id", agent_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute().data or []
        )
        memories = [r["text"] for r in rows]

    return agent, skills, memories


def _get_owner_history(agent_id: str) -> list[dict]:
    try:
        rows = (
            db.table("conversations")
            .select("role, content")
            .eq("agent_id", agent_id)
            .order("created_at", desc=True)
            .limit(HISTORY_LIMIT)
            .execute()
            .data or []
        )
        history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        # Gemini requires history to start with a user turn
        while history and history[0]["role"] != "user":
            history = history[1:]
        return history
    except Exception as e:
        log.warning("conversations table unavailable (run extend-database.sql): %s", e)
        return []


def _store_turn(agent_id: str, role: str, content: str) -> None:
    try:
        db.table("conversations").insert({"agent_id": agent_id, "role": role, "content": content}).execute()
    except Exception as e:
        log.warning("could not store conversation turn: %s", e)


def _maybe_extract_memory(agent_id: str, user_message: str) -> None:
    """Check if owner message reveals a personal fact; store it if so."""
    result = llm.complete(
        f"""The agent's owner said: "{user_message}"

Did this reveal a personal fact worth remembering long-term?
(e.g. names, dates, preferences, relationships, feelings)
If yes, write it as one short statement (e.g. "Owner's wife's birthday is March 15, she loves orchids").
If nothing memorable was shared, reply exactly: NULL""",
        max_tokens=60,
    )
    if result.strip().upper() != "NULL":
        db.table("living_memory").insert({"agent_id": agent_id, "text": result.strip()}).execute()


def chat(agent_id: str, message: str, owner_key: str | None) -> tuple[str, str]:
    """
    Returns (response_text, context).
    Context is determined server-side — caller cannot influence trust level.
    """
    # Single query: fetch full agent row — used for trust check and data load
    agent = db.table("living_agents").select("*").eq("id", agent_id).single().execute().data
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    context = _resolve_context(agent, owner_key)

    # Load only the data this context is entitled to (agent row reused, no second lookup)
    agent, skills, memories = _fetch_agent_data(agent_id, context, agent=agent)
    system = _build_system_prompt(agent, skills, context, memories)

    if context == "owner":
        history = _get_owner_history(agent_id)
    else:
        history = []

    response = llm.chat(system, history + [{"role": "user", "content": message}])

    if context == "owner":
        _store_turn(agent_id, "user", message)
        _store_turn(agent_id, "assistant", response)
        try:
            _maybe_extract_memory(agent_id, message)
        except Exception as e:
            log.warning("memory extraction failed: %s", e)
    else:
        try:
            db.table("living_activity_events").insert({
                "agent_id": agent_id,
                "event_type": "visit",
                "content": f"Stranger visited and asked: {message[:120]}",
            }).execute()
        except Exception as e:
            log.warning("could not record stranger visit: %s", e)

    return response, context
