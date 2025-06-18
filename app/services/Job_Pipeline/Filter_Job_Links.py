import asyncio
import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from services.tools import create_tools
from core.config import GEMINI_API_KEY, RESUME_PATH
import re
import os


gemini_model_1 = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17", 
    google_api_key=GEMINI_API_KEY,
    temperature=0.1
) if GEMINI_API_KEY else None

async def filter_job_links_with_llm(elements_info):
    if not gemini_model_1:
        print("No Gemini model available for filtering links.")
        return []

    links = elements_info.get("links", [])

    model = gemini_model_1

    system_msg = SystemMessage(content="""
        You are a smart filtering assistant.

        TASK: Given a list of hyperlinks from a LinkedIn job search results page, return **only** those URLs that point to individual job listings.

        INCLUDE:
        - Links to job detail pages (usually contain '/jobs/view/' in the path).

        EXCLUDE:
        - Navigation links
        - Company profile links
        - Category or location filters
        - Sign-in, help, or menu pages

        FORMAT: Return the list of job URLs as a JSON array of strings.
        IMPORTANT: Do NOT wrap it in markdown or code blocks like ```json.
    """)

    human_msg = HumanMessage(content=f"""
        Here are the raw page links:

        {json.dumps(links, indent=2)}

        Return ONLY job links as a JSON array of hrefs (like ["/jobs/view/...", ...]).
        Do NOT wrap the output in triple backticks.
    """)

    try:
        response = await model.ainvoke([system_msg, human_msg])
        raw_output = response.content.strip()

        # Remove markdown code block if present (Gemini often adds these)
        if raw_output.startswith("```"):
            raw_output = re.sub(r"^```(?:json)?\s*", "", raw_output)
            raw_output = re.sub(r"\s*```$", "", raw_output)

        filtered = json.loads(raw_output)
        return filtered if isinstance(filtered, list) else []

    except Exception as e:
        print(f"❌ Failed to parse filtered links: {e}")
        print(f"🔎 Raw output was: {repr(response.content)}")
        return []

def filter_job_links_locally(raw_links: list[str]) -> list[str]:
    seen = set()
    job_links = []

    for link in raw_links:
        if not isinstance(link, str):
            continue

        if link.startswith("/jobs/view/"):
            full_url = f"https://www.linkedin.com{link}"
        elif link.startswith("https://www.linkedin.com/jobs/view/"):
            full_url = link
        else:
            continue  

        if full_url not in seen:
            seen.add(full_url)
            job_links.append(full_url)

    return job_links
