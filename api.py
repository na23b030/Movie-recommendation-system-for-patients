POST /recommendations: ONLY movie details and a concise reason.
POST /recommendations/audit: Task 6 technical trace, never intended for patients.
from __future__ import annotations

from fastapi import Body, FastAPI, HTTPException
from recommender.engine import load_default, UNMODELED_SYMPTOMS
from recommender.semantic import SemanticUnavailable

app = FastAPI(
    title="Patient-Appropriate Movie Recommender",
    version="2.0.0",
    description="Synthetic patient demonstration; not a medical certification tool.",
)
engine = load_default()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "catalog_size": len(engine.movies), "rule_count": len(engine.rule_definitions)}


def _evaluate(profile: dict) -> dict:
    if not isinstance(profile, dict):
        raise HTTPException(status_code=422, detail="Expected a patient JSON object")
    payload = dict(profile)
    top_k = payload.pop("top_k", 5)
    diversify = payload.pop("diversify", True)
    # Accept an old request with use_llm:false without contacting any provider.
    old_llm = payload.pop("use_llm", False)
    if old_llm is not False:
        raise HTTPException(status_code=422, detail="LLM support was removed; omit use_llm or set it to false")
    if type(top_k) is not int or not 1 <= top_k <= 5:
        raise HTTPException(status_code=422, detail="top_k must be between 1 and 5")
    try:
        return engine.recommend(payload, top_k=top_k, diversify=diversify)
    except SemanticUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/recommendations")
def recommendations(profile: dict = Body(...)) -> dict:
    """Patient view: no scores, evidence, rules, audit, excluded titles, or diagnosis."""
    result = _evaluate(profile)
    unsupported_symptoms = set(profile.get("current_symptoms", [])) & UNMODELED_SYMPTOMS
    titles = [{
        "title": item["title"],
        "genres": item["genres"],
        "runtime_minutes": item["runtime_minutes"],
        "age_rating": item["age_rating"],
        "reason": item["explanation"] + (
            " Note: some reported symptoms have not been assessed with movie-specific evidence."
            if unsupported_symptoms else ""
        ),
    } for item in result["recommendations"]]
    if titles:
        return {"recommendations": titles}
    # A no-result explanation is essential to avoid falsely implying safety.
    if result["audit"]["eligible_count"] == 0:
        message = "No movies meet the reported viewing requirements using the available evidence."
    elif set(profile.get("known_sensitivities", [])) & {"sound_sensitivity", "visual_motion_sensitivity"}:
        message = "The available movie annotations cannot assess all of the reported sensitivities."
    else:
        message = "No strong match is available. Try another genre or describe the kinds of stories you enjoy."
    return {"recommendations": [], "message": message}


@app.post("/recommendations/audit")
def recommendation_audit(profile: dict = Body(...)) -> dict:
    """Assignment reviewer view: auditable rule trace and excluded candidates."""
    return _evaluate(profile)
