from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


class BootstrapRequest(BaseModel):
    name: str
    personality: str


@router.post("", status_code=201)
def bootstrap_agent(body: BootstrapRequest):
    try:
        agent = agent_service.bootstrap(body.name, body.personality)
        return {"agent": agent}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_agents():
    from app.db.supabase import db
    agents = db.table("living_agents").select("id, name, status, accent_color, showcase_emoji").execute().data or []
    return {"agents": agents}
