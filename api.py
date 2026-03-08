# api.py
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sessions import store

app = FastAPI(title="Crochetzies Chatbot API")

# Allow browser frontends to connect (Phase 5 will need this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST Endpoints ────────────────────────────────────────────────────────────

@app.post("/session/new")
def new_session():
    """
    Creates a new chat session.
    Returns a session_id that the client must include in all future requests.
    """
    session_id = store.create()
    manager = store.get(session_id)

    # Send the greeting message
    greeting = manager.get_response("hello")
    return {
        "session_id": session_id,
        "greeting": greeting
    }


@app.get("/session/{session_id}/stats")
def session_stats(session_id: str):
    """Returns stats for a session (turns, memory, etc.)"""
    manager = store.get(session_id)
    if not manager:
        raise HTTPException(status_code=404, detail="Session not found")
    return manager.get_stats()


@app.delete("/session/{session_id}")
def end_session(session_id: str):
    """Manually ends and deletes a session."""
    if not store.get(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    store.delete(session_id)
    return {"message": "Session ended"}


# ── WebSocket Endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    Main chat endpoint. Streams bot tokens back as they are generated.

    Client sends:  {"message": "I want a cat"}
    Server sends:  {"type": "token",  "data": "Sure"}   (one per token)
                   {"type": "token",  "data": "!"}
                   {"type": "done",   "data": ""}        (signals end of reply)
                   {"type": "error",  "data": "..."}     (if something goes wrong)
    """
    await websocket.accept()

    manager = store.get(session_id)
    if not manager:
        await websocket.send_json({"type": "error", "data": "Invalid session ID"})
        await websocket.close()
        return

    try:
        while True:
            # Wait for the user's message
            data = await websocket.receive_json()
            user_message = data.get("message", "").strip()

            if not user_message:
                await websocket.send_json({"type": "error", "data": "Empty message"})
                continue

            # Stream the response token by token
            await stream_response(websocket, manager, user_message)

            # If order is confirmed, close the connection cleanly
            if manager.session_ended:
                await websocket.send_json({"type": "session_end", "data": "Order confirmed. Session closed."})
                await websocket.close()
                store.delete(session_id)
                break

    except WebSocketDisconnect:
        store.delete(session_id)


async def stream_response(websocket: WebSocket, manager, user_message: str):
    """
    Calls the ConversationManager in a thread (since Ollama is blocking/sync),
    streams each token back over the WebSocket as it arrives.
    """
    import ollama
    from config import MODEL_NAME

    # Build the message list without running inference yet
    manager._add_turn("user", user_message)
    manager._manage_memory()

    full_reply = ""

    # Run Ollama streaming in a thread so it doesn't block the async event loop
    loop = asyncio.get_event_loop()

    def run_stream():
        return ollama.chat(
            model=MODEL_NAME,
            messages=manager._build_messages(),
            stream=True
        )

    response_stream = await loop.run_in_executor(None, run_stream)

    for chunk in response_stream:
        token = chunk["message"]["content"]
        full_reply += token
        # Send each token immediately to the client
        await websocket.send_json({"type": "token", "data": token})
        await asyncio.sleep(0)  # yield control so other connections stay responsive

    # Signal end of this response
    await websocket.send_json({"type": "done", "data": ""})

    # Record the completed reply in history
    manager._add_turn("assistant", full_reply)
    manager._turn_count += 1

    # Check for order completion signal
    if "order-complete" in full_reply.lower():
        manager.session_ended = True
        manager._save_history()
