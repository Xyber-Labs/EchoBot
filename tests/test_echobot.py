import os

from radio.core.flow import RadioFlow

import config.config as _  # noqa

os.environ.setdefault("RADIO_DISABLE_OBS", "1")


def test_runner_initialization() -> None:
    """High-level test to ensure all lower-level components persist as expected so Runner is successfully built."""
    settings = _.Settings()

    runner = RadioFlow(settings)  # type: ignore
    assert runner is not None
    assert isinstance(runner, RadioFlow)


def test_runner_attributes() -> None:
    """Test that Runner instance has expected attributes."""
    settings = _.Settings()
    runner = RadioFlow(settings)  # type: ignore
    assert hasattr(runner, "youtube")
    assert hasattr(runner, "obs")
    assert hasattr(runner, "schedule_service")
    assert hasattr(runner, "bgm")
    assert hasattr(runner, "scene_player")
    assert hasattr(runner, "chat")
    assert hasattr(runner, "schedule")
    assert hasattr(runner, "_running")
