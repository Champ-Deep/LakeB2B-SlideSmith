"""
Content generation using Claude 3.5 Sonnet via OpenRouter.
Two-phase: service mapping + pitch slide content generation.
"""
import httpx

from app.config import settings
from app.models import (
    ProspectRow,
    CompanyResearch,
    ServiceDefinition,
    PitchContent,
    SlideContent,
)
from app.services.service_catalog import load_catalog, match_services

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


async def _call_openrouter(prompt: str, model: str = "anthropic/claude-3.5-sonnet", max_tokens: int = 8192) -> str:
    """Make a call to OpenRouter API."""
    async with httpx.AsyncClient(timeout=120.0) as client:
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
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _format_services_for_prompt(services: list[ServiceDefinition]) -> str:
    """Format service definitions into a readable string for Claude."""
    parts = []
    for svc in services:
        parts.append(
            f"### {svc.name}\n"
            f"**Tagline:** {svc.tagline}\n"
            f"**Description:** {svc.description}\n"
            f"**Pain Points Addressed:** {', '.join(svc.pain_points_addressed)}\n"
            f"**ROI Metrics:** {', '.join(svc.roi_metrics)}\n"
            f"**Key Differentiators:** {', '.join(svc.key_differentiators)}\n"
        )
    return "\n".join(parts)


async def map_services(
    prospect: ProspectRow,
    research: CompanyResearch,
) -> list[ServiceDefinition]:
    """
    Phase 1: Select the top 3 most relevant LakeB2B services for this prospect.
    Uses lightweight keyword matching first, then Claude for nuanced selection.
    """
    catalog = load_catalog(settings.services_catalog_path)

    candidates = match_services(research, prospect.industry, catalog, top_n=5)

    if len(candidates) <= 3:
        return candidates

    candidates_text = _format_services_for_prompt(candidates)

    prompt = (
        f"You are a B2B sales strategist for LakeB2B.\n\n"
        f"**Prospect:** {prospect.company_name} ({prospect.industry})\n"
        f"**Contact:** {prospect.contact_name}, {prospect.contact_title}\n\n"
        f"**Research Summary:**\n{research.overview[:2000]}\n\n"
        f"**Pain Points Found:**\n"
        + "\n".join(f"- {p}" for p in research.pain_points[:8])
        + f"\n\n**Available LakeB2B Services:**\n{candidates_text}\n\n"
        f"Select exactly 3 services that would be MOST relevant and impactful "
        f"for this prospect. Return ONLY the service IDs, one per line, "
        f"in order of relevance (most relevant first).\n"
        f"Format: Just the IDs, nothing else."
    )

    response_text = await _call_openrouter(
        prompt,
        model=settings.service_mapping_model,
        max_tokens=settings.service_mapping_max_tokens,
    )

    selected_ids = [
        line.strip().lower()
        for line in response_text.strip().split("\n")
        if line.strip()
    ]

    id_to_svc = {svc.id.lower(): svc for svc in candidates}
    selected = [id_to_svc[sid] for sid in selected_ids if sid in id_to_svc]

    return selected[:3] if selected else candidates[:3]


async def generate_pitch(
    prospect: ProspectRow,
    research: CompanyResearch,
    selected_services: list[ServiceDefinition] | None = None,
) -> PitchContent:
    """
    Phase 2: Generate complete pitch deck content for Gamma API.
    Returns structured content with slide-by-slide text.
    """
    if selected_services is None:
        selected_services = await map_services(prospect, research)

    services_text = _format_services_for_prompt(selected_services)

    prompt = f"""You are an expert B2B pitch deck writer for LakeB2B, a leading B2B data services company.

Create a persuasive, data-driven pitch deck for the following prospect.

## PROSPECT INFO
- **Company:** {prospect.company_name}
- **Industry:** {prospect.industry}
- **Website:** {prospect.website_url}
- **Contact:** {prospect.contact_name}, {prospect.contact_title}
{f"- **Extra Context:** {prospect.extra_context}" if prospect.extra_context else ""}

## RESEARCH ON PROSPECT
{research.raw_research[:6000]}

## LAKEB2B SERVICES TO PITCH (Top 3)
{services_text}

## INSTRUCTIONS
Generate a 15-slide pitch deck with the following structure. For each slide, provide:
- A compelling title
- Body content (2-4 paragraphs or bullet points)
- Speaker notes (what the presenter should say/emphasize)

### SLIDE STRUCTURE:
1. **Title Slide** - "{prospect.company_name} × LakeB2B: [Compelling value prop]"
2. **About {prospect.company_name}** - Show understanding of their business (from research)
3. **Pain Point Discovery** - Present 3 key challenges as visual boxes (from research)
4-6. **Deep Dive: Pain Point A** - Problem → Impact → LakeB2B Solution (Service 1)
7-9. **Deep Dive: Pain Point B** - Problem → Impact → LakeB2B Solution (Service 2)
10-12. **Deep Dive: Pain Point C** - Problem → Impact → LakeB2B Solution (Service 3)
13. **ROI Summary** - Quantified impact across all 3 solutions
14. **Why LakeB2B** - Credibility, scale, differentiators
15. **Next Steps & CTA** - Clear action items with timeline

### FORMATTING RULES:
- Use specific data points from research (don't be generic)
- Include concrete ROI metrics from the service catalog
- Pain points must be SPECIFIC to {prospect.company_name}, not generic industry problems
- Speaker notes should guide the presenter on emphasis and talking points
- Keep slide body concise - presentations are visual, not walls of text
- Use markdown formatting (headers, bullet points, bold) for clarity

### OUTPUT FORMAT:
For each slide, output exactly:
---SLIDE [number]---
TITLE: [slide title]
BODY:
[slide body content in markdown]
NOTES:
[speaker notes]
---END SLIDE---

Generate all 15 slides now."""

    raw_output = await _call_openrouter(
        prompt,
        model=settings.pitch_generation_model,
        max_tokens=settings.pitch_max_tokens,
    )

    slides = _parse_slides(raw_output)

    input_text = _build_gamma_input_text(slides, prospect)

    return PitchContent(
        company_name=prospect.company_name,
        slides=slides,
        mapped_services=selected_services,
        input_text=input_text,
    )


def _parse_slides(raw_output: str) -> list[SlideContent]:
    """Parse Claude's slide output into structured SlideContent objects."""
    slides = []
    current_slide_num = 0
    current_title = ""
    current_body_lines = []
    current_notes_lines = []
    section = None

    for line in raw_output.split("\n"):
        stripped = line.strip()

        if stripped.startswith("---SLIDE"):
            if current_slide_num > 0:
                slides.append(SlideContent(
                    slide_number=current_slide_num,
                    title=current_title,
                    body="\n".join(current_body_lines).strip(),
                    speaker_notes="\n".join(current_notes_lines).strip(),
                ))
            try:
                current_slide_num = int(stripped.replace("---SLIDE", "").replace("---", "").strip())
            except ValueError:
                current_slide_num += 1
            current_title = ""
            current_body_lines = []
            current_notes_lines = []
            section = None

        elif stripped.startswith("TITLE:"):
            current_title = stripped.replace("TITLE:", "").strip()
            section = None

        elif stripped == "BODY:":
            section = "body"

        elif stripped == "NOTES:":
            section = "notes"

        elif stripped.startswith("---END SLIDE---"):
            if current_slide_num > 0:
                slides.append(SlideContent(
                    slide_number=current_slide_num,
                    title=current_title,
                    body="\n".join(current_body_lines).strip(),
                    speaker_notes="\n".join(current_notes_lines).strip(),
                ))
                current_slide_num = 0
                current_title = ""
                current_body_lines = []
                current_notes_lines = []
                section = None

        else:
            if section == "body":
                current_body_lines.append(line)
            elif section == "notes":
                current_notes_lines.append(line)

    if current_slide_num > 0:
        slides.append(SlideContent(
            slide_number=current_slide_num,
            title=current_title,
            body="\n".join(current_body_lines).strip(),
            speaker_notes="\n".join(current_notes_lines).strip(),
        ))

    return slides


def _build_gamma_input_text(slides: list[SlideContent], prospect: ProspectRow) -> str:
    """
    Build the inputText parameter for Gamma API.
    Gamma expects markdown-like content where sections become slides.
    """
    parts = []
    for slide in slides:
        part = f"# {slide.title}\n\n{slide.body}"
        if slide.speaker_notes:
            part += f"\n\n> **Speaker Notes:** {slide.speaker_notes}"
        parts.append(part)

    return "\n\n---\n\n".join(parts)
