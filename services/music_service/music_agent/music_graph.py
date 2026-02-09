import json
import os
from datetime import datetime

from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import END, START, StateGraph

from app_logging.logger import logger
from config.config import Settings
from LLM import clean_response
from services.music_service.media.soundcloud_upload import SoundCloudUploader
from services.music_service.music_agent.music_generation_prompt import (
    MUSIC_GENERATION_PROMPT, MUSIC_VALIDATION_PROMPT)
from services.music_service.music_agent.state import MusicGenerationState
from services.music_service.music_agent.sunoapi import generate_song_suno


class MusicGeneration:
    def __init__(
        self,
        LLM,
        LLM_THINKING,
        music_memory: dict,
        music_style: str,
        agent_personality: dict,
        agent_name: str,
        call_back_url: str,
        settings: Settings,
        history_file_path: str,
        agent_knowledge: dict,
    ):
        self.llm = LLM
        self.llm_thinking = LLM_THINKING
        self.music_memory = music_memory
        self.music_style = music_style
        self.agent_personality = agent_personality
        self.agent_name = agent_name
        self.call_back_url = call_back_url
        self.music_memory_counter = 0
        self.settings = settings
        self.history_file_path = history_file_path
        self.agent_knowledge = agent_knowledge
        self.graph = self._build_graph()

    def _build_graph(self):
        # Add nodes and edges
        builder = StateGraph(
            MusicGenerationState,
            input=MusicGenerationState,
            output=MusicGenerationState,
        )
        builder.add_node("generate_song_prompt", self.generate_song_prompt)
        builder.add_node("validate_song_prompt", self.validate_song_prompt)
        builder.add_node("generate_song", self.generate_song)
        builder.add_node("send_song_to_soundcloud", self.send_song_to_soundcloud)

        builder.add_edge(START, "generate_song_prompt")
        builder.add_edge("generate_song_prompt", "validate_song_prompt")
        builder.add_conditional_edges(
            "validate_song_prompt",
            self.route_validate_song_prompt,
            {
                "generate_song": "generate_song",
                "generate_song_prompt": "generate_song_prompt",
                END: END,
            },
        )
        builder.add_edge("generate_song", "send_song_to_soundcloud")
        builder.add_edge("send_song_to_soundcloud", END)

        graph = builder.compile()
        logger.info("Graph compiled successfully")

        # Script to save the graph as an image file
        # Save the graph visualization as an image file
        # logger.info("Saving graph as image")
        # try:
        #     # Get the directory of the current file
        #     output_dir = os.path.dirname(os.path.abspath(__file__))
        #     output_path = os.path.join(output_dir, "music_graph.png")

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

    async def generate_song_prompt(self, state: MusicGenerationState):
        """
        LangGraph node that generates a song prompt based on the music memory.
        """

        formated_prompt = MUSIC_GENERATION_PROMPT.format(
            music_memory=self.music_memory,
            music_style=self.music_style,
            agent_personality=self.agent_personality,
            agent_name=self.agent_name,
            agent_knowledge=self.agent_knowledge,
        )
        result = await self.llm_thinking.ainvoke(formated_prompt)
        result = JsonOutputParser().parse(clean_response(result.content))
        state.song_name = result["song_name"]
        state.song_prompt = result["song_prompt"]
        state.negativeTags = result["negativeTags"]
        state.vocalGender = result["vocalGender"]
        state.styleWeight = result["styleWeight"]
        state.weirdnessConstraint = result["weirdnessConstraint"]
        state.audioWeight = result["audioWeight"]
        logger.info(f"Song prompt {state.song_prompt}")
        logger.info(f"Full result {result}")
        return state

    async def validate_song_prompt(self, state: MusicGenerationState):
        """
        LangGraph node that validates a song prompt.
        """

        song_prompt_length = len(state.song_prompt)
        logger.info(f"Song prompt length {song_prompt_length}")
        formated_prompt = MUSIC_VALIDATION_PROMPT.format(
            song_name=state.song_name,
            song_prompt=state.song_prompt,
            song_prompt_length=song_prompt_length,
            music_memory=self.music_memory,
            music_style=self.music_style,
            agent_personality=self.agent_personality,
            agent_name=self.agent_name,
            negativeTags=state.negativeTags,
            vocalGender=state.vocalGender,
            styleWeight=state.styleWeight,
            weirdnessConstraint=state.weirdnessConstraint,
            audioWeight=state.audioWeight,
        )
        result = await self.llm.ainvoke(formated_prompt)
        result = JsonOutputParser().parse(clean_response(result.content))
        state.song_prompt_validated = result.get("song_prompt_validated", False)
        state.recommendations = result.get("recommendations")
        state.negativeTags = result.get("negativeTags")
        state.vocalGender = result.get("vocalGender")
        logger.info(f"Song prompt validated {state.song_prompt_validated}")
        logger.info(f"Recommendations {state.recommendations}")
        return state

    async def route_validate_song_prompt(self, state: MusicGenerationState):
        """
        LangGraph node that routes the validate song prompt.
        """
        if state.song_prompt_validated:
            return "generate_song"
        elif not state.song_prompt_validated and state.generate_song_prompt_counter < 3:
            state.generate_song_prompt_counter += 1
            return "generate_song_prompt"
        else:
            return END

    async def generate_song(self, state: MusicGenerationState):
        """
        LangGraph node that generates a song based on the song prompt.
        """
        try:
            song_prompt = state.song_prompt
            if state.recommendations:
                song_prompt += f"\n{state.recommendations}"

            if len(song_prompt) > 400:
                logger.warning("Prompt is too long, truncating to 400 characters.")
                song_prompt = song_prompt[:400]

            filenames, titles = generate_song_suno(
                suno_settings=self.settings.suno,
                song_prompt=song_prompt,
                negativeTags=state.negativeTags,
                vocalGender=state.vocalGender,
                styleWeight=state.styleWeight,
                weirdnessConstraint=state.weirdnessConstraint,
                audioWeight=state.audioWeight,
                output_dir=self.settings.media.suno_output_dir,
            )
        except Exception as e:
            logger.error(f"Error generating song: {e}")
            state.error_message = (
                f"Error during song generation: {e}"  # Set an error message in state
            )
            return state  # Return the state, not END
        if filenames:
            logger.info(f"Filenames {filenames}")

            history_file_path = self.history_file_path
            logger.info(f"History file path {history_file_path}")
            music_generation_history = {"music_generation_history": []}
            if (
                os.path.exists(history_file_path)
                and os.path.getsize(history_file_path) > 0
            ):
                with open(history_file_path, "r") as f:
                    try:
                        loaded_data = json.load(f)
                        if (
                            isinstance(loaded_data, dict)
                            and "music_generation_history" in loaded_data
                        ):
                            music_generation_history = loaded_data
                    except json.JSONDecodeError:
                        logger.warning(
                            f"{history_file_path} is corrupted. Starting a new history."
                        )

            if music_generation_history["music_generation_history"]:
                new_id = (
                    music_generation_history["music_generation_history"][-1].get(
                        "id", 0
                    )
                    + 1
                )
            else:
                new_id = 1

            music_generation_history["music_generation_history"].append(
                {
                    "id": new_id,
                    "song_name": titles[0] if titles else state.song_name,
                    "song_prompt": state.song_prompt,
                    "negativeTags": state.negativeTags,
                    "vocalGender": state.vocalGender,
                    "styleWeight": state.styleWeight,
                    "weirdnessConstraint": state.weirdnessConstraint,
                    "audioWeight": state.audioWeight,
                    "created_at": datetime.now().strftime("%Y-%m-%d"),
                }
            )
            with open(self.history_file_path, "w") as f:
                json.dump(music_generation_history, f, indent=4)
            state.song_filepath = filenames[0]
            if titles:
                state.song_name = titles[0]
            logger.info(f"Song generated and saved to {state.song_filepath}")

        else:
            logger.error("Failed to generate song")
        return state

    def should_continue(self, state):
        if state.song_filepath:
            return "end"
        else:
            return "generate_song_prompt"

    async def send_song_to_soundcloud(self, state: MusicGenerationState):
        """
        LangGraph node that sends a song to soundcloud using api.
        """
        try:
            uploader = SoundCloudUploader()
            result = uploader.upload(
                file_path=state.song_filepath,
                playlist_name=self.settings.soundcloud.SOUNDCLOUD_PLAYLIST_NAME,
                track_title=state.song_name,  # Use the updated song_name from the state
            )
            state.song_sent_soundcloud = result
        except Exception as e:
            logger.error(f"Error sending song to soundcloud: {e}")
            state.song_sent_soundcloud = False
        return state
