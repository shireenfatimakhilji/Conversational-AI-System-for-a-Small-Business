# Crochetzies Chatbot - Virtual Order Assistant

A conversational AI chatbot for taking custom crochet orders using Ollama LLM with streaming responses, session management, and a modern Next.js frontend.

## Prerequisites

- Python 3.10+
- Node.js 16+
- Ollama with qwen2.5:1.5b model

## Quick Start

### 1. Install Ollama Model

```bash
ollama pull qwen2.5:1.5b
```

### 2. Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the backend server
uvicorn api:app --reload
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 4. Access Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Project Structure

```
├── api.py                  # FastAPI server with REST & WebSocket endpoints
├── convo_manager.py        # Conversation orchestration & memory management
├── prompt_temp.py          # System prompts & templates
├── config.py               # Configuration & pricing
├── sessions.py             # Thread-safe session management
├── test_dialogs.py         # Multi-turn dialogue tests
├── requirements.txt        # Python dependencies
│
├── frontend/
│   ├── pages/
│   │   ├── index.js       # Main page
│   │   └── _app.js        # App wrapper
│   ├── src/
│   │   ├── components/    # React components
│   │   └── hooks/         # Custom hooks (WebSocket)
│   ├── styles/            # Global styles
│   └── package.json       # Frontend dependencies
│
└── Testing & Reliability Features:
    ├── benchmark_latency.py          # Latency benchmarking tool
    ├── stress_test.py                # Load & stress testing
    ├── retry_utils.py                # Retry with exponential backoff
    ├── circuit_breaker.py            # Circuit breaker pattern
    ├── error_handlers.py             # Centralized error handling
    ├── demo_reliability_features.py  # Interactive demo
    ├── TESTING_RELIABILITY_GUIDE.md  # Full documentation
    └── QUICK_REFERENCE.md            # Quick commands reference
```

## Features

### Core Functionality

- **Conversational Ordering**: Natural language order processing
- **Session Management**: Thread-safe multi-user support
- **Streaming Responses**: Real-time token-by-token responses via WebSocket
- **Memory Management**: Hybrid sliding window + summarization
- **Order Validation**: Collects all required information before confirmation

### Testing & Reliability

- **Latency Benchmarking**: Measure API & WebSocket performance
- **Stress Testing**: Simulate concurrent users with realistic patterns
- **Retry Logic**: Automatic retry with exponential backoff
- **Circuit Breaker**: Prevent cascading failures
- **Error Handling**: Comprehensive error classification & recovery

## Usage Examples

### Run Tests

```bash
# Dialogue tests
python test_dialogs.py

# Latency benchmark
python benchmark_latency.py --iterations 20

# Stress test (5 users, 30 seconds)
python stress_test.py --users 5 --duration 30

# Feature demo
python demo_reliability_features.py
```

### API Endpoints

- `POST /session/new` - Create new session
- `GET /session/{id}/stats` - Get session statistics
- `DELETE /session/{id}` - End session
- `WS /ws/chat/{id}` - WebSocket chat endpoint

## Configuration

Edit `config.py` to customize:

- Model name
- Memory window size
- Product pricing
- Session timeout

## Dependencies

### Backend

- fastapi
- uvicorn
- ollama
- websockets

### Frontend

- next.js
- react

### Testing (Optional)

- requests
- websockets
- psutil

## Assignment Components

1. **Backend**: FastAPI server with streaming LLM integration
2. **Frontend**: Next.js React application with WebSocket client
3. **Testing**: Comprehensive test suite and reliability features
4. **Documentation**: Full guides and examples

## Notes

- Requires Ollama to be running locally
- Frontend proxies API calls to backend (configured in next.config.js)

---

**Date**: March 2026  
**Tech Stack**: Python, FastAPI, Ollama, Next.js, React

# Conversational-AI-System-for-a-Small-Business