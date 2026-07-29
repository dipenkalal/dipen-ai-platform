from datetime import UTC, datetime
from types import SimpleNamespace

import collectors.system as system_module
import pytest


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0.0),
        (1024**3, 1.0),
        (5 * 1024**3, 5.0),
        (1536 * 1024**2, 1.5),
    ],
)
def test_bytes_to_gb(value, expected):
    assert system_module.bytes_to_gb(value) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "Less than one minute"),
        (30, "Less than one minute"),
        (60, "1 minute"),
        (120, "2 minutes"),
        (3600, "1 hour"),
        (7200, "2 hours"),
        (86400, "1 day"),
        (172800, "2 days"),
        (90000, "1 day, 1 hour"),
        (176400, "2 days, 1 hour"),
        (3660, "1 hour, 1 minute"),
        (3720, "1 hour, 2 minutes"),
        (90060, "1 day, 1 hour"),
    ],
)
def test_format_uptime(seconds, expected):
    assert system_module.format_uptime(seconds) == expected


def test_get_disk_usage(monkeypatch):
    fake_disk = SimpleNamespace(
        total=100 * 1024**3,
        used=40 * 1024**3,
        free=60 * 1024**3,
        percent=40.04,
    )

    calls = []

    def fake_disk_usage(path):
        calls.append(path)
        return fake_disk

    monkeypatch.setattr(
        system_module.psutil,
        "disk_usage",
        fake_disk_usage,
    )

    result = system_module.get_disk_usage("/data")

    assert result == {
        "path": "/data",
        "total_gb": 100.0,
        "used_gb": 40.0,
        "free_gb": 60.0,
        "percent": 40.0,
    }

    assert calls == ["/data"]


def test_get_system_status(monkeypatch):
    fake_memory = SimpleNamespace(
        total=16 * 1024**3,
        used=8 * 1024**3,
        available=7 * 1024**3,
        percent=50.04,
    )

    fake_now = datetime(
        2025,
        1,
        2,
        12,
        0,
        0,
        tzinfo=UTC,
    )

    fake_boot_time = datetime(
        2025,
        1,
        1,
        10,
        30,
        0,
        tzinfo=UTC,
    ).timestamp()

    class FakeDateTime:
        @classmethod
        def fromtimestamp(cls, value, tz=None):
            assert value == fake_boot_time
            assert tz is UTC
            return datetime.fromtimestamp(value, tz=tz)

        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return fake_now

    monkeypatch.setattr(
        system_module.psutil,
        "virtual_memory",
        lambda: fake_memory,
    )

    monkeypatch.setattr(
        system_module.psutil,
        "boot_time",
        lambda: fake_boot_time,
    )

    monkeypatch.setattr(
        system_module.psutil,
        "cpu_percent",
        lambda interval: 12.34,
    )

    def fake_cpu_count(logical):
        return 8 if logical else 4

    monkeypatch.setattr(
        system_module.psutil,
        "cpu_count",
        fake_cpu_count,
    )

    monkeypatch.setattr(
        system_module,
        "datetime",
        FakeDateTime,
    )

    disk_calls = []

    def fake_get_disk_usage(path):
        disk_calls.append(path)
        return {
            "path": path,
            "total_gb": 500.0,
            "used_gb": 200.0,
            "free_gb": 300.0,
            "percent": 40.0,
        }

    monkeypatch.setattr(
        system_module,
        "get_disk_usage",
        fake_get_disk_usage,
    )

    result = system_module.get_system_status()

    expected_seconds = int(
        (
            fake_now
            - datetime.fromtimestamp(
                fake_boot_time,
                tz=UTC,
            )
        ).total_seconds()
    )

    assert result == {
        "cpu": {
            "usage_percent": 12.3,
            "physical_cores": 4,
            "logical_threads": 8,
        },
        "memory": {
            "total_gb": 16.0,
            "used_gb": 8.0,
            "available_gb": 7.0,
            "percent": 50.0,
        },
        "uptime": {
            "seconds": expected_seconds,
            "formatted": "1 day, 1 hour",
        },
        "disks": {
            "system": {
                "path": "/",
                "total_gb": 500.0,
                "used_gb": 200.0,
                "free_gb": 300.0,
                "percent": 40.0,
            }
        },
    }

    assert disk_calls == ["/"]


def test_get_system_status_uses_home_anchor(monkeypatch):
    fake_memory = SimpleNamespace(
        total=1024**3,
        used=512 * 1024**2,
        available=512 * 1024**2,
        percent=50.0,
    )

    now = datetime(
        2025,
        1,
        1,
        0,
        1,
        0,
        tzinfo=UTC,
    )

    boot = datetime(
        2025,
        1,
        1,
        0,
        0,
        0,
        tzinfo=UTC,
    )

    class FakeDateTime:
        @classmethod
        def fromtimestamp(cls, value, tz=None):
            return boot

        @classmethod
        def now(cls, tz=None):
            return now

    class FakePath:
        @classmethod
        def home(cls):
            return SimpleNamespace(anchor="/custom-root/")

    monkeypatch.setattr(
        system_module.psutil,
        "virtual_memory",
        lambda: fake_memory,
    )
    monkeypatch.setattr(
        system_module.psutil,
        "boot_time",
        lambda: boot.timestamp(),
    )
    monkeypatch.setattr(
        system_module.psutil,
        "cpu_percent",
        lambda interval: 0,
    )
    monkeypatch.setattr(
        system_module.psutil,
        "cpu_count",
        lambda logical: 1,
    )
    monkeypatch.setattr(
        system_module,
        "datetime",
        FakeDateTime,
    )
    monkeypatch.setattr(
        system_module,
        "Path",
        FakePath,
    )

    captured = {}

    def fake_get_disk_usage(path):
        captured["path"] = path
        return {"path": path}

    monkeypatch.setattr(
        system_module,
        "get_disk_usage",
        fake_get_disk_usage,
    )

    result = system_module.get_system_status()

    assert captured["path"] == "/custom-root/"
    assert result["uptime"]["seconds"] == 60
    assert result["uptime"]["formatted"] == "1 minute"
