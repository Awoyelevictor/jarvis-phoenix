from app.memory import MemoryStore


def test_memory_persists_and_can_be_deleted(tmp_path):
    store = MemoryStore(
        database_path=str(tmp_path / "memory.sqlite3"),
        owner_id="c2ed5c38-8d14-42de-a095-88f6d9f30a22",
    )
    saved = store.add("I prefer concise explanations", memory_type="preference")

    assert store.list()[0]["content"] == "I prefer concise explanations"
    assert store.context()[0].endswith("I prefer concise explanations")
    assert store.delete(saved["id"]) is True
    assert store.list() == []
    assert store.delete(saved["id"]) is False


def test_cloud_memories_require_explicit_approval(tmp_path):
    store = MemoryStore(
        database_path=str(tmp_path / "memory.sqlite3"),
        owner_id="c2ed5c38-8d14-42de-a095-88f6d9f30a22",
    )
    local = store.add("Keep this on this device", approved_for_cloud_sync=False)
    approved = store.add("Sync this approved note", approved_for_cloud_sync=True)

    rows = {item["content"]: item["approved_for_cloud_sync"] for item in store.list()}
    assert rows[local["content"]] == 0
    assert rows[approved["content"]] == 1
