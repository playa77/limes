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

    win.refresh_banner()

    assert client.health_calls == 1
    assert win.banner.status_text() == "ok"
    assert not win.banner.is_unreachable()


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


def test_views_placeholder_stacked_widget(qtbot: Any) -> None:
    state = SessionState()
    win = MainWindow(state, ProfileStore(), FakeClient)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    assert win.stack.count() > 0
    for i in range(win.stack.count()):
        assert win.stack.widget(i).metaObject().className() == "QWidget"


def test_connection_changed_updates_banner_profile(qtbot: Any) -> None:
    state = SessionState()
    win = MainWindow(state, ProfileStore(), FakeClient)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    profile = ConnectionProfile(name="local", base_url="http://127.0.0.1:9999")
    state.set_connection(profile)
    assert win.banner.profile_label_text() == "local http://127.0.0.1:9999"

    state.set_connection(None)
    assert win.banner.profile_label_text() == "disconnected"


def test_fake_client_type_sanity() -> None:
    # FakeClient.health returns HealthInfo (mirrors the real client contract)
    c = FakeClient()
    assert isinstance(c.health(), HealthInfo)
