import operator
from dataclasses import dataclass, field

from typing_extensions import Annotated


@dataclass(kw_only=True)
class SummaryState:
    research_topic: Annotated[list, operator.add] = field(
        default_factory=list
    )  # Research topics list
    search_query: str = field(default=None)  # Search query
    web_research_results: Annotated[list, operator.add] = field(
        default_factory=list
    )  # Web research results
    news_article: str = field(default=None)  # News article
    news_article_title: str = field(default=None)  # News article title
    news_article_content: str = field(default=None)  # News article content
    news_article_validated: bool = field(default=False)  # News article validated
    news_article_attempt: int = field(default=0)  # News article attempt count
    should_create_article: bool = field(default=False)  # Should create tweet
    research_topics_counter: int = field(
        default=0
    )  # Research topics counter. For the overall topics list
    research_topics_total: int = field(
        default=0
    )  # Research topics total. For the overall topics list
    recommendations: str = field(default=None)  # Recommendations
    current_article_version: str = field(
        default=None
    )  # Current article version that has been created
    final_summaries: Annotated[list, operator.add] = field(
        default_factory=list
    )  # Final summaries


@dataclass(kw_only=True)
class SummaryStateInput:
    research_topic: str = field(default=None)  # Report topic


@dataclass(kw_only=True)
class SummaryStateOutput:
    news_article_title: str = field(default=None)  # News article title
    news_article_summary: str = field(default=None)  # News article summary
    news_article_content: str = field(default=None)  # News article content
    final_summaries: list = field(default=None)  # Final summaries
