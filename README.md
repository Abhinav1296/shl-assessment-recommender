---
title: SHL Assessment Recommender
emoji: "🎯"
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# SHL Conversational Assessment Recommender

A FastAPI service that recommends SHL assessments through multi-turn conversation.

## Endpoints

- GET /health — readiness check
- POST /chat — chat with the agent

## Stack

- FastAPI + Uvicorn
- Groq (Llama 3.1 8B for routing, Llama 3.3 70B for generation)
- Hybrid retrieval: BM25 + sentence-transformers (all-MiniLM-L6-v2)
- 377-item SHL Individual Test Solutions catalog

Built for the SHL AI Intern take-home assignment.
