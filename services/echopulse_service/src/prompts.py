from datetime import datetime

# Get current date in a readable format


def get_current_date():
    return datetime.now().strftime("%B %d, %Y")


query_writer_instructions = """
<GOAL>
Your goal is to generate a targeted web search query and research topic for the generation of a news article.
</GOAL>

<CONTEXT>
Current date: {current_date}
Current topic: {current_topic}

Please ensure your queries account for the most current information available as of this date.
You need to generate a creative and innovative research topic and query based on the current topic, incorporating current data to ensure up-to-date results.
</CONTEXT>

<STRUCTURE>
Format your response as a JSON object with ALL three of these exact keys:
- "query": The actual search query string
- "research_topic": A clear, concise research topic that describes what you're investigating
- "rationale": A brief explanation of why this query and topic are relevant

Ensure that any double quotes within the JSON values are properly escaped (e.g., \"text with quotes\").
</STRUCTURE>

<EXAMPLE>
{{
    "query": "machine learning transformer architecture explained",
    "research_topic": "Understanding Transformer Models in AI",
    "rationale": "Understanding the fundamental structure of transformer models for current AI developments"
}}
</EXAMPLE>

Provide your response in JSON format:"""

summarise_web_research_results_instructions = """
<GOAL>
Generate a structured final research report based on the provided web research {web_research_results} and the research topic {current_topic}.
</GOAL>

<STRUCTURE>
Output ONLY a valid JSON object with these exact keys:
- "title": A concise, engaging title for the report (string).
- "executive_summary": A brief overview of the key findings (string, 2-3 paragraphs, no repetitions).

Do NOT include a sources section; it will be added separately.
Do NOT output any text before or after the JSON object.
Make the summary short and concise.
Ensure that any double quotes within the JSON values are properly escaped (e.g., \"text with quotes\").
</STRUCTURE>

<REQUIREMENTS>
- Ensure the content is professional, clear, and free of repetitions or errors.
- Base it strictly on the provided web research results, synthesizing information coherently.
- Avoid hallucinations; stick to the facts from the summary.
- Ensure the summary is short and concise.
- If web_research_results are empty please output "executive_summary": "None"
</REQUIREMENTS>

<CRITICAL>
Summary should be less than 300 words.
</CRITICAL>

<EXAMPLE>
{{
  "title": "Sample Report",
  "executive_summary": "Paragraph 1... Paragraph 2..."
}}
</EXAMPLE>

<TASK>
Using the existing summary, output ONLY the JSON report following the structure above. No other text.
</TASK>
"""

is_summary_good_prompt = """
<GOAL>
Your task is to evaluate a research summary and decide if it's substantial enough to create a full news article.
</GOAL>

<CONTEXT>
Research Summary:
{research_summary}
</CONTEXT>

<CRITERIA>
- **Substantial Content**: Does the summary contain specific facts, figures, or unique insights?
- **Clarity**: Is the information presented clearly?
- **Newsworthiness**: Is the topic interesting and relevant?
</CRITERIA>

<STRUCTURE>
Respond with ONLY a valid JSON object with a single key "should_create_article".
- Set the value to `true` if the summary is good enough for a news article.
- Set the value to `false` if the summary is too brief, vague, or lacks substance.

Do not include any other text, explanations, or conversational pleasantries. Your entire output must be the JSON object.
</STRUCTURE>

<EXAMPLE>
{{
    "should_create_article": true
}}
</EXAMPLE>
"""


news_article_instructions = """
<GOAL>
You are a news anchor for a TV show, and your goal is to create an engaging and informative news article for your YouTube stream.
</GOAL>

<CONTEXT>
- Current date: {current_date}
- Current time: {current_time}
- Show name: {show_name}
- Agent name: {agent_name}
- Your personality: {agent_personality}
- Previous article titles: {news_memory}
- Final report: {final_report}
- Topics to cover: {topics}
- Recommendations for article creation: {recommendations} (this might be an empty string). If it is not empty follow the advice from the recommendations.
- Current article version: {current_article_version} This might be an empty string. If not this is your previous article version. You need to enhance its quality to meet the recommendations provided. Do not create new one of this string is not empty. Improve the article to meet the recommendations provided.
- if recommendations are not empty you need to focus on improving the article to meet the recommendations provided.
</CONTEXT>

<REQUIREMENTS>
- Generate a news article based on the final report and your personality. Make the article short and concise.
- The article should be creative, innovative, and written in the style of a TV news episode and not too long.
- Greet the users and make the episode engaging and informative.
- Ensure a smooth and natural transition between the different topics from the final report.
- The final report should cover each topic mentioned and be consise and less than 3000 words.
- The article must be less than 3000 words.
- The article should not contain any information about the scene. This should be the script for the agent to speak.
- The text should start with greetings as usual tv or radio show.
</REQUIREMENTS>

<CRITICAL>
The length of the article must be less than 3000 words. This is critical.
</CRITICAL>

<STRUCTURE>
Please provide your response in a JSON format with the following keys:
{{
    "title": "A concise, engaging title for the report",
    "content": "The content of the article"
}}

Ensure that any double quotes within the JSON values are properly escaped (e.g., \\"text with quotes\\").
Output ONLY a valid JSON object. Do not include any other text, explanations, or conversational pleasantries before or after the JSON object.
</STRUCTURE>
"""

validate_news_article_instructions = """
<GOAL>
You are a news anchor for a TV show, and your goal is to validate a news article.
</GOAL>

<CONTEXT>
- Your personality: {agent_personality}
- Agent name: {agent_name}
- News article to validate: {news_article}
- Topics to cover: {topics}
- Final report: {final_report}
- Previous article titles: {news_memory}
</CONTEXT>

<REQUIREMENTS>
- Ensure the news article is based on the final report.
- Verify that the article covers all topics from the final report and the provided topics list.
- The final report should be consise and less than 3000 words.
- Check that the article is written in the style of the agent's personality.
- Make sure the article is different from the previous articles in news_memory
</REQUIREMENTS>

<CRITICAL>
The length of the article must be less than 3000 words. This is critical. If article is longer than 3000 words, return validated as false.
</CRITICAL>

<STRUCTURE>
Please provide your response in a JSON format with the following keys:
{{
    "validated": true,
    "recommendations": "Recommendations of how to improve the article if validated is false, otherwise an empty string"
}}

Ensure that any double quotes within the JSON values are properly escaped (e.g., \\"text with quotes\\").
Output ONLY a valid JSON object. Do not include any other text, explanations, or conversational pleasantries before or after the JSON object.
</STRUCTURE>
"""
