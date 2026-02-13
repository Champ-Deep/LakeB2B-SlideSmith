"""
Status route – check job progress and download results.
"""
import os

import redis
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter()
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get the current status of a processing job."""
    job_key = f"job:{job_id}"
    job_data = redis_client.hgetall(job_key)

    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    total_rows = int(job_data.get("total_rows", 0))
    completed = int(job_data.get("completed", 0))
    failed = int(job_data.get("failed", 0))

    # Get per-row statuses
    rows = []
    for row_idx in range(2, total_rows + 2):  # Excel rows are 2-indexed (1 is header)
        row_key = f"job:{job_id}:row:{row_idx}"
        row_data = redis_client.hgetall(row_key)
        if row_data:
            rows.append({
                "row_index": row_idx,
                "company_name": row_data.get("company_name", ""),
                "status": row_data.get("status", "queued"),
                "deck_url": row_data.get("deck_url", ""),
                "pptx_url": row_data.get("pptx_url", ""),
                "error": row_data.get("error", ""),
            })

    # Calculate overall progress
    progress_pct = round((completed + failed) / total_rows * 100) if total_rows > 0 else 0

    return {
        "job_id": job_id,
        "status": job_data.get("status", "unknown"),
        "total_rows": total_rows,
        "completed": completed,
        "failed": failed,
        "progress_percent": progress_pct,
        "output_file": job_data.get("output_file", ""),
        "rows": rows,
    }


@router.get("/download/{job_id}")
async def download_output(job_id: str):
    """Download the output Excel file with deck URLs."""
    job_key = f"job:{job_id}"
    job_data = redis_client.hgetall(job_key)

    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    output_file = job_data.get("output_file", "")
    if not output_file or not os.path.exists(output_file):
        raise HTTPException(
            status_code=400,
            detail="Output file not ready yet. Job may still be processing.",
        )

    filename = os.path.basename(output_file)
    return FileResponse(
        output_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )
