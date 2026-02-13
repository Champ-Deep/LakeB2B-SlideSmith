"""
Service catalog loader.
Reads LakeB2B service definitions from YAML and provides matching logic.
"""
from __future__ import annotations
import yaml
from pathlib import Path

from app.models import ServiceDefinition, CompanyResearch


_catalog_cache: list[ServiceDefinition] | None = None


def load_catalog(yaml_path: str = "./data/services_catalog.yaml") -> list[ServiceDefinition]:
    """Load service definitions from YAML file. Caches after first load."""
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache

    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Service catalog not found at {yaml_path}. "
            "Please create it from the template in data/services_catalog.yaml"
        )

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    services = []
    for svc_data in data.get("services", []):
        services.append(ServiceDefinition(**svc_data))

    _catalog_cache = services
    return services


def reload_catalog(yaml_path: str = "./data/services_catalog.yaml") -> list[ServiceDefinition]:
    """Force reload the catalog (e.g., after editing YAML)."""
    global _catalog_cache
    _catalog_cache = None
    return load_catalog(yaml_path)


def match_services(
    research: CompanyResearch,
    prospect_industry: str,
    catalog: list[ServiceDefinition] | None = None,
    top_n: int = 3,
) -> list[ServiceDefinition]:
    """
    Simple keyword-based matching to find the most relevant LakeB2B services
    for a given prospect. Returns top N services ranked by relevance score.

    This is a lightweight heuristic – Claude will do the real nuanced mapping.
    This pre-filters the catalog to give Claude fewer, more relevant services.
    """
    if catalog is None:
        catalog = load_catalog()

    scored: list[tuple[float, ServiceDefinition]] = []

    # Build a bag of words from research
    research_text = " ".join([
        research.overview,
        " ".join(research.pain_points),
        " ".join(research.tech_stack),
        research.industry_context,
        " ".join(research.opportunities),
    ]).lower()

    for service in catalog:
        score = 0.0

        # Industry match bonus
        for ind in service.ideal_for_industries:
            if ind.lower() in prospect_industry.lower() or prospect_industry.lower() in ind.lower():
                score += 3.0
                break

        # Pain point keyword overlap
        for pain in service.pain_points_addressed:
            pain_words = set(pain.lower().split())
            overlap = sum(1 for w in pain_words if w in research_text)
            score += overlap * 0.5

        # Description keyword overlap with research text
        desc_words = set(service.description.lower().split())
        desc_overlap = sum(1 for w in desc_words if len(w) > 4 and w in research_text)
        score += desc_overlap * 0.2

        scored.append((score, service))

    # Sort by score descending, return top N
    scored.sort(key=lambda x: x[0], reverse=True)
    return [svc for _, svc in scored[:top_n]]
