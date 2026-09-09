# desktop/tests/unit/test_main_window.py | v0.1.0 | MainWindow shell + banner (FR-DC-001/002)
from __future__ import annotations

from typing import Any

from limes_desktop.api.errors import ApiUnreachable
from limes_desktop.api.models import HealthInfo
from limes_desktop.config import ConnectionProfile, ProfileStore
from limes_desktop.state import SessionState
from limes_desktop.views.main_window import MainWindow
from test_main_window_support import FakeClient


def test_banner_refresh_shows_green_state_and_version(qtbot: Any) -> None:
    state = SessionState()
    client = FakeClient()
    win = MainWindow(state, ProfileStore(), lambda: client)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    # the startup probe already ran in __init__; refresh_banner is the test seam
    assert client.health_calls == 1
    win.refresh_banner()
    assert client.health_calls == 2
    assert win.banner.status_text() == "ok"
    assert not win.banner.is_unreachable()


def test_startup_probe_hits_health_and_shows_version(qtbot: Any) -> None:
    state = SessionState()
    client = FakeClient()
    win = MainWindow(state, ProfileStore(), lambda: client)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    assert client.health_calls == 1
    assert win.banner.status_text() == "ok"
    assert win.banner.version_label_text() == "ontology 1.0.0"


def test_unreachable_client_sets_banner_unreachable_without_exception(
    qtbot: Any,
) -> None:
    state = SessionState()
    client = FakeClient()
    client.fail = True
    win = MainWindow(state, ProfileStore(), lambda: client)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    win.refresh_banner()  # must not raise

    assert win.banner.is_unreachable()
    assert win.banner.status_text() != "ok"


def test_banner_refresh_timer_pausable(qtbot: Any) -> None:
    state = SessionState()
    win = MainWindow(state, ProfileStore(), FakeClient)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    win.refresh_banner()
    win.banner.client_factory = lambda: (_ for _ in ()).throw(ApiUnreachable("down"))
    win.refresh_banner()
    assert win.banner.is_unreachable()
    assert not win.banner._timer.isActive()

    # direct seam: tests drive refresh without waiting 10 s
    win.banner.client_factory = lambda: FakeClient()
    win.refresh_banner()
    assert not win.banner.is_unreachable()
    assert win.banner._timer.isActive()


def test_views_stacked_widget(qtbot: Any) -> None:
    state = SessionState()
    win = MainWindow(state, ProfileStore(), FakeClient)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    # since Task 6 the first stack page is the EntityView, not a placeholder;
    # Task 7 adds the NLQ view (page 1) and Cypher console (page 2)
    assert win.stack.count() > 0
    assert win.stack.widget(0) is win.entity_view
    assert win.stack.widget(1) is win.nlq_view
    assert win.stack.widget(2) is win.cypher_console
    for i in range(3, win.stack.count()):
        assert win.stack.widget(i).metaObject().className() == "QWidget"


def test_connection_changed_updates_banner_profile_and_reprobes(
    qtbot: Any,
) -> None:
    calls: dict[str, FakeClient] = {}

    def factory() -> FakeClient:
        # one client per profile's base_url, like the real __main__ factory
        return calls.setdefault("client", FakeClient())

    state = SessionState()
    win = MainWindow(state, ProfileStore(), factory)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    client = calls["client"]
    startup_calls = client.health_calls  # startup probe already ran

    profile = ConnectionProfile(name="local", base_url="http://127.0.0.1:9999")
    state.set_connection(profile)
    assert win.banner.profile_label_text() == "local http://127.0.0.1:9999"
    assert client.health_calls == startup_calls + 1  # immediate reprobe

    state.set_connection(None)
    assert win.banner.profile_label_text() == "disconnected"
    assert client.health_calls == startup_calls + 2


def test_fake_client_type_sanity() -> None:
    # FakeClient.health returns HealthInfo (mirrors the real client contract)
    c = FakeClient()
    assert isinstance(c.health(), HealthInfo)
