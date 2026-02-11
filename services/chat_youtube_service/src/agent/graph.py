from __future__ import annotations

import datetime
import time
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import END, START, StateGraph

from app_logging.logger import logger
from LLM import clean_response
from services.chat_youtube_service.src.agent.prompts import (ATTACK_PROMPT,
                                                             REPLY_PROMPT,
                                                             SCAM_PROMPT)
from services.chat_youtube_service.src.agent.state import YoutubeState


class Youtube_Responder_Agent:
    def __init__(
        self,
        agent_name: str,
        llm,
        llm_thinking,
        llm_validation,
        agent_personality,
        agent_knowledge,
        youtube_disclaimer,
        settings,
        chat_rules,
    ) -> None:
        self.llm = llm
        self.llm_thinking = llm_thinking
        self.llm_validation = llm_validation
        self.agent_personality = agent_personality
        self.agent_knowledge = agent_knowledge
        self.agent_name = agent_name
        self._personality: str = agent_personality
        self.youtube_disclaimer = youtube_disclaimer
        self.settings = settings
        self.chat_rules = chat_rules
        self.graph = self._build_graph()
        self._llm_last_refresh = time.time()

    def _extract_message_text(self, message: Any) -> str:
        """Extract message text from state, handling both string and dict formats."""
        if isinstance(message, str):
            return message
        elif isinstance(message, dict):
            return message.get("message", str(message))
        else:
            return str(message)

    def _build_graph(self):
        builder = StateGraph(YoutubeState)
        # ------------------------------------------------------------------------------------------------
        # Nodes
        # ------------------------------------------------------------------------------------------------
        builder.add_node("input_scam_validation", self.input_scam_validation)
        builder.add_node("input_attack_validation", self.input_attack_validation)
        builder.add_node("create_reply", self.create_reply)

        # ------------------------------------------------------------------------------------------------
        # Define edges of the graph
        # ------------------------------------------------------------------------------------------------
        builder.add_edge(START, "input_scam_validation")

        builder.add_conditional_edges(
            "input_scam_validation",
            self.route_after_scam_check,
            {"input_attack_validation": "input_attack_validation", "end": END},
        )

        builder.add_conditional_edges(
            "input_attack_validation",
            self.route_after_attack_check,
            {"create_reply": "create_reply", "end": END},
        )

        builder.add_edge("create_reply", END)

        # ------------------------------------------------------------------------------------------------
        # Build the graph
        # ------------------------------------------------------------------------------------------------

        graph = builder.compile()
        logger.info("Graph compiled successfully")

        # ------------------------------------------------------------------------------------------------
        # Plotting the graph
        # ------------------------------------------------------------------------------------------------
        # Script to save the graph as an image file
        # Save the graph visualization as an image file
        # logger.info("Saving graph as image")
        # try:

        #     # Get the directory of the current file
        #     output_dir = os.path.dirname(os.path.abspath(__file__))
        #     output_path = os.path.join(output_dir, "youtube_responder_graph.png")

        #     # Save the graph visualization as a PNG file
        #     try:
        #         # Use the appropriate method to save the graph
        #         # The get_graph() method accesses the internal graph representation
        #         graph_image = graph.get_graph().draw_mermaid_png()
        #         with open(output_path, "wb") as f:
        #             f.write(graph_image)
        #         logger.info(f"Graph saved to {output_path}")
        #     except Exception as e:
        #         logger.error(f"Error saving graph: {e}")
        # except Exception as e:
        #     logger.error(f"Error saving graph: {e}")

        return graph

    def route_after_scam_check(self, state: YoutubeState):
        if state["scam_result"]:
            return "end"
        return "input_attack_validation"

    def route_after_attack_check(self, state: YoutubeState):
        if state["is_attack"]:
            return "end"
        return "create_reply"

    async def input_scam_validation(self, state: YoutubeState) -> YoutubeState:
        # Check if the message is a scam
        user_message = self._extract_message_text(state["message"])
        scam_promt_formated = SCAM_PROMPT.format(user_message=user_message)

        scam_check_response = await self.llm.ainvoke(scam_promt_formated)
        scam_check_response = JsonOutputParser().parse(
            clean_response(scam_check_response.content)
        )

        logger.info(f"Scam check response: {scam_check_response}")

        if isinstance(scam_check_response, list):
            scam_check_response = scam_check_response[0]

        is_scam_str = str(scam_check_response.get("is_scam", "false")).lower()
        is_scam = is_scam_str == "true"
        state["scam_result"] = is_scam

        return state

    async def input_attack_validation(self, state: YoutubeState) -> YoutubeState:
        """
        This node checks if the user's message is an attack.
        """
        user_message = self._extract_message_text(state["message"])
        attack_prompt_formatted = ATTACK_PROMPT.format(user_message=user_message)

        attack_check_response = await self.llm.ainvoke(attack_prompt_formatted)
        attack_check_response = JsonOutputParser().parse(
            clean_response(attack_check_response.content)
        )

        logger.info(f"Attack check response: {attack_check_response}")

        if isinstance(attack_check_response, list):
            attack_check_response = attack_check_response[0]

        is_attack_str = str(attack_check_response.get("is_attack", "false")).lower()
        is_attack = is_attack_str == "true"
        state["is_attack"] = is_attack

        return state

    async def create_reply(self, state: YoutubeState) -> YoutubeState:
        """
        This node is dedicated to create the reply to the user's message.
        """

        chat_history = state.get("chat_history", [])
        user_recent_messages = state.get("user_recent_messages", [])
        author = state.get("author", "User")
        user_message = self._extract_message_text(state["message"])

        logger.info(f"Chat history: {chat_history}")
        logger.info(f"User recent messages: {user_recent_messages}")

        current_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # Format chat history for better readability
        formatted_chat_history = ""
        if chat_history:
            formatted_chat_history = "\n".join(
                [
                    f"  - {msg.get('author', 'Unknown')}: {msg.get('message', '')} → Agent: {msg.get('agent_reply_text', '')}"
                    for msg in chat_history[-10:]  # Last 10 exchanges
                ]
            )
        else:
            formatted_chat_history = "  (No previous conversation history)"

        # Format user's recent messages for context
        formatted_user_history = ""
        if user_recent_messages:
            formatted_user_history = "\n".join(
                [f"  - {msg.get('message', '')}" for msg in user_recent_messages]
            )
            logger.info(f"Formatted user history: {formatted_user_history}")
        else:
            formatted_user_history = (
                "  (This is the user's first message in this conversation)"
            )
            logger.info(f"Formatted user history: {formatted_user_history}")

        reply_prompt = REPLY_PROMPT.format(
            agent_personality=self.agent_personality,
            user_message=user_message,
            author=author,
            agent_knowledge=self.agent_knowledge,
            chat_history=formatted_chat_history,
            user_recent_messages=formatted_user_history,
            youtube_disclaimer=self.youtube_disclaimer,
            chat_rules=self.chat_rules,
            current_date=current_date,
        )

        reply_response = await self.llm.ainvoke(reply_prompt)
        reply_response = JsonOutputParser().parse(
            clean_response(reply_response.content)
        )

        if isinstance(reply_response, list):
            reply_response = reply_response[0]

        reply_text = reply_response.get("reply_text", "")
        state["agent_reply_text"] = reply_text
        logger.info(f"Reply text: {reply_text}")
        return state
