# sessions.py
import uuid
from threading import Lock
from convo_manager import ConversationManager

class SessionStore:
    """
    Holds one ConversationManager per active user session.
    Thread-safe so concurrent users don't interfere with each other.
    """
    def __init__(self):
        self._sessions: dict[str, ConversationManager] = {}
        self._lock = Lock()

    def create(self) -> str:
        """Creates a new session, returns its unique ID."""
        session_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[session_id] = ConversationManager()
        return session_id

    def get(self, session_id: str) -> ConversationManager | None:
        """Returns the ConversationManager for a session, or None if not found."""
        return self._sessions.get(session_id)

    def delete(self, session_id: str):
        """Removes a session when the user disconnects."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        """Returns all active session IDs (useful for debugging)."""
        return list(self._sessions.keys())

# Single global instance shared across the whole app
store = SessionStore()