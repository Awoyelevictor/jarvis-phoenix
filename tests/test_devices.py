from app.devices import DeviceError, DeviceRegistry


def test_pairing_code_is_one_time_and_token_authenticates(tmp_path):
    registry = DeviceRegistry(str(tmp_path / "devices.sqlite3"))
    pairing = registry.create_pairing_code()
    paired = registry.pair(pairing["code"], "Phoenix Android", "android")

    assert registry.authenticate(paired["device_token"])["id"] == paired["device_id"]
    assert registry.authenticate("not-a-real-token") is None

    try:
        registry.pair(pairing["code"], "Second device", "android")
    except DeviceError as exc:
        assert "invalid or expired" in str(exc)
    else:
        raise AssertionError("Pairing code should only be usable once")


def test_command_queue_is_scoped_to_device_and_completes(tmp_path):
    registry = DeviceRegistry(str(tmp_path / "devices.sqlite3"))
    pairing = registry.create_pairing_code()
    paired = registry.pair(pairing["code"], "Windows PC", "windows")

    queued = registry.enqueue(paired["device_id"], "ping", {"source": "test"})
    claimed = registry.claim_next(paired["device_token"])
    assert claimed["command_id"] == queued["command_id"]
    assert claimed["payload"] == {"source": "test"}
    assert registry.claim_next(paired["device_token"]) is None

    assert registry.complete(paired["device_token"], queued["command_id"], {"ok": True})
    assert not registry.complete(paired["device_token"], queued["command_id"], {"ok": True})


def test_revoked_device_cannot_heartbeat_or_claim(tmp_path):
    registry = DeviceRegistry(str(tmp_path / "devices.sqlite3"))
    pairing = registry.create_pairing_code()
    paired = registry.pair(pairing["code"], "Test phone", "android")
    assert registry.revoke(paired["device_id"])

    try:
        registry.heartbeat(paired["device_token"])
    except DeviceError as exc:
        assert "invalid or revoked" in str(exc)
    else:
        raise AssertionError("Revoked device must not authenticate")


def test_unsupported_commands_are_rejected(tmp_path):
    registry = DeviceRegistry(str(tmp_path / "devices.sqlite3"))
    pairing = registry.create_pairing_code()
    paired = registry.pair(pairing["code"], "Test phone", "android")

    try:
        registry.enqueue(paired["device_id"], "delete_everything", {})
    except DeviceError as exc:
        assert "not enabled" in str(exc)
    else:
        raise AssertionError("Unknown command must be rejected")
