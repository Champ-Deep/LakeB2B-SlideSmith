"""
History route -- query Postgres for past generated decks.
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, desc, func

router = APIRouter()


@router.get("/history")
async def get_deck_history(limit: int = 50, offset: int = 0):
    """Return a paginated list of all generated decks."""
    from app.database import async_session
    from app.db_models import GeneratedDeck

    if async_session is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    async with async_session() as session:
        count_result = await session.execute(
            select(func.count()).select_from(GeneratedDeck)
        )
        total = count_result.scalar()

        result = await session.execute(
            select(GeneratedDeck)
            .order_by(desc(GeneratedDeck.created_at))
            .offset(offset)
            .limit(limit)
        )
        decks = result.scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "decks": [
            {
                "id": d.id,
                "job_id": d.job_id,
                "company_name": d.company_name,
                "contact_name": d.contact_name,
                "deck_url": d.deck_url,
                "pptx_url": d.pptx_url,
                "gamma_id": d.gamma_id,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in decks
        ],
    }


@router.get("/history/{deck_id}")
async def get_deck_detail(deck_id: int):
    """Return full details of a generated deck including research and content."""
    from app.database import async_session
    from app.db_models import GeneratedDeck

    if async_session is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    async with async_session() as session:
        result = await session.execute(
            select(GeneratedDeck).where(GeneratedDeck.id == deck_id)
        )
        deck = result.scalar_one_or_none()

    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    return {
        "id": deck.id,
        "job_id": deck.job_id,
        "company_name": deck.company_name,
        "contact_name": deck.contact_name,
        "deck_url": deck.deck_url,
        "pptx_url": deck.pptx_url,
        "pdf_url": deck.pdf_url,
        "gamma_id": deck.gamma_id,
        "research_data": deck.research_data,
        "pitch_content": deck.pitch_content,
        "mapped_services": deck.mapped_services,
        "created_at": deck.created_at.isoformat() if deck.created_at else None,
    }
