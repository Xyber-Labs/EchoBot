from typing import Any, Dict, List, Optional, TypedDict


class YoutubeState(TypedDict):
    message: Dict[str, Any]
    author: Optional[str]
    chat_history: List[Dict[str, Any]]
    user_recent_messages: List[Dict[str, Any]]
    scam_result: Any
    decision: Dict[str, str]
    reply_prompt: Optional[str]
    agent_reply_text: Optional[str]
    need_web_research: bool
    is_attack: bool
    skip: bool
