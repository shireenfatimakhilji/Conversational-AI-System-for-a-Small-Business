# Crochetzies Chatbot - Virtual Order Assistant

## Business Use Case

Crochetzies is a conversational AI assistant designed for a small custom crochet business. The chatbot helps customers place personalized orders through natural conversation instead of traditional forms.

The system enhances user experience using:

- **RAG (Retrieval-Augmented Generation):**  
  Retrieves relevant business knowledge (pricing, policies, product info) from a document store to ensure accurate and consistent responses.

- **Tool Integration:**
  - CRM Tool: Stores and manages customer order details  
  - Calendar Tool: Calculates delivery dates based on business rules  
  - Weather Tool: Assesses delivery delays due to weather conditions  
  - Calculator Tool: Computes pricing dynamically  

Together, these components allow the chatbot to behave like a real business assistant—handling orders, answering questions, and performing backend operations intelligently.

---

### Components Explanation

- **Frontend (Next.js):** Chat UI and WebSocket communication  
- **API Layer (FastAPI):** Handles routes, sessions, ASR, TTS  
- **Conversation Manager:** Controls dialogue flow and memory  
- **RAG System:** Retrieves relevant knowledge chunks  
- **Tool Orchestrator:** Executes tools with validation  
- **Session Manager:** Manages active users and chat sessions  

---

## Features

- Streaming chat responses over WebSocket  
- Session-based conversations with a maximum of 4 active users  
- Tool execution for CRM, calculator, weather, and calendar  
- RAG-based knowledge retrieval  
- Voice support through ASR and TTS  
- Local CLI entrypoint  
- Test scripts for validation  

---

## Tech Stack

- Backend: Python, FastAPI, Ollama, Whisper, pyttsx3  
- Frontend: Next.js, React  
- RAG: Sentence Transformers  
- Storage: SQLite + in-memory sessions  

---

## Model Selection

- Model: `qwen2.5:1.5b` (via Ollama)
- Reason:
  - Lightweight and runs locally  
  - Fast enough for real-time chat  
- Performance:
  - ~15–25 tokens/sec  
  - ~2–4GB RAM usage  

---

## Document Collection (RAG)

- Documents: ~150–200 chunks  
- Source: FAQs, pricing, policies  
- Chunk Size: 200–500 tokens  
- Embedding Model: `all-MiniLM-L6-v2`  
- Retrieval:
  - Top-K: 3–5  
  - Similarity: Cosine  

---

## Tools Description

### CRM Tool
- Stores customer data  
- Example:
```json
{"tool": "crm", "args": {"action": "create", "customer_name": "Ali"}}

## Quick Start

### 1. Pull the Ollama model

```bash
ollama pull qwen2.5:1.5b
```

### 2. Start the backend

```bash
pip install -r requirements.txt
uvicorn api:app --reload
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Open the app

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Project Structure

```
├── api.py                  # FastAPI app, REST endpoints, WebSocket chat, ASR, TTS
├── convo_manager.py        # Conversation flow, memory handling, weather routing
├── orchestrator.py         # Tool registration, schema validation, execution
├── sessions.py             # Session store with max concurrent user limit
├── config.py               # Model name, pricing, and conversation settings
├── prompt_temp.py          # System prompt and summarization templates
├── main.py                 # Simple CLI chat entrypoint
├── tools/                  # CRM, calculator, and weather tools
├── test_tools.py           # Direct tool and orchestrator checks
├── test_dialogs.py         # Multi-turn dialogue scenarios
├── stress_test.py          # Load testing script
├── demo_reliability_features.py  # Reliability feature demo
├── retry_utils.py          # Retry helpers
├── error_handlers.py       # Shared error handling helpers
├── requirements.txt        # Backend dependencies
├── Dockerfile              # Backend container image
└── frontend/
    ├── pages/
    │   ├── index.js        # App entry page
    │   └── _app.js         # Next.js app wrapper
    ├── src/
    │   ├── components/     # Chat UI components
    │   └── hooks/          # WebSocket hook
    ├── styles/             # Global styles
    └── package.json        # Frontend dependencies and scripts
```

## Backend API

- `POST /session/new` creates a new chat session and returns a greeting.
- `GET /session/{session_id}/stats` returns session statistics.
- `DELETE /session/{session_id}` ends a session.
- `POST /asr/transcribe` transcribes uploaded audio with Whisper.
- `POST /tts/speak` returns spoken audio as WAV.
- `WS /ws/chat/{session_id}` streams chat responses.

## Tool Layer

The orchestrator in `orchestrator.py` exposes three registered tools:

- `crm` for storing and updating customer records in `data/crm.sqlite3`
- `calculator` for safe arithmetic evaluation
- `weather` for weather lookup and delivery impact assessment

## Running Tests

```bash
python test_tools.py
python test_rag.py
python test_tools2.py
python test_dialogs.py
python stress_test.py
python demo_reliability_features.py
```

## Configuration

Adjust `config.py` to change:

- Ollama model name
- Memory window size
- Product pricing
- Business name

The frontend proxies `/api/*` and `/ws/*` to the backend through `frontend/next.config.js`, so the browser app can talk to the local FastAPI server without extra setup.

## Notes

- The project expects Ollama to be running locally before the backend starts.
- If FFmpeg is missing, `/asr/transcribe` will return a service unavailable error.
- Weather lookups fall back to demo data when no API key is configured.

**Tech Stack**: Python, FastAPI, Ollama, Whisper, Next.js, React

## Link to th edemo video: https://youtu.be/5npbhZ2dv5c