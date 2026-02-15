"""
Gamma API v1.0 client.
Generates presentations via the Gamma API, polls for completion,
and returns deck URLs.

API docs: https://developers.gamma.app/reference/generate-a-gamma
"""
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.models import PitchContent, GammaResult


def _headers() -> dict:
    """Standard headers for Gamma API v1.0."""
    return {
        "X-API-KEY": settings.gamma_api_key,
        "Content-Type": "application/json",
    }


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=3, max=15))
async def create_presentation(content: PitchContent) -> GammaResult:
    """
    Generate a presentation via Gamma API v1.0.

    Steps:
    1. POST /generations with content
    2. Poll GET /generations/{id} until completed
    3. Return deck URL
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Step 1: Submit generation request
        payload = {
            "inputText": content.input_text,
            "textMode": "preserve",
            "format": "presentation",
            "numCards": len(content.slides) or 15,
            "exportAs": "pptx",
        }

        if settings.gamma_theme_id:
            payload["themeId"] = settings.gamma_theme_id

        response = await client.post(
            f"{settings.gamma_api_base_url}/generations",
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        gen_data = response.json()

        generation_id = gen_data.get("generationId", "")
        if not generation_id:
            raise RuntimeError(f"Gamma API did not return a generationId: {gen_data}")

        # Step 2: Poll for completion
        return await _poll_generation(client, generation_id)


async def _poll_generation(
    client: httpx.AsyncClient,
    generation_id: str,
    max_wait_seconds: int = 300,
    poll_interval: int = 5,
) -> GammaResult:
    """Poll Gamma API until generation is complete or timeout."""
    elapsed = 0

    while elapsed < max_wait_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        response = await client.get(
            f"{settings.gamma_api_base_url}/generations/{generation_id}",
            headers=_headers(),
        )

        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "")

            if status == "completed":
                return _parse_gamma_response(data)
            elif status == "failed":
                error = data.get("error", {})
                msg = error.get("message", "Unknown error") if isinstance(error, dict) else str(error)
                raise RuntimeError(f"Gamma generation failed: {msg}")

    raise TimeoutError(f"Gamma generation timed out after {max_wait_seconds}s for ID {generation_id}")


def _parse_gamma_response(data: dict) -> GammaResult:
    """Parse Gamma API v1.0 response into our GammaResult model."""
    generation_id = data.get("generationId", "")
    gamma_url = data.get("gammaUrl", "")

    # Try to extract export URLs if present in the response
    pptx_url = data.get("pptxUrl", "")
    pdf_url = data.get("pdfUrl", "")

    # Check for exports in various formats the API might return
    exports = data.get("exports", {})
    if isinstance(exports, dict):
        pptx_url = pptx_url or exports.get("pptx", "")
        pdf_url = pdf_url or exports.get("pdf", "")

    return GammaResult(
        gamma_id=generation_id,
        url=gamma_url,
        pptx_url=pptx_url,
        pdf_url=pdf_url,
        status="completed",
    )


async def list_themes() -> list[dict]:
    """Fetch available themes from Gamma API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{settings.gamma_api_base_url}/themes",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()
