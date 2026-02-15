"""
Company research using Perplexity Sonar via OpenRouter API.
Implements adaptive depth (quick vs deep) based on data availability.
Caches research in Postgres to avoid repeat API calls (30-day TTL).
"""
import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.models import ProspectRow, CompanyResearch, ResearchDepth

RESEARCH_CACHE_TTL_DAYS = 30

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
    Checks Postgres cache first (30-day TTL) to avoid repeat API costs.
    """
    # Check cache first
    cached = await _check_research_cache(prospect.company_name)
    if cached:
        return cached

    depth = determine_research_depth(prospect)
    model = settings.research_model

    company = prospect.company_name
    url_hint = f" (website: {prospect.website_url})" if prospect.website_url else ""
    industry_hint = f" in the {prospect.industry} industry" if prospect.industry else ""

    queries = []

    if depth == ResearchDepth.QUICK:
        queries = [
            (
                f"Give me a comprehensive overview of {company}{url_hint}{industry_hint}. "
                f"Include: what they do, company size, target market, key products/services, "
                f"technology stack (CRM, marketing tools, data platforms), and any recent "
                f"news, funding, partnerships, or product launches."
            ),
            (
                f"What are the top business challenges and pain points for {company}{industry_hint}? "
                f"Focus on: data quality issues, sales/marketing efficiency, lead generation, "
                f"technology gaps, competitive pressures, and opportunities for B2B data services."
            ),
        ]
    else:
        queries = [
            (
                f"Provide a detailed company overview of {company}{url_hint}{industry_hint}. "
                f"Include: founding year, headquarters, employee count, revenue range, "
                f"key leadership, mission, primary business model, and technology stack "
                f"(CRM, marketing automation, data/analytics, cloud infrastructure)."
            ),
            (
                f"What are the key business pain points and challenges facing {company}? "
                f"Focus specifically on: data quality/enrichment needs, SDR productivity, "
                f"buyer intent visibility, lead scoring accuracy, ABM capabilities, "
                f"demand generation effectiveness, and competitive landscape."
            ),
            (
                f"What are the latest news, strategic priorities, and recent developments "
                f"for {company}? Also describe the key buyer personas who would purchase "
                f"B2B data, sales intelligence, or marketing technology solutions."
            ),
        ]

    results = []
    for query in queries:
        result = await _query_perplexity(query, model=model)
        results.append(result)

    raw_research = "\n\n---\n\n".join(results)

    research = CompanyResearch(
        company_name=company,
        overview=results[0] if len(results) > 0 else "",
        pain_points=_extract_bullet_points(results[1]) if len(results) > 1 else [],
        tech_stack=_extract_bullet_points(results[0]) if len(results) > 0 else [],
        industry_context=results[0] if len(results) > 0 else "",
        recent_news=results[2] if len(results) > 2 else (results[0] if results else ""),
        opportunities=_extract_bullet_points(results[1]) if len(results) > 1 else [],
        competitive_landscape=results[1] if depth == ResearchDepth.DEEP and len(results) > 1 else "",
        depth_used=depth,
        raw_research=raw_research,
    )

    # Save to cache for future lookups
    await _save_research_cache(company, research)

    return research


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


async def _check_research_cache(company_name: str) -> CompanyResearch | None:
    """Check Postgres cache for existing research. Returns None if not found or expired."""
    from app.database import async_session
    from app.db_models import ResearchCache
    from sqlalchemy import select

    if async_session is None:
        return None

    normalized = company_name.strip().lower()
    try:
        async with async_session() as session:
            result = await session.execute(
                select(ResearchCache).where(
                    ResearchCache.company_name_normalized == normalized
                )
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                return None

            # Check TTL
            age = datetime.datetime.now(datetime.timezone.utc) - entry.created_at.replace(
                tzinfo=datetime.timezone.utc
            )
            if age.days > RESEARCH_CACHE_TTL_DAYS:
                return None

            return CompanyResearch(**entry.research_data)
    except Exception:
        return None


async def _save_research_cache(company_name: str, research: CompanyResearch):
    """Save research results to Postgres cache."""
    from app.database import async_session
    from app.db_models import ResearchCache

    if async_session is None:
        return

    normalized = company_name.strip().lower()
    try:
        async with async_session() as session:
            session.add(ResearchCache(
                company_name_normalized=normalized,
                research_data=research.model_dump(),
            ))
            await session.commit()
    except Exception:
        pass  # Duplicate key or DB error — skip silently
