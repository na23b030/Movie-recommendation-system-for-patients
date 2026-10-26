"""Patient-Appropriate Movie Recommender API.

POST /recommendations: top-five results with the scoring and safety trace.
POST /recommendations/audit: full technical trace for deeper inspection.
GET /health: catalog and rule counts.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException

from recommender.engine import load_default
from recommender.semantic import SemanticUnavailable


app = FastAPI(
    title="Patient-Appropriate Movie Recommender",
    version="2.1.0",
    description="Synthetic-patient demonstration, not a medical certification tool.",
)
engine = load_default()


def _rule_source_urls() -> dict[str, str]:
    """Reference URLs from the same human-readable source register as the rules."""
    source_file = Path(__file__).resolve().parent / "rules" / "Rule_sources.md"
    entries = re.findall(
        r"\*\*(S\d+)\s+—\s+\[[^\]]+\]\((https?://[^)]+)\)",
        source_file.read_text(encoding="utf-8"),
    )
    return dict(entries)


RULE_SOURCE_URLS = _rule_source_urls()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "catalog_size": len(engine.movies),
        "rule_count": len(engine.rule_definitions),
    }


def _evaluate(profile: dict) -> dict:
    """Validate an inline patient profile and use the unchanged recommender."""
    if not isinstance(profile, dict):
        raise HTTPException(status_code=422, detail="Expected a patient JSON object")

    payload = dict(profile)
    top_k = payload.pop("top_k", 5)
    diversify = payload.pop("diversify", True)

    # Compatibility with older requests; there is no LLM dependency.
    use_llm = payload.pop("use_llm", False)
    if use_llm is not False:
        raise HTTPException(
            status_code=422,
            detail="LLM support was removed; omit use_llm or set it to false",
        )
    if type(top_k) is not int or not 1 <= top_k <= 5:
        raise HTTPException(status_code=422, detail="top_k must be between 1 and 5")

    try:
        return engine.recommend(payload, top_k=top_k, diversify=diversify)
    except SemanticUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _rule_outcomes(evaluations: list[dict]) -> list[dict]:
    """Show every evaluated rule, including passes, without repeating long citations."""
    output = []
    for rule in evaluations:
        item = {"rule_id": rule["rule_id"], "outcome": rule["outcome"]}
        if rule["outcome"] == "soft_penalty":
            item["applied_penalty"] = rule["applied_penalty"]
        output.append(item)
    return output


def _recommendation_item(item: dict) -> dict:
    """Make score components and all 16 safety-rule outcomes visible."""
    return {
        "title": item["title"],
        "genres": item["genres"],
        "runtime_minutes": item["runtime_minutes"],
        "age_rating": item["age_rating"],
        "reason": item["explanation"],
        "taste_match": {
            "score": item["taste_score"],
            "features": item["taste_breakdown"],
            "weights": item["weights"],
            "weighted_contributions": item["taste_contributions"],
            "matched_genres": item["matched_genres"],
        },
        "soft_penalties": [
            {"rule_id": rule["rule_id"], "applied_penalty": rule["applied_penalty"]}
            for rule in item["soft_penalties"]
        ],
        "total_soft_penalty": item["total_penalty"],
        "final_score": item["final_score"],
        "rule_evaluations": _rule_outcomes(item["rule_evaluations"]),
    }


def _excluded_example(item: dict) -> dict:
    """Give the reviewer a real excluded candidate and its hard-veto evidence."""
    hard_rules = [
        {
            "rule_id": rule["rule_id"],
            "patient_condition": rule["patient_condition"],
            "movie_condition": rule["movie_condition"],
            "justification_type": rule["justification_type"],
            "source": rule["source"],
            "movie_evidence_confidence": rule["movie_evidence_confidence"],
        }
        for rule in item["rule_evaluations"]
        if rule["outcome"] == "hard_exclude"
    ]
    return {
        "title": item["title"],
        "hard_exclusion_rule_ids": item["hard_exclusion_rule_ids"],
        "hard_exclusion_reasons": hard_rules,
        "rule_evaluations": _rule_outcomes(item["rule_evaluations"]),
    }


@app.post("/recommendations")
def recommendations(profile: dict = Body(...)) -> dict:
    """Task 6: recommend up to five titles with transparent scoring and rule results."""
    result = _evaluate(profile)
    excluded = result["excluded_candidates"]

    response = {
        "recommendations": [
            _recommendation_item(movie) for movie in result["recommendations"]
        ],
        # One actual example is enough for Task 6; the full list remains in /audit.
        "excluded_candidates": [
            _excluded_example(excluded[0])
        ] if excluded else [],
        "summary": {
            "requested_count": result["requested_count"],
            "returned_count": result["returned_count"],
            "hard_excluded_count": result["audit"]["excluded_count"],
            "rule_count": result["audit"]["rule_count"],
            "diversity_enabled": result["audit"]["diversity_enabled"],
            "hard_constraints_rechecked": result["audit"]["all_recommendations_rechecked"],
        },
        # Store rule provenance once rather than duplicating sources for every film.
        "rule_sources": {
            rule["rule_id"]: {
                "justification_type": rule["justification_type"],
                "source": rule["source"],
                "source_urls": [
                    RULE_SOURCE_URLS[source_id]
                    for source_id in re.findall(r"S\d+", rule["source"])
                    if source_id in RULE_SOURCE_URLS
                ],
            }
            for rule in engine.rule_definitions
        },
        "warnings": result["warnings"],
        "disclaimer": result["disclaimer"],
    }
    if not excluded:
        response["exclusion_note"] = (
            "No movies were hard-excluded for this profile; "
            "an excluded example cannot be shown without inventing one. "
            "Try a profile with age restrictions or content avoidances."
        )
    return response


@app.post("/recommendations/audit")
def recommendation_audit(profile: dict = Body(...)) -> dict:
    """Full machine-readable recommendation, rule, and exclusion details."""
    return _evaluate(profile)
