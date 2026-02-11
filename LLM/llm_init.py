import sys
from typing import Any, Dict, Optional

from app_logging.logger import logger
from config.config import LLMSettings
from LLM.llm_utils import initialize_llm, initialize_llm_from_config


def initialize_llms(llm_config: Optional[Dict[str, Any]] = None):
    if llm_config:
        logger.info("Initializing LLMs from provided configuration dictionary.")
        LLM = initialize_llm_from_config(llm_config.get("main"))
        LLM_SPARE = initialize_llm_from_config(llm_config.get("spare"))

        if LLM and LLM_SPARE:
            LLM = LLM.with_fallbacks([LLM_SPARE])
            logger.info("Main LLM with fallbacks is ready.")

        LLM_THINKING = initialize_llm_from_config(llm_config.get("thinking"))
        if not LLM_THINKING:
            LLM_THINKING = LLM
        elif LLM_SPARE:
            LLM_THINKING = LLM_THINKING.with_fallbacks([LLM_SPARE])
            logger.info("Thinking LLM with fallbacks is ready.")

        LLM_VALIDATION = initialize_llm_from_config(llm_config.get("validation"))
        if not LLM_VALIDATION:
            LLM_VALIDATION = LLM

        return LLM, LLM_THINKING, LLM_VALIDATION

    # Initialize the Main LLM, with fallback to Spare on failure
    LLM = None
    try:
        LLM = initialize_llm(llm_type="main", raise_on_error=True)
        if LLM:
            logger.info(f"Main LLM initialized: {type(LLM).__name__}")
    except Exception as e:
        logger.warning(f"Failed to initialize main LLM: {e}")
        logger.warning("Attempting to use spare LLM as main.")

    # Initialize the Spare LLM (only if main LLM failed or to set as fallback)
    LLM_SPARE = initialize_llm(llm_type="spare", raise_on_error=False)
    if LLM_SPARE:
        logger.info(f"Spare LLM initialized: {type(LLM_SPARE).__name__}")

    # If main LLM failed, use spare as main
    if not LLM and LLM_SPARE:
        LLM = LLM_SPARE
        logger.info("Using spare LLM as the main LLM.")
    # If main LLM succeeded, add spare as fallback
    elif LLM and LLM_SPARE:
        LLM = LLM.with_fallbacks([LLM_SPARE])
        logger.info("Main LLM with fallbacks is ready.")

    # If still no LLM, we can't continue
    if not LLM:
        logger.critical("Could not initialize any LLM. Exiting.")
        sys.exit(1)

    # Initialize the Thinking LLM (returns None on failure)
    LLM_THINKING = initialize_llm(llm_type="thinking", raise_on_error=False)
    if LLM_THINKING:
        logger.info(f"Thinking LLM initialized: {type(LLM_THINKING).__name__}")
        # Optionally, give the thinking LLM a fallback as well
        if LLM_SPARE:
            LLM_THINKING = LLM_THINKING.with_fallbacks([LLM_SPARE])
            logger.info("Thinking LLM with fallbacks is ready.")
    else:
        logger.warning(
            "Thinking LLM could not be initialized. Falling back to the main LLM."
        )
        LLM_THINKING = LLM

    # Initialize the Validation LLM (returns None on failure)
    LLM_VALIDATION = initialize_llm(llm_type="validation", raise_on_error=False)
    if LLM_VALIDATION:
        logger.info(f"Validation LLM initialized: {type(LLM_VALIDATION).__name__}")
    else:
        logger.warning(
            "Validation LLM could not be initialized. Falling back to the main LLM."
        )
        LLM_VALIDATION = LLM

    return LLM, LLM_THINKING, LLM_VALIDATION
