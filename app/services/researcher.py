"""
Company research using Perplexity Sonar via OpenRouter API.
Implements adaptive depth (quick vs deep) based on data availability.
"""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.models import ProspectRow, CompanyResearch, ResearchDepth

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

WELL_KNOWN_COMPANIES = {
    "salesforce", "snowflake", "hubspot", "adobe", "oracle", "sap", "microsoft",
    "google", "amazon", "meta", "apple", "ibm", "cisco", "dell", "intel",
    "zoom", "slack", "shopify", "stripe", "twilio", "datadog", "splunk",
    "servicenow", "workday", "atlassian", "dropbox", "zendesk", "intercom",
    "marketo", "eloqua", "pardot", "mailchimp", "sendgrid", "segment",
}


def _load_system_prompt() -> str:
    """Load the research system prompt from file."""
    try:
        with open(settings.research_system_prompt_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return (
            "You are a B2B company research analyst. Provide detailed, factual "
            "information about companies including their technology stack, "
            "business challenges, industry position, and recent developments. "
            "Be specific and data-driven."
        )


def determine_research_depth(prospect: ProspectRow) -> ResearchDepth:
    """Decide whether to run quick or deep research based on data availability."""
    if prospect.company_name.lower().strip() in WELL_KNOWN_COMPANIES:
        return ResearchDepth.QUICK

    if prospect.industry and prospect.website_url:
        return ResearchDepth.QUICK

    return ResearchDepth.DEEP


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
async def _query_perplexity(query: str, model: str = "perplexity/sonar") -> str:
    """Make a single query to Perplexity via OpenRouter API."""
    system_prompt = _load_system_prompt()

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://lakeb2b.com",
                "X-Title": "LakeB2B Pitch Deck Creator",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def research_company(prospect: ProspectRow) -> CompanyResearch:
    """
    Research a company using Perplexity Sonar via OpenRouter.
    Depth is automatically determined based on available data.
    """
    depth = determine_research_depth(prospect)
    model = "perplexity/sonar" if depth == ResearchDepth.QUICK else "perplexity/sonar"

    company = prospect.company_name
    url_hint = f" (website: {prospect.website_url})" if prospect.website_url else ""
    industry_hint = f" in the {prospect.industry} industry" if prospect.industry else ""

    queries = []

    if depth == ResearchDepth.QUICK:
        queries = [
            (
                f"Give me a comprehensive overview of {company}{url_hint}{industry_hint}. "
                f"Include: what they do, company size, target market, key products/services, "
                f"and their technology stack (CRM, marketing tools, data platforms they use)."
            ),
            (
                f"What are the top business challenges and pain points for {company}{industry_hint}? "
                f"Focus on: data quality issues, sales/marketing efficiency, lead generation, "
                f"technology gaps, and competitive pressures."
            ),
            (
                f"What are the latest news, initiatives, and strategic priorities for {company}? "
                f"Include any recent funding, partnerships, product launches, or market expansion."
            ),
        ]
    else:
        queries = [
            (
                f"Provide a detailed company overview of {company}{url_hint}{industry_hint}. "
                f"Include: founding year, headquarters, employee count, revenue range, "
                f"key leadership, mission, and primary business model."
            ),
            (
                f"What technology stack does {company} use? Include: CRM systems, marketing "
                f"automation platforms, data/analytics tools, sales enablement tools, "
                f"cloud infrastructure, and any custom/proprietary technology."
            ),
            (
                f"What are the key business pain points and challenges facing {company}? "
                f"Focus specifically on: data quality/enrichment needs, SDR productivity, "
                f"buyer intent visibility, lead scoring accuracy, ABM capabilities, "
                f"and demand generation effectiveness."
            ),
            (
                f"Describe the competitive landscape for {company}{industry_hint}. "
                f"Who are their main competitors? What differentiates {company}? "
                f"Where are they vulnerable competitively?"
            ),
            (
                f"Who are the key buyer personas at {company} that would be involved in "
                f"purchasing B2B data, sales intelligence, or marketing technology solutions? "
                f"What are their typical priorities and decision criteria?"
            ),
        ]

    results = []
    for query in queries:
        result = await _query_perplexity(query, model=model)
        results.append(result)

    raw_research = "\n\n---\n\n".join(results)

    return CompanyResearch(
        company_name=company,
        overview=results[0] if len(results) > 0 else "",
        pain_points=_extract_bullet_points(results[1]) if len(results) > 1 else [],
        tech_stack=_extract_bullet_points(results[1] if depth == ResearchDepth.QUICK else (results[1] if len(results) > 1 else "")),
        industry_context=results[0] if len(results) > 0 else "",
        recent_news=results[2] if len(results) > 2 else "",
        opportunities=_extract_bullet_points(results[1]) if len(results) > 1 else [],
        competitive_landscape=results[3] if depth == ResearchDepth.DEEP and len(results) > 3 else "",
        depth_used=depth,
        raw_research=raw_research,
    )


def _extract_bullet_points(text: str) -> list[str]:
    """Extract bullet-point-like items from research text."""
    points = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith(("-", "•", "*", "–")) and len(line) > 5:
            cleaned = line.lstrip("-•*– ").strip()
            if cleaned:
                points.append(cleaned)
    if not points:
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 20]
        points = sentences[:5]
    return points
