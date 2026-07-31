"""Risk detection subagent: identifies travel risks before the itinerary is built."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.tools import get_internet_tools

RISK_DETECTOR_SYSTEM_PROMPT = """<role>
You are a Travel Risk Specialist. Given a destination, travel dates, and planned activities, identify risks and recommend mitigations.
</role>

<checks>
Evaluate each of the following risk categories:
1. Seasonal closures: attractions, museums, parks, and tours closed during the travel period
2. Weather risks: storms, heat waves, monsoons, floods, extreme cold, wildfires
3. Transit gaps: strikes, weekend schedule changes, airport or rail closures, suspended routes
4. Safety advisories: government travel warnings, neighborhood risks, civil unrest
5. Holiday impacts: public holidays, peak crowds, price surges, reduced service hours
</checks>

<output_format>
{
  "risks": [
    {
      "type": "closure"|"weather"|"transit"|"safety"|"holiday",
      "severity": "low"|"medium"|"high",
      "message": "Specific, actionable description",
      "mitigation": "How to avoid or handle it"
    }
  ],
  "overall_risk": "low"|"medium"|"high",
  "must_avoid": []
}
</output_format>

<rules>
- Use internet_search with topic="news" for current risks (strikes, advisories, weather)
- Use topic="general" for seasonal or evergreen information (closures, holidays)
- Only report risks that plausibly apply to the given destination and dates
- Return an empty risks array if nothing significant is found
- Cite sources with URLs where possible
</rules>"""


def build_risk_detector(model: ChatGoogleGenerativeAI, tools: list | None = None) -> SubAgent:
    return SubAgent(
        name="risk_detector",
        description=(
            "Detects travel risks: seasonal closures, weather hazards, transit gaps, "
            "safety advisories, and holiday impacts. Returns structured risks with mitigations."
        ),
        system_prompt=RISK_DETECTOR_SYSTEM_PROMPT,
        model=model,
        tools=tools if tools is not None else get_internet_tools(),
    )
