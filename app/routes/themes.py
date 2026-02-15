"""
Themes route -- list available Gamma themes.
"""
from fastapi import APIRouter, HTTPException

from app.services.gamma_client import list_themes

router = APIRouter()


@router.get("/themes")
async def get_themes():
    """List available Gamma themes so the user can find their theme ID."""
    try:
        themes = await list_themes()
        return {"themes": themes, "count": len(themes)}
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch themes from Gamma: {str(e)}",
        )
