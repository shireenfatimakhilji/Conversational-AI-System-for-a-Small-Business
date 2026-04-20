# api.py
import asyncio
import tempfile
import os
import io
import re
import wave
import subprocess
import shutil

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sessions import store

import whisper as _whisper


def _ensure_ffmpeg_available() -> bool:
    """Ensure ffmpeg is discoverable for Whisper's subprocess call."""
    if shutil.which("ffmpeg"):
        return True
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        return shutil.which("ffmpeg") is not None
    except Exception:
        return False


# ── Load models at startup ────────────────────────────────────────────────────

print("Loading Whisper ASR model...")
_asr_model = _whisper.load_model("base")
_ffmpeg_ok = _ensure_ffmpeg_available()
if not _ffmpeg_ok:
    print("Warning: FFmpeg not found. /asr/transcribe will be unavailable.")
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
    if not _ffmpeg_ok:
        raise HTTPException(
            status_code=503,
            detail=(
                "FFmpeg is required for ASR transcription but was not found. "
                "Install FFmpeg system-wide, or install imageio-ffmpeg and restart the server."
            ),
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        contents = await audio.read()
        tmp.write(contents)
        tmp_path = tmp.name
    try:
        result = _asr_model.transcribe(tmp_path)
        return {"text": result["text"].strip()}
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="FFmpeg executable not found at runtime. Install FFmpeg and restart the backend.",
        )
    finally:
        os.unlink(tmp_path)


# ── TTS Endpoint ──────────────────────────────────────────────────────────────

@app.post("/tts/speak")
async def speak_text(payload: dict):
    """Converts text to speech using Windows SAPI via pyttsx3, returns WAV."""
    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")

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
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 1.0)
        tmp_path = tempfile.mktemp(suffix=".wav")
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        engine.stop()
        with open(tmp_path, "rb") as f:
            audio_data = f.read()
        os.unlink(tmp_path)
        return io.BytesIO(audio_data)

    audio_buffer = await loop.run_in_executor(None, generate_audio)
    return StreamingResponse(
        audio_buffer,
        media_type="audio/wav",
        headers={"Cache-Control": "no-cache"},
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

            await _stream_response(websocket, manager, user_message)

            if manager.session_ended:
                await websocket.send_json({
                    "type": "session_end",
                    "data": "Order confirmed. Session closed.",
                })
                await websocket.close()
                store.delete(session_id)
                break

    except WebSocketDisconnect:
        store.delete(session_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.send_json({"type": "error", "data": str(e)})
        await websocket.close()
        store.delete(session_id)


async def _stream_response(websocket: WebSocket, manager, user_message: str) -> None:
    """
    Stream tokens to the WebSocket using manager.stream_response_async().

    All conversation logic (memory, RAG, weather, tool-calls, finalization)
    lives inside the manager — api.py only routes tokens to the socket.
    """
    async for token in manager.stream_response_async(user_message):
        await websocket.send_json({"type": "token", "data": token})
        await asyncio.sleep(0)

    await websocket.send_json({"type": "done", "data": ""})

    # Finalize AFTER streaming so session_ended is set correctly before
    # the caller checks manager.session_ended.
    manager.finalize_response(manager.last_streamed_reply)