"""Secure device pairing and command queue for the ULTRON multi-device core.

The registry stores only hashes of pairing codes and device bearer tokens.
It uses SQLite so it works in local development without extra services; set
ULTRON_DEVICE_DB to a persistent mounted path in cloud deployments.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class DeviceError(ValueError):
    """A safe, expected device-registry error."""


class DeviceRegistry:
    def __init__(self, database_path: str | None = None):
        default_dir = Path.home() / ".ultron"
        default_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = Path(
            database_path or os.getenv("ULTRON_DEVICE_DB", str(default_dir / "devices.sqlite3"))
        ).expanduser()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys = ON")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS device_pairings (
                    code_hash TEXT PRIMARY KEY,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    revoked INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS device_commands (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL REFERENCES devices(id),
                    command TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    created_at TEXT NOT NULL,
                    claimed_at TEXT,
                    completed_at TEXT,
                    result TEXT
                );
                CREATE INDEX IF NOT EXISTS device_commands_queue
                    ON device_commands(device_id, status, created_at);
            """)
        try:
            self.database_path.chmod(0o600)
        except OSError:
            pass

    def create_pairing_code(self, ttl_seconds: int = 300) -> dict[str, Any]:
        ttl_seconds = max(60, min(int(ttl_seconds), 600))
        code = secrets.token_urlsafe(9)
        now = _now()
        expires = now + timedelta(seconds=ttl_seconds)
        with self._connect() as db:
            db.execute("DELETE FROM device_pairings WHERE expires_at < ?", (_stamp(now),))
            db.execute(
                "INSERT INTO device_pairings(code_hash, expires_at, created_at) VALUES (?, ?, ?)",
                (_digest(code), _stamp(expires), _stamp(now)),
            )
        return {"code": code, "expires_at": _stamp(expires), "expires_in": ttl_seconds}

    def pair(self, code: str, name: str, platform: str) -> dict[str, str]:
        code = code.strip()
        name = name.strip()[:80]
        platform = platform.strip().lower()[:32]
        if not code or not name or not platform:
            raise DeviceError("Pairing code, device name, and platform are required.")
        now = _stamp(_now())
        token = secrets.token_urlsafe(36)
        device_id = str(uuid.uuid4())
        with self._connect() as db:
            pairing = db.execute(
                "SELECT code_hash, expires_at FROM device_pairings WHERE code_hash = ?",
                (_digest(code),),
            ).fetchone()
            if pairing is None or pairing["expires_at"] <= now:
                if pairing is not None:
                    db.execute("DELETE FROM device_pairings WHERE code_hash = ?", (_digest(code),))
                raise DeviceError("Pairing code is invalid or expired.")
            db.execute("DELETE FROM device_pairings WHERE code_hash = ?", (_digest(code),))
            db.execute(
                """INSERT INTO devices(id, name, platform, token_hash, created_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (device_id, name, platform, _digest(token), now, now),
            )
        return {"device_id": device_id, "device_token": token, "name": name, "platform": platform}

    def authenticate(self, token: str) -> dict[str, str] | None:
        if not token:
            return None
        with self._connect() as db:
            row = db.execute(
                "SELECT id, name, platform FROM devices WHERE token_hash = ? AND revoked = 0",
                (_digest(token),),
            ).fetchone()
        return dict(row) if row else None

    def heartbeat(self, token: str) -> dict[str, Any]:
        device = self.authenticate(token)
        if not device:
            raise DeviceError("Device credential is invalid or revoked.")
        now = _stamp(_now())
        with self._connect() as db:
            db.execute("UPDATE devices SET last_seen_at = ? WHERE id = ?", (now, device["id"]))
        return {"ok": True, "device_id": device["id"], "last_seen_at": now}

    def list_devices(self) -> list[dict[str, Any]]:
        cutoff = _stamp(_now() - timedelta(seconds=90))
        with self._connect() as db:
            rows = db.execute(
                """SELECT id, name, platform, created_at, last_seen_at, revoked
                   FROM devices ORDER BY created_at DESC"""
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["online"] = bool(item["last_seen_at"] and item["last_seen_at"] >= cutoff and not item["revoked"])
            item["revoked"] = bool(item["revoked"])
            result.append(item)
        return result

    def revoke(self, device_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("UPDATE devices SET revoked = 1 WHERE id = ?", (device_id,))
        return cursor.rowcount > 0

    def enqueue(self, device_id: str, command: str, payload: dict[str, Any] | None = None) -> dict[str, str]:
        allowed = {"open_app", "open_url", "run_tests", "inspect_project", "notify", "ping"}
        if command not in allowed:
            raise DeviceError("Unsupported command. This command type is not enabled.")
        if payload is not None and not isinstance(payload, dict):
            raise DeviceError("Command payload must be an object.")
        safe_payload = json.dumps(payload or {}, ensure_ascii=False)
        if len(safe_payload) > 12000:
            raise DeviceError("Command payload is too large.")
        command_id = str(uuid.uuid4())
        now = _stamp(_now())
        with self._connect() as db:
            device = db.execute(
                "SELECT id FROM devices WHERE id = ? AND revoked = 0", (device_id,)
            ).fetchone()
            if device is None:
                raise DeviceError("Device was not found or has been revoked.")
            db.execute(
                """INSERT INTO device_commands(id, device_id, command, payload, status, created_at)
                   VALUES (?, ?, ?, ?, 'queued', ?)""",
                (command_id, device_id, command, safe_payload, now),
            )
        return {"command_id": command_id, "status": "queued", "created_at": now}

    def claim_next(self, token: str) -> dict[str, Any] | None:
        device = self.authenticate(token)
        if not device:
            raise DeviceError("Device credential is invalid or revoked.")
        now = _stamp(_now())
        with self._connect() as db:
            row = db.execute(
                """SELECT id, command, payload, created_at FROM device_commands
                   WHERE device_id = ? AND status = 'queued'
                   ORDER BY created_at LIMIT 1""",
                (device["id"],),
            ).fetchone()
            if row is None:
                return None
            cursor = db.execute(
                """UPDATE device_commands SET status = 'claimed', claimed_at = ?
                   WHERE id = ? AND status = 'queued'""",
                (now, row["id"]),
            )
            if cursor.rowcount != 1:
                return None
        return {
            "command_id": row["id"],
            "command": row["command"],
            "payload": json.loads(row["payload"]),
            "created_at": row["created_at"],
        }

    def complete(self, token: str, command_id: str, result: dict[str, Any]) -> bool:
        device = self.authenticate(token)
        if not device:
            raise DeviceError("Device credential is invalid or revoked.")
        if not isinstance(result, dict) or len(json.dumps(result, ensure_ascii=False)) > 12000:
            raise DeviceError("Command result must be a small JSON object.")
        now = _stamp(_now())
        with self._connect() as db:
            cursor = db.execute(
                """UPDATE device_commands SET status = 'completed', completed_at = ?, result = ?
                   WHERE id = ? AND device_id = ? AND status = 'claimed'""",
                (now, json.dumps(result, ensure_ascii=False), command_id, device["id"]),
            )
        return cursor.rowcount == 1
