# api.py
import asyncio
import tempfile
import os
import io
import re
import wave
import subprocess

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sessions import store

import whisper as _whisper

# ── Load models at startup ────────────────────────────────────────────────────

print("Loading Whisper ASR model...")
_asr_model = _whisper.load_model("base")
print("Whisper loaded!")

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Crochetzies Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Session Endpoints ─────────────────────────────────────────────────────────

@app.post("/session/new")
def new_session():
    try:
        session_id = store.create()
        manager = store.get(session_id)
        greeting = manager.get_response("hello")
        return {"session_id": session_id, "greeting": greeting}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/session/{session_id}/stats")
def session_stats(session_id: str):
    manager = store.get(session_id)
    if not manager:
        raise HTTPException(status_code=404, detail="Session not found")
    return manager.get_stats()


@app.delete("/session/{session_id}")
def end_session(session_id: str):
    if not store.get(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    store.delete(session_id)
    return {"message": "Session ended"}


# ── ASR Endpoint ──────────────────────────────────────────────────────────────

@app.post("/asr/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Receives browser mic audio, returns transcribed text via local Whisper."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        contents = await audio.read()
        tmp.write(contents)
        tmp_path = tmp.name
    try:
        result = _asr_model.transcribe(tmp_path)
        return {"text": result["text"].strip()}
    finally:
        os.unlink(tmp_path)


# ── TTS Endpoint ──────────────────────────────────────────────────────────────

@app.post("/tts/speak")
async def speak_text(payload: dict):
    """Converts text to speech using Windows SAPI via pyttsx3, returns WAV."""
    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")

    # Clean text
    text = re.sub(r"[*_`#|]", "", text)
    text = re.sub(r"ORDER-COMPLETE", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Rs\.", "Rupees", text)
    text = text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Text empty after cleaning.")

    loop = asyncio.get_event_loop()

    def generate_audio():
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)   # speed
        engine.setProperty("volume", 1.0) # volume

        # Save to temp WAV file
        tmp_path = tempfile.mktemp(suffix=".wav")
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        engine.stop()

        # Read back
        with open(tmp_path, "rb") as f:
            audio_data = f.read()
        os.unlink(tmp_path)

        return io.BytesIO(audio_data)

    audio_buffer = await loop.run_in_executor(None, generate_audio)

    return StreamingResponse(
        audio_buffer,
        media_type="audio/wav",
        headers={"Cache-Control": "no-cache"}
    )


# ── WebSocket Endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()

    manager = store.get(session_id)
    if not manager:
        await websocket.send_json({"type": "error", "data": "Invalid session ID"})
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "").strip()

            if not user_message:
                await websocket.send_json({"type": "error", "data": "Empty message"})
                continue

            await stream_response(websocket, manager, user_message)

            if manager.session_ended:
                await websocket.send_json({
                    "type": "session_end",
                    "data": "Order confirmed. Session closed."
                })
                await websocket.close()
                store.delete(session_id)
                break

    except WebSocketDisconnect:
        store.delete(session_id)


async def stream_response(websocket: WebSocket, manager, user_message: str):
    import ollama
    from config import MODEL_NAME

    manager._add_turn("user", user_message)
    manager._manage_memory()

    full_reply = ""
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
        await websocket.send_json({"type": "token", "data": token})
        await asyncio.sleep(0)

    await websocket.send_json({"type": "done", "data": ""})

    manager._add_turn("assistant", full_reply)
    manager._turn_count += 1

    if "order-complete" in full_reply.lower():
        manager.session_ended = True
        manager._save_history()
