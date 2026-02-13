"""
Gamma API v1.0 client.
Generates presentations via the Gamma API, polls for completion,
and returns deck URLs.
"""
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.models import PitchContent, GammaResult


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=3, max=15))
async def create_presentation(content: PitchContent) -> GammaResult:
    """
    Generate a presentation via Gamma API v1.0.
    
    Steps:
    1. POST to generate endpoint with content
    2. Poll for completion (generation is async on Gamma's side)
    3. Return deck URL and export URLs
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Step 1: Submit generation request
        payload = {
            "content": content.input_text,
            "textMode": "preserve",  # Keep our carefully crafted content as-is
        }

        # Add theme if configured
        if settings.gamma_theme_id:
            payload["themeId"] = settings.gamma_theme_id

        # Request PPTX export alongside the deck
        payload["exportAs"] = ["pptx"]

        headers = {
            "Authorization": f"Bearer {settings.gamma_api_key}",
            "Content-Type": "application/json",
        }

        response = await client.post(
            f"{settings.gamma_api_base_url}/generate",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        gen_data = response.json()

        # Step 2: Handle async generation
        # Gamma may return immediately with the result, or we may need to poll
        gamma_id = gen_data.get("id", "")
        status = gen_data.get("status", "completed")

        if status in ("completed", "done"):
            return _parse_gamma_response(gen_data)

        # Step 3: Poll for completion if still processing
        if gamma_id:
            return await _poll_generation(client, headers, gamma_id)

        # Direct completion
        return _parse_gamma_response(gen_data)


async def _poll_generation(
    client: httpx.AsyncClient,
    headers: dict,
    gamma_id: str,
    max_wait_seconds: int = 300,
    poll_interval: int = 5,
) -> GammaResult:
    """Poll Gamma API until generation is complete or timeout."""
    elapsed = 0

    while elapsed < max_wait_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        response = await client.get(
            f"{settings.gamma_api_base_url}/gammas/{gamma_id}",
            headers=headers,
        )

        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "")

            if status in ("completed", "done", "published"):
                return _parse_gamma_response(data)
            elif status in ("failed", "error"):
                raise RuntimeError(
                    f"Gamma generation failed for ID {gamma_id}: "
                    f"{data.get('error', 'Unknown error')}"
                )

    raise TimeoutError(f"Gamma generation timed out after {max_wait_seconds}s for ID {gamma_id}")


def _parse_gamma_response(data: dict) -> GammaResult:
    """Parse Gamma API response into our GammaResult model."""
    gamma_id = data.get("id", "")
    
    # Gamma URL format
    url = data.get("url", "")
    if not url and gamma_id:
        url = f"https://gamma.app/docs/{gamma_id}"

    # Export URLs
    exports = data.get("exports", {})
    pptx_url = ""
    pdf_url = ""

    if isinstance(exports, dict):
        pptx_url = exports.get("pptx", "")
        pdf_url = exports.get("pdf", "")
    elif isinstance(exports, list):
        for export in exports:
            if isinstance(export, dict):
                if export.get("format") == "pptx":
                    pptx_url = export.get("url", "")
                elif export.get("format") == "pdf":
                    pdf_url = export.get("url", "")

    return GammaResult(
        gamma_id=gamma_id,
        url=url,
        pptx_url=pptx_url,
        pdf_url=pdf_url,
        status="completed",
    )


async def list_themes() -> list[dict]:
    """Fetch available themes from Gamma API (useful for finding themeId)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{settings.gamma_api_base_url}/themes",
            headers={
                "Authorization": f"Bearer {settings.gamma_api_key}",
            },
        )
        response.raise_for_status()
        return response.json()
