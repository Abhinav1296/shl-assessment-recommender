"""
main.py
FastAPI service exposing /health and /chat endpoints.
"""

import os
from typing import List, Optional, Literal
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import SHLAgent

# ------------------------------------------------------------
# Global agent instance (loaded once at startup)
# ------------------------------------------------------------
agent: Optional[SHLAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the agent (catalog + embeddings) on startup."""
    global agent
    print("[main] Booting SHL Agent...")
    agent = SHLAgent()
    print("[main] Agent ready.")
    yield
    print("[main] Shutting down.")


app = FastAPI(
    title="SHL Assessment Recommender",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permissive so the evaluator can hit us from anywhere
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# Pydantic schemas — MUST match assignment spec exactly
# ------------------------------------------------------------

class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: List[Message] = Field(..., min_length=1)


class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str


class ChatResponse(BaseModel):
    reply: str
    recommendations: List[Recommendation]
    end_of_conversation: bool


class HealthResponse(BaseModel):
    status: str


# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    """Readiness check for the evaluator."""
    return HealthResponse(status="ok")


@app.get("/")
def root():
    """Landing page — helpful for browser hits."""
    return {
        "service": "SHL Assessment Recommender",
        "endpoints": {
            "GET /health": "Health check",
            "POST /chat": "Conversational chat endpoint",
        },
        "status": "running" if agent is not None else "loading",
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Main chat endpoint. Stateless — full history passed each call."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not ready yet")

    # Convert pydantic models to plain dicts for the agent
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    try:
        result = agent.chat(messages)
    except Exception as e:
        print(f"[main] Chat error: {e}")
        # Graceful fallback — schema must still be valid
        return ChatResponse(
            reply="I hit an internal error. Could you rephrase your request?",
            recommendations=[],
            end_of_conversation=False,
        )

    # Coerce to schema, enforce max 10 recommendations
    recs = result.get("recommendations", [])[:10]
    return ChatResponse(
        reply=result.get("reply", ""),
        recommendations=[Recommendation(**r) for r in recs],
        end_of_conversation=bool(result.get("end_of_conversation", False)),
    )


# ------------------------------------------------------------
# Dev entry point
# ------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)