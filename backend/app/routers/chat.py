from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import chat_service

router = APIRouter(prefix="/agents", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    owner_key: str | None = None


@router.post("/{agent_id}/chat")
def chat(agent_id: str, body: ChatRequest):
    try:
        response, context = chat_service.chat(agent_id, body.message, body.owner_key)
        return {"response": response, "context": context}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
