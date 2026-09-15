---
title: Voyager AI Backend
emoji: 🌍
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Voyager AI - FastAPI Backend

AI Travel Planning Engine with Deep Agents, LangGraph Orchestration, and Multi-turn Streaming.

## Space Configuration
- **SDK**: Docker
- **App Port**: 7860
- **Base Endpoint**: `https://<space-name>.hf.space`

## Key API Endpoints
- `GET /health` - Health check & system status
- `POST /chat/stream` - SSE streaming agent response
- `POST /chat/cancel` - Cancel active agent generation
- `POST /chat/regenerate` - Regenerate itinerary recommendations
- `GET /threads` - List user conversation threads
- `GET /threads/{thread_id}/activities` - Retrieve tool calls, thinking, and charts
- `POST /share/{thread_id}` - Generate shared itinerary token
- `GET /share/{token}` - Public read-only itinerary access
- `POST /upload` - Multimodal document & flight PDF upload

