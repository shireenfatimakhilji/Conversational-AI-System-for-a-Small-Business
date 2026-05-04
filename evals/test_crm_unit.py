"""
test_crm_unit.py
================
Component-level (unit) tests for CRMTool.
Directly calls the tool — no LLM involved.

Tests cover:
  Layer 1 — CRUD correctness (create, read, update, delete, list)
  Layer 2 — Schema / validation edge cases
  Layer 3 — Concurrent access safety
  Layer 4 — Persistence across instances

Run:
    cd nlp_3
    python -m pytest evals/test_crm_unit.py -v
  OR standalone:
    python evals/test_crm_unit.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import threading
import time
import unittest

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.crm import CRMTool


# ── helper ────────────────────────────────────────────────────────────────────

def run(coro):
    """Run a coroutine synchronously (compatible with Python 3.10+)."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TempCRM:
    """Context manager that gives a CRMTool backed by a temp SQLite file."""

    def __enter__(self):
        self._dir = tempfile.mkdtemp()
        self.db = os.path.join(self._dir, "test_crm.sqlite3")
        self.crm = CRMTool(db_path=self.db)
        return self.crm

    def __exit__(self, *_):
        import shutil
        shutil.rmtree(self._dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 1 — CRUD correctness
# ══════════════════════════════════════════════════════════════════════════════

class TestCRMCreate(unittest.TestCase):
    """Test creating (upsert) customer records."""

    def test_upsert_creates_new_record(self):
        with TempCRM() as crm:
            result = run(crm.run({
                "action": "upsert",
                "user_id": "u001",
                "name": "Alice",
                "email": "alice@example.com",
            }))
            self.assertEqual(result["action"], "upsert")
            user = result["user"]
            self.assertEqual(user["user_id"], "u001")
            self.assertEqual(user["name"], "Alice")
            self.assertEqual(user["email"], "alice@example.com")
            self.assertIsNotNone(user["created_at"])
            self.assertIsNotNone(user["updated_at"])

    def test_upsert_stores_phone_address_notes(self):
        with TempCRM() as crm:
            run(crm.run({
                "action": "upsert",
                "user_id": "u002",
                "name": "Bob",
                "phone": "+1-555-0100",
                "address": "123 Main St, Springfield",
                "notes": "Prefers pink yarn",
            }))
            result = run(crm.run({"action": "get", "user_id": "u002"}))
            user = result["user"]
            self.assertEqual(user["phone"], "+1-555-0100")
            self.assertEqual(user["address"], "123 Main St, Springfield")
            self.assertEqual(user["notes"], "Prefers pink yarn")

    def test_upsert_stores_preferences(self):
        with TempCRM() as crm:
            run(crm.run({
                "action": "upsert",
                "user_id": "u003",
                "name": "Carol",
                "preferences": {"color": "blue", "size": "medium"},
            }))
            result = run(crm.run({"action": "get", "user_id": "u003"}))
            prefs = result["user"]["preferences"]
            self.assertEqual(prefs["color"], "blue")
            self.assertEqual(prefs["size"], "medium")

    def test_upsert_stores_metadata(self):
        with TempCRM() as crm:
            run(crm.run({
                "action": "upsert",
                "user_id": "u004",
                "name": "Dan",
                "metadata": {"source": "chatbot", "session": "abc123"},
            }))
            result = run(crm.run({"action": "get", "user_id": "u004"}))
            meta = result["user"]["metadata"]
            self.assertEqual(meta["source"], "chatbot")
            self.assertEqual(meta["session"], "abc123")

    def test_upsert_overwrites_existing_record(self):
        """Upsert on existing user_id should update, not duplicate."""
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "u005", "name": "Eve", "email": "old@x.com"}))
            run(crm.run({"action": "upsert", "user_id": "u005", "name": "Eve Updated", "email": "new@x.com"}))
            result = run(crm.run({"action": "get", "user_id": "u005"}))
            user = result["user"]
            self.assertEqual(user["name"], "Eve Updated")
            self.assertEqual(user["email"], "new@x.com")
            # List should contain only one record for this user
            all_users = run(crm.run({"action": "list"}))["users"]
            ids = [u["user_id"] for u in all_users]
            self.assertEqual(ids.count("u005"), 1)


class TestCRMRead(unittest.TestCase):
    """Test reading customer records."""

    def test_get_existing_user(self):
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "r001", "name": "Frank"}))
            result = run(crm.run({"action": "get", "user_id": "r001"}))
            self.assertEqual(result["action"], "get")
            self.assertEqual(result["user"]["name"], "Frank")

    def test_get_nonexistent_user_returns_none(self):
        with TempCRM() as crm:
            result = run(crm.run({"action": "get", "user_id": "does_not_exist"}))
            self.assertIsNone(result["user"])

    def test_list_empty_db(self):
        with TempCRM() as crm:
            result = run(crm.run({"action": "list"}))
            self.assertEqual(result["action"], "list")
            self.assertEqual(result["users"], [])

    def test_list_returns_all_users(self):
        with TempCRM() as crm:
            for i in range(5):
                run(crm.run({"action": "upsert", "user_id": f"list_{i}", "name": f"User {i}"}))
            result = run(crm.run({"action": "list"}))
            self.assertEqual(len(result["users"]), 5)

    def test_list_ordered_by_updated_at_desc(self):
        """Most recently updated user should appear first."""
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "old_user", "name": "Old"}))
            time.sleep(0.05)
            run(crm.run({"action": "upsert", "user_id": "new_user", "name": "New"}))
            users = run(crm.run({"action": "list"}))["users"]
            self.assertEqual(users[0]["user_id"], "new_user")


class TestCRMUpdate(unittest.TestCase):
    """Test updating existing customer records."""

    def test_update_name(self):
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "upd001", "name": "Grace"}))
            result = run(crm.run({"action": "update", "user_id": "upd001", "name": "Grace Updated"}))
            self.assertEqual(result["action"], "update")
            self.assertEqual(result["user"]["name"], "Grace Updated")

    def test_update_preserves_created_at(self):
        """update action must NOT change created_at."""
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "upd002", "name": "Henry"}))
            before = run(crm.run({"action": "get", "user_id": "upd002"}))["user"]["created_at"]
            time.sleep(0.05)
            run(crm.run({"action": "update", "user_id": "upd002", "name": "Henry 2"}))
            after = run(crm.run({"action": "get", "user_id": "upd002"}))["user"]["created_at"]
            self.assertEqual(before, after)

    def test_update_merges_preferences(self):
        """Preferences from update should be merged, not replaced."""
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "upd003", "name": "Ivy",
                         "preferences": {"color": "red", "size": "small"}}))
            run(crm.run({"action": "update", "user_id": "upd003",
                         "preferences": {"color": "blue"}}))
            prefs = run(crm.run({"action": "get", "user_id": "upd003"}))["user"]["preferences"]
            self.assertEqual(prefs["color"], "blue")   # updated
            self.assertEqual(prefs["size"], "small")   # preserved

    def test_update_nonexistent_user_raises(self):
        with TempCRM() as crm:
            with self.assertRaises(ValueError):
                run(crm.run({"action": "update", "user_id": "ghost", "name": "Ghost"}))

    def test_update_refreshes_updated_at(self):
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "upd004", "name": "Jack"}))
            before = run(crm.run({"action": "get", "user_id": "upd004"}))["user"]["updated_at"]
            time.sleep(0.05)
            run(crm.run({"action": "update", "user_id": "upd004", "name": "Jack 2"}))
            after = run(crm.run({"action": "get", "user_id": "upd004"}))["user"]["updated_at"]
            self.assertGreater(after, before)


class TestCRMDelete(unittest.TestCase):
    """Test deleting customer records."""

    def test_delete_existing_user_returns_true(self):
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "del001", "name": "Kate"}))
            result = run(crm.run({"action": "delete", "user_id": "del001"}))
            self.assertEqual(result["action"], "delete")
            self.assertTrue(result["deleted"])

    def test_deleted_user_not_found_afterward(self):
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "del002", "name": "Leo"}))
            run(crm.run({"action": "delete", "user_id": "del002"}))
            result = run(crm.run({"action": "get", "user_id": "del002"}))
            self.assertIsNone(result["user"])

    def test_delete_nonexistent_user_returns_false(self):
        with TempCRM() as crm:
            result = run(crm.run({"action": "delete", "user_id": "nobody"}))
            self.assertFalse(result["deleted"])

    def test_delete_one_does_not_affect_others(self):
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "keep", "name": "Keeper"}))
            run(crm.run({"action": "upsert", "user_id": "gone", "name": "Goner"}))
            run(crm.run({"action": "delete", "user_id": "gone"}))
            users = run(crm.run({"action": "list"}))["users"]
            ids = [u["user_id"] for u in users]
            self.assertIn("keep", ids)
            self.assertNotIn("gone", ids)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2 — Validation and error handling
# ══════════════════════════════════════════════════════════════════════════════

class TestCRMValidation(unittest.TestCase):
    """Test schema validation and error behaviour."""

    def test_missing_action_raises(self):
        with TempCRM() as crm:
            with self.assertRaises((ValueError, KeyError, Exception)):
                run(crm.run({}))

    def test_empty_action_raises(self):
        with TempCRM() as crm:
            with self.assertRaises(ValueError):
                run(crm.run({"action": ""}))

    def test_unknown_action_raises(self):
        with TempCRM() as crm:
            with self.assertRaises(ValueError):
                run(crm.run({"action": "nuke_everything"}))

    def test_get_without_user_id_raises(self):
        with TempCRM() as crm:
            with self.assertRaises(ValueError):
                run(crm.run({"action": "get"}))

    def test_update_without_user_id_raises(self):
        with TempCRM() as crm:
            with self.assertRaises(ValueError):
                run(crm.run({"action": "update"}))

    def test_delete_without_user_id_raises(self):
        with TempCRM() as crm:
            with self.assertRaises(ValueError):
                run(crm.run({"action": "delete"}))

    def test_upsert_with_empty_name_stores_none(self):
        """An explicitly empty string name should be treated as None/cleared."""
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "v001", "name": "   "}))
            user = run(crm.run({"action": "get", "user_id": "v001"}))["user"]
            self.assertIsNone(user["name"])

    def test_schema_has_required_action_field(self):
        schema = CRMTool.schema()
        self.assertIn("action", schema.get("required", []))

    def test_user_record_has_expected_fields(self):
        with TempCRM() as crm:
            run(crm.run({"action": "upsert", "user_id": "f001", "name": "Mia"}))
            user = run(crm.run({"action": "get", "user_id": "f001"}))["user"]
            expected_fields = {
                "user_id", "name", "email", "phone", "address",
                "notes", "preferences", "metadata", "created_at", "updated_at",
            }
            self.assertEqual(set(user.keys()), expected_fields)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 3 — Concurrent access
# ══════════════════════════════════════════════════════════════════════════════

class TestCRMConcurrency(unittest.TestCase):
    """Test thread-safety of CRM operations."""

    def test_concurrent_upserts_no_corruption(self):
        """50 threads each upsert a distinct user — no exceptions, no data loss."""
        with TempCRM() as crm:
            errors = []

            def _upsert(uid):
                try:
                    asyncio.run(crm.run({"action": "upsert", "user_id": uid, "name": f"User {uid}"}))
                except Exception as exc:
                    errors.append(str(exc))

            threads = [threading.Thread(target=_upsert, args=(f"t{i}",)) for i in range(50)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [], f"Concurrent errors: {errors}")
            count = len(run(crm.run({"action": "list"}))["users"])
            self.assertEqual(count, 50)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 4 — Persistence across CRMTool instances
# ══════════════════════════════════════════════════════════════════════════════

class TestCRMPersistence(unittest.TestCase):
    """Records must survive after the CRMTool object is destroyed and recreated."""

    def test_data_persists_across_instances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "persist.sqlite3")

            crm1 = CRMTool(db_path=db_path)
            run(crm1.run({"action": "upsert", "user_id": "persist_user", "name": "Persist Me"}))
            del crm1

            crm2 = CRMTool(db_path=db_path)
            result = run(crm2.run({"action": "get", "user_id": "persist_user"}))
            self.assertIsNotNone(result["user"])
            self.assertEqual(result["user"]["name"], "Persist Me")


# ══════════════════════════════════════════════════════════════════════════════
# Standalone runner
# ══════════════════════════════════════════════════════════════════════════════

def run_crm_unit_tests() -> dict:
    """Run all CRM unit tests and return a summary dict."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestCRMCreate, TestCRMRead, TestCRMUpdate,
        TestCRMDelete, TestCRMValidation, TestCRMConcurrency,
        TestCRMPersistence,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return {
        "total": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "passed": result.wasSuccessful(),
    }


if __name__ == "__main__":
    summary = run_crm_unit_tests()
    print(f"\n{'='*60}")
    print(f"CRM UNIT TEST SUMMARY")
    print(f"  Total  : {summary['total']}")
    print(f"  Passed : {summary['total'] - summary['failures'] - summary['errors']}")
    print(f"  Failed : {summary['failures']}")
    print(f"  Errors : {summary['errors']}")
    print(f"  Result : {'✅ ALL PASSED' if summary['passed'] else '❌ SOME FAILED'}")
    print(f"{'='*60}")
