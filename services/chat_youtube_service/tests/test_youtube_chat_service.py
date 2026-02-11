from __future__ import annotations

from types import SimpleNamespace

from services.chat_youtube_service.src.youtube_chat_service import YoutubeChatService


class FakeYoutubeClient:
    def __init__(self) -> None:
        self.current_watch_url = "https://youtube.test/watch?v=abc"
        self.current_broadcast_id = "broadcast-1"
        self.current_stream_key = "stream-key-1"
        self.current_live_chat_id = "live-chat-1"
        self.cleared = False

    def create_new_broadcast(self, title_prefix: str, force: bool = False):
        assert title_prefix == "EchoBot"
        assert force is False
        return ("stream-key-1", self.current_watch_url, self.current_broadcast_id, True)

    def get_live_chat_id(self, broadcast_id: str) -> str:
        assert broadcast_id == "broadcast-1"
        return "live-chat-1"

    def get_chat_messages(self, live_chat_id: str):
        assert live_chat_id == "live-chat-1"
        return SimpleNamespace(
            items=[
                SimpleNamespace(id="m1"),
                SimpleNamespace(id="m2"),
            ]
        )

    def filter_relevant_messages(self, messages):
        return [m for m in messages if m.id == "m2"]

    def post_chat_message(self, live_chat_id: str, message: str) -> None:
        assert live_chat_id == "live-chat-1"
        assert message == "reply"

    def is_broadcast_active(self, broadcast_id: str) -> bool:
        return broadcast_id == "broadcast-1"

    def clear_broadcast_parameters(self) -> None:
        self.cleared = True


def test_start_broadcast_returns_expected_payload() -> None:
    service = YoutubeChatService(FakeYoutubeClient())
    result = service.start_broadcast(title_prefix="EchoBot", force=False)
    assert result["stream_key"] == "stream-key-1"
    assert result["broadcast_id"] == "broadcast-1"
    assert result["watch_url"] == "https://youtube.test/watch?v=abc"
    assert result["is_new"] is True


def test_fetch_relevant_messages_filters_answered_and_irrelevant() -> None:
    service = YoutubeChatService(FakeYoutubeClient())
    live_chat_id, relevant = service.fetch_relevant_messages(
        "broadcast-1", answered_ids={"m1"}
    )
    assert live_chat_id == "live-chat-1"
    assert len(relevant) == 1
    assert relevant[0].id == "m2"


def test_get_broadcast_details_returns_active_broadcast_data() -> None:
    service = YoutubeChatService(FakeYoutubeClient())
    details = service.get_broadcast_details()
    assert details["watch_url"] == "https://youtube.test/watch?v=abc"
    assert details["broadcast_id"] == "broadcast-1"
    assert details["live_chat_id"] == "live-chat-1"
