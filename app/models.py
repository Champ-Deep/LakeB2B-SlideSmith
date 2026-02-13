"""
Pydantic models for data flowing through the pipeline.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Single Client Input ─────────────────────────────────────────────────────────

class SingleProspect(BaseModel):
    """Single client form input."""
    client_name: str = Field(description="Client's full name")
    company: str = Field(description="Company name")
    role: str = Field(description="Client's role/title")
    linkedin_url: str = Field(default="", description="LinkedIn profile URL (optional)")
    email: str = Field(default="", description="Email address (optional)")
    phone: str = Field(default="", description="Phone number (optional)")
    notes: str = Field(default="", description="Additional notes (optional)")


class SingleJobStatus(BaseModel):
    """Status for single client processing."""
    job_id: str
    company_name: str
    status: RowStatus = RowStatus.QUEUED
    deck_url: str = ""
    pptx_url: str = ""
    error: str = ""


# ── Excel Row Input ──────────────────────────────────────────────────────────

class ProspectRow(BaseModel):
    """One row from the uploaded Excel file."""
    row_index: int = Field(description="Original row number in the Excel (1-indexed)")
    company_name: str
    industry: str = ""
    website_url: str = ""
    contact_name: str = ""
    contact_title: str = ""
    extra_context: str = Field(default="", description="Any other notes/columns concatenated")


# ── Research Output ──────────────────────────────────────────────────────────

class ResearchDepth(str, Enum):
    QUICK = "quick"
    DEEP = "deep"


class CompanyResearch(BaseModel):
    """Structured research output from Perplexity."""
    company_name: str
    overview: str = ""
    pain_points: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    industry_context: str = ""
    recent_news: str = ""
    opportunities: list[str] = Field(default_factory=list)
    competitive_landscape: str = ""
    depth_used: ResearchDepth = ResearchDepth.QUICK
    raw_research: str = Field(default="", description="Full concatenated research text")


# ── Service Catalog ──────────────────────────────────────────────────────────

class ServiceDefinition(BaseModel):
    """One LakeB2B service from the catalog YAML."""
    id: str
    name: str
    tagline: str = ""
    description: str = ""
    pain_points_addressed: list[str] = Field(default_factory=list)
    ideal_for_industries: list[str] = Field(default_factory=list)
    roi_metrics: list[str] = Field(default_factory=list)
    key_differentiators: list[str] = Field(default_factory=list)


# ── Content Generation Output ────────────────────────────────────────────────

class SlideContent(BaseModel):
    """Content for a single slide."""
    slide_number: int
    title: str
    body: str
    speaker_notes: str = ""


class PitchContent(BaseModel):
    """Full pitch deck content ready for Gamma API."""
    company_name: str
    slides: list[SlideContent] = Field(default_factory=list)
    mapped_services: list[ServiceDefinition] = Field(default_factory=list)
    input_text: str = Field(default="", description="Formatted text for Gamma inputText param")


# ── Gamma API Result ─────────────────────────────────────────────────────────

class GammaResult(BaseModel):
    """Result from Gamma API generation."""
    gamma_id: str = ""
    url: str = ""
    pptx_url: str = ""
    pdf_url: str = ""
    status: str = "pending"


# ── Job / Row Status ─────────────────────────────────────────────────────────

class RowStatus(str, Enum):
    QUEUED = "queued"
    RESEARCHING = "researching"
    GENERATING_CONTENT = "generating_content"
    CREATING_DECK = "creating_deck"
    COMPLETE = "complete"
    FAILED = "failed"


class RowResult(BaseModel):
    """Final result for one Excel row."""
    row_index: int
    company_name: str
    status: RowStatus = RowStatus.QUEUED
    deck_url: str = ""
    pptx_url: str = ""
    error: str = ""


class JobStatus(BaseModel):
    """Overall job status for the full Excel upload."""
    job_id: str
    total_rows: int = 0
    completed: int = 0
    failed: int = 0
    status: str = "pending"  # pending / processing / complete / failed
    rows: list[RowResult] = Field(default_factory=list)
    output_file: str = ""
