"""SQLite-backed CRM tool for storing customer details."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Dict


class CRMTool:
    """Persist and retrieve customer profiles."""

    def __init__(self, db_path: str | Path | None = None):
        base_dir = Path(__file__).resolve().parent.parent
        self.db_path = Path(db_path) if db_path else base_dir / "data" / "crm.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._ensure_schema()

    @staticmethod
    def schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["upsert", "get", "update", "delete", "list"],
                },
                "user_id": {"type": "string"},
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "address": {"type": "string"},
                "notes": {"type": "string"},
                "preferences": {"type": "object"},
                "metadata": {"type": "object"},
            },
            "required": ["action"],
            "additionalProperties": True,
        }

    async def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        action = str(args.get("action", "")).strip().lower()
        if not action:
            raise ValueError("CRM action is required.")

        if action in {"get", "update", "delete"} and not str(args.get("user_id", "")).strip():
            raise ValueError(f"'user_id' is required for CRM action '{action}'.")

        if action == "upsert":
            user_id = self._require_user_id(args)
            record = self._upsert(user_id, args)
            return {"action": action, "user": record}

        if action == "get":
            record = self._get(self._require_user_id(args))
            return {"action": action, "user": record}

        if action == "update":
            user_id = self._require_user_id(args)
            record = self._update(user_id, args)
            return {"action": action, "user": record}

        if action == "delete":
            removed = self._delete(self._require_user_id(args))
            return {"action": action, "deleted": removed}

        if action == "list":
            return {"action": action, "users": self._list()}

        raise ValueError(f"Unsupported CRM action: {action}")

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    user_id TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    phone TEXT,
                    address TEXT,
                    notes TEXT,
                    preferences_json TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _require_user_id(self, args: Dict[str, Any]) -> str:
        user_id = str(args.get("user_id", "")).strip()
        if not user_id:
            raise ValueError("'user_id' is required.")
        return user_id

    def _row_to_user(self, row: sqlite3.Row | None) -> Dict[str, Any] | None:
        if row is None:
            return None
        return {
            "user_id": row["user_id"],
            "name": row["name"],
            "email": row["email"],
            "phone": row["phone"],
            "address": row["address"],
            "notes": row["notes"],
            "preferences": json.loads(row["preferences_json"] or "{}"),
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _upsert(self, user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM customers WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            current = self._row_to_user(existing) or {
                "user_id": user_id,
                "name": None,
                "email": None,
                "phone": None,
                "address": None,
                "notes": None,
                "preferences": {},
                "metadata": {},
                "created_at": self._now(),
                "updated_at": self._now(),
            }

            updated = self._merge_payload(current, args)
            connection.execute(
                """
                INSERT INTO customers (
                    user_id, name, email, phone, address, notes,
                    preferences_json, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    name = excluded.name,
                    email = excluded.email,
                    phone = excluded.phone,
                    address = excluded.address,
                    notes = excluded.notes,
                    preferences_json = excluded.preferences_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    updated["user_id"],
                    updated["name"],
                    updated["email"],
                    updated["phone"],
                    updated["address"],
                    updated["notes"],
                    json.dumps(updated["preferences"], ensure_ascii=False),
                    json.dumps(updated["metadata"], ensure_ascii=False),
                    updated["created_at"],
                    updated["updated_at"],
                ),
            )
            connection.commit()
            return updated

    def _update(self, user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM customers WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"No CRM record found for user_id '{user_id}'.")

            current = self._row_to_user(row)
            assert current is not None
            updated = self._merge_payload(current, args, preserve_created_at=True)
            connection.execute(
                """
                UPDATE customers
                SET name = ?, email = ?, phone = ?, address = ?, notes = ?,
                    preferences_json = ?, metadata_json = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    updated["name"],
                    updated["email"],
                    updated["phone"],
                    updated["address"],
                    updated["notes"],
                    json.dumps(updated["preferences"], ensure_ascii=False),
                    json.dumps(updated["metadata"], ensure_ascii=False),
                    updated["updated_at"],
                    user_id,
                ),
            )
            connection.commit()
            return updated

    def _get(self, user_id: str) -> Dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM customers WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return self._row_to_user(row)

    def _delete(self, user_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM customers WHERE user_id = ?",
                (user_id,),
            )
            connection.commit()
            return cursor.rowcount > 0

    def _list(self) -> list[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM customers ORDER BY updated_at DESC"
            ).fetchall()
            return [self._row_to_user(row) for row in rows if row is not None]

    def _merge_payload(
        self,
        current: Dict[str, Any],
        args: Dict[str, Any],
        preserve_created_at: bool = False,
    ) -> Dict[str, Any]:
        merged = dict(current)
        for field_name in ("name", "email", "phone", "address", "notes"):
            if field_name in args and args[field_name] is not None:
                merged[field_name] = str(args[field_name]).strip() or None

        preferences = dict(merged.get("preferences", {}) or {})
        preferences_arg = args.get("preferences")
        if isinstance(preferences_arg, dict):
            preferences.update(preferences_arg)
        merged["preferences"] = preferences

        metadata = dict(merged.get("metadata", {}) or {})
        metadata_arg = args.get("metadata")
        if isinstance(metadata_arg, dict):
            metadata.update(metadata_arg)
        merged["metadata"] = metadata

        merged["updated_at"] = self._now()
        if not preserve_created_at and not merged.get("created_at"):
            merged["created_at"] = self._now()
        return merged