"""Persistent local memory with optional approved Supabase cloud sync."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class MemoryStore:
    def __init__(self, database_path: str | None = None, supabase_url: str = "", service_key: str = "", owner_id: str = ""):
        default_dir = Path.home() / ".ultron"
        default_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = Path(database_path or os.getenv("ULTRON_MEMORY_DB", str(default_dir / "memory.sqlite3"))).expanduser()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.supabase_url = supabase_url.rstrip("/")
        self.service_key = service_key
        self.owner_id = owner_id or self._load_owner_id(default_dir / "owner_id")
        self._initialize()

    @staticmethod
    def _load_owner_id(path: Path) -> str:
        configured = os.getenv("ULTRON_OWNER_ID", "").strip()
        if configured:
            return str(uuid.UUID(configured))
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                return str(uuid.UUID(path.read_text(encoding="utf-8").strip()))
            except (ValueError, OSError):
                pass
        value = str(uuid.uuid4())
        path.write_text(value, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return value

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute("""
                create table if not exists memories (
                    id text primary key,
                    owner_id text not null,
                    memory_type text not null,
                    content text not null,
                    approved_for_cloud_sync integer not null default 0,
                    created_at text not null,
                    updated_at text not null
                )
            """)
            db.execute("create index if not exists memories_owner_created on memories(owner_id, created_at desc)")

    @property
    def cloud_configured(self) -> bool:
        return bool(self.supabase_url and self.service_key)

    def _cloud_request(self, method: str, path: str, payload=None):
        if not self.cloud_configured:
            return None
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }
        if method == "POST":
            headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        request = Request(f"{self.supabase_url}/rest/v1/{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=12) as response:
                body = response.read()
            return json.loads(body.decode("utf-8")) if body else None
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise RuntimeError(f"Cloud memory sync failed: {exc}") from exc

    def add(self, content: str, memory_type: str = "conversation", approved_for_cloud_sync: bool = False) -> dict:
        content = content.strip()
        if not content:
            raise ValueError("Memory cannot be empty.")
        if memory_type not in {"profile", "preference", "project", "conversation", "instruction"}:
            memory_type = "conversation"
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "id": str(uuid.uuid4()),
            "owner_id": self.owner_id,
            "memory_type": memory_type,
            "content": content[:4000],
            "approved_for_cloud_sync": bool(approved_for_cloud_sync),
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as db:
            db.execute(
                "insert into memories (id, owner_id, memory_type, content, approved_for_cloud_sync, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?)",
                (item["id"], item["owner_id"], item["memory_type"], item["content"], int(item["approved_for_cloud_sync"]), now, now),
            )
        if item["approved_for_cloud_sync"] and self.cloud_configured:
            try:
                self._cloud_request("POST", "ultron_memories?on_conflict=id", [item])
                item["cloud_synced"] = True
            except RuntimeError:
                item["cloud_synced"] = False
        else:
            item["cloud_synced"] = False
        return item

    def list(self, limit: int = 40) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "select id, memory_type, content, approved_for_cloud_sync, created_at from memories where owner_id = ? order by created_at desc limit ?",
                (self.owner_id, max(1, min(limit, 100))),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete(self, memory_id: str) -> bool:
        with self._connect() as db:
            row = db.execute(
                "select id, approved_for_cloud_sync from memories where id = ? and owner_id = ?",
                (memory_id, self.owner_id),
            ).fetchone()
            if row is None:
                return False
            db.execute("delete from memories where id = ? and owner_id = ?", (memory_id, self.owner_id))
        if row["approved_for_cloud_sync"] and self.cloud_configured:
            try:
                self._cloud_request(
                    "DELETE",
                    f"ultron_memories?id=eq.{quote(memory_id)}&owner_id=eq.{quote(self.owner_id)}",
                )
            except RuntimeError:
                # Local deletion succeeds; cloud cleanup can be retried separately.
                pass
        return True

    def context(self, limit: int = 20) -> list[str]:
        local = self.list(limit)
        seen = {item["content"] for item in local}
        if self.cloud_configured:
            query = (
                "ultron_memories?select=id,memory_type,content,created_at"
                f"&owner_id=eq.{quote(self.owner_id)}&approved_for_cloud_sync=eq.true"
                "&order=created_at.desc&limit=40"
            )
            try:
                remote = self._cloud_request("GET", query) or []
                for item in remote:
                    if item.get("content") and item["content"] not in seen:
                        local.append(item)
                        seen.add(item["content"])
            except RuntimeError:
                pass
        return [f"- {item['memory_type']}: {item['content']}" for item in local[:limit]]

    def sync_approved(self) -> int:
        if not self.cloud_configured:
            return 0
        with self._connect() as db:
            rows = db.execute(
                "select id, owner_id, memory_type, content, approved_for_cloud_sync, created_at, updated_at from memories where owner_id = ? and approved_for_cloud_sync = 1",
                (self.owner_id,),
            ).fetchall()
        if not rows:
            return 0
        self._cloud_request("POST", "ultron_memories?on_conflict=id", [dict(row) for row in rows])
        return len(rows)
