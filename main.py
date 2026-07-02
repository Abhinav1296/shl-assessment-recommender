"""
main.py
FastAPI service exposing /health and /chat endpoints.
"""

import os
from typing import List, Optional, Literal
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from agent import SHLAgent

# ------------------------------------------------------------
# Global agent instance
# ------------------------------------------------------------
agent: Optional[SHLAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# Schemas
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
# Landing page
# ------------------------------------------------------------

LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SHL Assessment Recommender</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
    background: #0a0e1a;
    color: #e0e6f0;
    line-height: 1.6;
    min-height: 100vh;
    background-image:
      radial-gradient(circle at 20% 30%, rgba(0, 255, 200, 0.08) 0%, transparent 40%),
      radial-gradient(circle at 80% 70%, rgba(100, 100, 255, 0.08) 0%, transparent 40%);
  }
  .container { max-width: 900px; margin: 0 auto; padding: 60px 30px; }
  .header { text-align: center; margin-bottom: 50px; }
  .badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(0, 255, 150, 0.1);
    border: 1px solid rgba(0, 255, 150, 0.4);
    color: #00ff99;
    padding: 6px 14px; border-radius: 20px; font-size: 12px;
    margin-bottom: 20px; font-weight: 600; letter-spacing: 0.5px;
  }
  .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #00ff99; box-shadow: 0 0 8px #00ff99;
    animation: pulse 1.6s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
  h1 {
    font-size: 42px; font-weight: 700;
    background: linear-gradient(135deg, #00ffcc 0%, #6a8fff 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -1px; margin-bottom: 12px;
  }
  .tagline { color: #8a9bb5; font-size: 15px; }
  .prompt { color: #00ffcc; }
  .section {
    background: rgba(20, 26, 42, 0.6);
    border: 1px solid rgba(100, 130, 200, 0.15);
    border-radius: 12px; padding: 28px; margin-bottom: 20px;
    backdrop-filter: blur(10px);
  }
  h2 {
    font-size: 14px; color: #00ffcc; text-transform: uppercase;
    letter-spacing: 2px; margin-bottom: 18px; font-weight: 600;
  }
  .endpoint {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 16px; background: rgba(0, 0, 0, 0.3);
    border-radius: 8px; margin-bottom: 12px;
    border-left: 3px solid #00ffcc;
  }
  .method {
    padding: 3px 10px; border-radius: 4px; font-size: 11px;
    font-weight: 700; letter-spacing: 0.5px;
  }
  .method.get { background: #1a3a2e; color: #00ff99; }
  .method.post { background: #2a1a3a; color: #c99aff; }
  .path { color: #e0e6f0; font-size: 14px; }
  .desc { color: #6b7a94; font-size: 13px; margin-left: auto; }
  pre {
    background: #000; border: 1px solid rgba(100, 130, 200, 0.2);
    border-radius: 8px; padding: 16px; overflow-x: auto;
    font-size: 13px; color: #a0b4d0; margin-top: 8px;
  }
  .tech-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px; margin-top: 10px;
  }
  .tech-item {
    background: rgba(0, 0, 0, 0.3); padding: 12px 14px;
    border-radius: 8px; font-size: 13px; color: #b0c0dc;
    border-left: 2px solid #6a8fff;
  }
  .tech-item strong { color: #00ffcc; display: block; margin-bottom: 3px; font-size: 12px; }
  footer {
    text-align: center; margin-top: 40px; padding-top: 24px;
    border-top: 1px solid rgba(100, 130, 200, 0.15);
    color: #6b7a94; font-size: 13px;
  }
  footer a { color: #00ffcc; text-decoration: none; }
  footer a:hover { text-decoration: underline; }
  .cursor { display: inline-block; width: 8px; height: 16px;
    background: #00ffcc; animation: blink 1s infinite;
    vertical-align: middle; margin-left: 2px; }
  @keyframes blink { 50% { opacity: 0; } }
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="badge"><span class="dot"></span> SERVICE OPERATIONAL</div>
      <h1>SHL Assessment Recommender</h1>
      <p class="tagline"><span class="prompt">&gt;_</span> Conversational agent for SHL Individual Test Solutions catalog<span class="cursor"></span></p>
    </div>

    <div class="section">
      <h2>// API Endpoints</h2>
      <div class="endpoint">
        <span class="method get">GET</span>
        <span class="path">/health</span>
        <span class="desc">Readiness check</span>
      </div>
      <div class="endpoint">
        <span class="method post">POST</span>
        <span class="path">/chat</span>
        <span class="desc">Conversational recommendations</span>
      </div>
      <div class="endpoint">
        <span class="method get">GET</span>
        <span class="path">/docs</span>
        <span class="desc">Interactive OpenAPI docs</span>
      </div>
    </div>

    <div class="section">
      <h2>// Example Request</h2>
      <pre>curl -X POST https://abhinav23124-shl-agent.hf.space/chat \\
  -H "Content-Type: application/json" \\
  -d '{
    "messages": [
      {"role": "user", "content": "Hiring senior Java developer"}
    ]
  }'</pre>
    </div>

    <div class="section">
      <h2>// Example Response</h2>
      <pre>{
  "reply": "For a senior Java developer role...",
  "recommendations": [
    {
      "name": "Core Java (Advanced Level) (New)",
      "url": "https://www.shl.com/products/...",
      "test_type": "K"
    }
  ],
  "end_of_conversation": false
}</pre>
    </div>

    <div class="section">
      <h2>// Stack</h2>
      <div class="tech-grid">
        <div class="tech-item"><strong>API</strong>FastAPI + Uvicorn</div>
        <div class="tech-item"><strong>LLM</strong>Groq (Llama 3.1 + 3.3)</div>
        <div class="tech-item"><strong>Retrieval</strong>BM25 + MiniLM Embeddings</div>
        <div class="tech-item"><strong>Catalog</strong>377 SHL Assessments</div>
        <div class="tech-item"><strong>Deploy</strong>Docker on HF Spaces</div>
        <div class="tech-item"><strong>Contract</strong>Stateless, 8-turn cap</div>
      </div>
    </div>

    <footer>
      Built by <a href="https://www.linkedin.com/in/abhinav1296/" target="_blank">Abhinav</a>
      for the SHL AI Intern take-home assignment
    </footer>
  </div>
</body>
</html>"""


# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def root():
    """Landing page for browser hits."""
    return HTMLResponse(content=LANDING_HTML)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not ready yet")

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    try:
        result = agent.chat(messages)
    except Exception as e:
        print(f"[main] Chat error: {e}")
        return ChatResponse(
            reply="I hit an internal error. Could you rephrase your request?",
            recommendations=[],
            end_of_conversation=False,
        )

    recs = result.get("recommendations", [])[:10]
    return ChatResponse(
        reply=result.get("reply", ""),
        recommendations=[Recommendation(**r) for r in recs],
        end_of_conversation=bool(result.get("end_of_conversation", False)),
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)