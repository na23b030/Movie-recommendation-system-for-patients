from __future__ import annotations

import ast
import json
import math
import re
from statistics import median
from threading import Lock

import numpy as np
from recommender.semantic import SemanticEncoder, SemanticUnavailable
from pathlib import Path
from typing import Any

GENRE_ALIASES = {"sci-fi": "science fiction", "science-fiction": "science fiction"}
CONFIDENCE_FACTOR = {"high": 1.0, "medium": 0.85, "low": 0.5, "unknown": 0.0, "recorded_metadata": 1.0}
# Explicit heuristics, not clinically validated or trained on patient feedback.
WEIGHTS_WITH_TEXT = {"semantic_similarity": 0.72, "genre_coverage": 0.22, "genre_focus": 0.06}
WEIGHTS_NO_TEXT = {"semantic_similarity": 0.0, "genre_coverage": 0.80, "genre_focus": 0.20}
WEIGHTS_MIXED_UNKNOWN = {"semantic_similarity": 0.60, "genre_coverage": 0.32, "genre_focus": 0.08}
# Calibrated semantic-label ground truth is unavailable. These conservative,
# testable engineering thresholds prevent forcing weak matches into a top-5.
MIN_SEMANTIC_AFFINITY = 0.27
MIN_SEMANTIC_ADVANTAGE = 0.05
RATING_VALUES = {
    "MPA": {"G", "PG", "PG-13", "R", "NC-17"},
    "BBFC": {"U", "PG", "12", "12A", "15", "18", "R18"},
    "CBFC": {"U", "UA", "A"},
}
PATIENT_ARRAYS = ("preferred_genres", "known_sensitivities", "current_symptoms", "content_avoidances", "accessibility_requirements")
# Strictly distinguish accepted-but-unmodeled symptoms from unknown/misspelled ones.
# Unmodeled known symptoms generate warnings; they are never silently treated as addressed.
KNOWN_SENSITIVITIES = {"photosensitive_seizure_trigger", "light_sensitivity", "fear_distress_sensitivity", "sound_sensitivity", "visual_motion_sensitivity"}
KNOWN_SYMPTOMS = {"severe_fatigue", "mild_fatigue", "concentration_difficulty", "nausea", "pain"}
KNOWN_ACCESSIBILITY = {"subtitles", "audio_description"}
UNMODELED_SYMPTOMS = {"mild_fatigue", "pain"}
UNMODELED_SENSITIVITIES = {"sound_sensitivity", "visual_motion_sensitivity"}


def read_records(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig") as f:
        content = json.load(f)
    if not isinstance(content, list):
        raise ValueError(f"{path} must contain a JSON array")
    return content


def norm_genres(values: list[str]) -> set[str]:
    if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
        raise ValueError("Genre values must be a list of strings")
    return {GENRE_ALIASES.get(v.strip().casefold(), v.strip().casefold()) for v in values if v.strip()}


def validate_patient(patient: dict) -> dict:
    if not isinstance(patient, dict):
        raise ValueError("The request body must be a patient-profile JSON object")
    if type(patient.get("age")) is not int or not 0 <= patient["age"] <= 120:
        raise ValueError("age must be an integer between 0 and 120")
    for key in PATIENT_ARRAYS:
        value = patient.get(key, [])
        if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
            raise ValueError(f"{key} must be an array of non-empty strings")
    for key, allowed in (("known_sensitivities", KNOWN_SENSITIVITIES), ("current_symptoms", KNOWN_SYMPTOMS), ("accessibility_requirements", KNOWN_ACCESSIBILITY)):
        unknown = set(patient.get(key, [])) - allowed
        if unknown:
            raise ValueError(f"Unsupported {key} values: {sorted(unknown)}; no matching safety rules are implemented")
    if not isinstance(patient.get("diagnosis_context", ""), str) or not isinstance(patient.get("treatment_phase", ""), str):
        raise ValueError("diagnosis_context and treatment_phase must be strings when supplied")
    # Synthetic profiles use no free-text. The API optionally accepts free-text interests;
    # do not infer a made-up query from a patient's medical history or genre labels.
    if not isinstance(patient.get("interest_text", ""), str) or len(patient.get("interest_text", "")) > 300:
        raise ValueError("interest_text must be a string of at most 300 characters")
    cleaned = dict(patient)
    for key in PATIENT_ARRAYS:
        cleaned[key] = list(patient.get(key, []))
    return cleaned


def _literal(text: str) -> Any:
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "null":
        return None
    try:
        return ast.literal_eval(text)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"Unsupported literal in rule: {text}") from exc


def _movie_value(movie: dict, path: str) -> Any:
    if path == "age_rating":
        data = movie["age_rating"]
        return f"{data['system']}:{data['value']}"
    value: Any = movie
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"Movie {movie.get('movie_id')}: missing attribute {path}")
        value = value[key]
    return value


def _compile_patient(expr: str):
    m = re.fullmatch(r"(known_sensitivities|current_symptoms|accessibility_requirements) contains ('[^']+')", expr)
    if m:
        field, value = m.groups()
        return lambda p: _literal(value) in p[field]
    m = re.fullmatch(r"age < (\d+)", expr)
    if m:
        number = int(m.group(1))
        return lambda p: p["age"] < number
    if expr == "content_avoidances is nonempty":
        return lambda p: bool(p["content_avoidances"])
    raise ValueError(f"Unsupported patient condition: {expr}")


def _compile_content(expr: str):
    if expr == "sensitivity_tags.content_warnings intersects content_avoidances":
        return lambda m, p: bool(set(m["sensitivity_tags"]["content_warnings"]) & set(p["content_avoidances"]))
    match = re.fullmatch(r"([a-zA-Z_][\w.]*) (==|!=|in|contains|>) (.+)", expr)
    if not match:
        raise ValueError(f"Unsupported movie condition: {expr}")
    path, operator, raw = match.groups()
    if path not in {
        "age_rating", "runtime_minutes", "sensitivity_tags.flashing_strobe_content",
        "sensitivity_tags.plot_complexity_estimate", "sensitivity_tags.content_warnings",
        "sensitivity_tags.threat_intensity_estimate", "sensitivity_tags.accessibility.subtitles_available",
        "sensitivity_tags.accessibility.audio_description_available",
    }:
        raise ValueError(f"Unsupported movie field in rule: {path}")
    expected = _literal(raw)
    if operator == "==":
        return lambda m, p: _movie_value(m, path) == expected
    if operator == "!=":
        return lambda m, p: _movie_value(m, path) != expected
    if operator == "in":
        if not isinstance(expected, (list, tuple, set)):
            raise ValueError("'in' expects a literal collection")
        return lambda m, p: _movie_value(m, path) in expected
    if operator == "contains":
        return lambda m, p: expected in (_movie_value(m, path) or [])
    if operator == ">":
        if type(expected) not in (int, float):
            raise ValueError("Numeric comparison requires numeric threshold")
        return lambda m, p: _movie_value(m, path) is not None and _movie_value(m, path) > expected
    raise ValueError(f"Unimplemented rule operator: {operator}")


def _confidence(movie: dict, expr: str) -> str:
    confidence = movie["annotation_confidence"]
    if "age_rating" in expr:
        return confidence["age_rating"]
    if "flashing_strobe_content" in expr:
        return confidence["flashing_strobe_content"]
    if "content_warnings" in expr:
        return confidence["content_warnings"]
    if "plot_complexity_estimate" in expr or "threat_intensity_estimate" in expr:
        return confidence["subjective_estimates"]
    if "accessibility." in expr:
        return confidence["accessibility"]
    if "runtime_minutes" in expr:
        return "recorded_metadata"  # Runtime has no dedicated evidence-confidence field.
    return "unknown"


class Rules:
    """Closed rule grammar: no eval(), no arbitrary expressions, fail on invalid entries."""

    def __init__(self, rules: list[dict]):
        if not isinstance(rules, list) or not rules:
            raise ValueError("At least one guideline rule is required")
        identifiers = set()
        compiled = []
        required = {"rule_id", "patient_attribute", "content_attribute", "severity", "penalty_weight", "justification_type", "source", "notes"}
        for rule in rules:
            if set(rule) != required:
                raise ValueError(f"Rule has missing/extra fields: {rule.get('rule_id')}")
            rid = rule["rule_id"]
            if not isinstance(rid, str) or not rid or rid in identifiers:
                raise ValueError(f"Duplicate or invalid rule identifier: {rid}")
            identifiers.add(rid)
            if rule["severity"] not in {"hard_exclude", "soft_penalty"}:
                raise ValueError(f"Invalid severity: {rid}")
            weight = rule["penalty_weight"]
            if rule["severity"] == "hard_exclude" and weight is not None:
                raise ValueError(f"Hard exclusion cannot have a score weight: {rid}")
            if rule["severity"] == "soft_penalty" and (type(weight) not in (int, float) or not -1 <= weight < 0 or not math.isfinite(weight)):
                raise ValueError(f"Soft penalties must be finite negative weights: {rid}")
            if rule["justification_type"] not in {"sourced", "inferred"} or not rule["source"]:
                raise ValueError(f"Missing/invalid source justification: {rid}")
            compiled.append((rule, _compile_patient(rule["patient_attribute"]), _compile_content(rule["content_attribute"])))
        self.compiled = compiled
        self.raw = rules

    def evaluate(self, patient: dict, movie: dict) -> list[dict]:
        result = []
        for rule, check_patient, check_movie in self.compiled:
            patient_match = bool(check_patient(patient))
            movie_match = bool(check_movie(movie, patient)) if patient_match else None
            triggered = bool(patient_match and movie_match)
            outcome = rule["severity"] if triggered else "pass"
            conf = _confidence(movie, rule["content_attribute"])
            item = {
                "rule_id": rule["rule_id"], "outcome": outcome,
                "patient_condition": rule["patient_attribute"], "movie_condition": rule["content_attribute"],
                "patient_condition_met": patient_match, "movie_condition_met": movie_match,
                "justification_type": rule["justification_type"], "source": rule["source"],
                "movie_evidence_confidence": conf,
            }
            if triggered and "content_warnings intersects" in rule["content_attribute"]:
                item["matched_content_warnings"] = sorted(set(movie["sensitivity_tags"]["content_warnings"]) & set(patient["content_avoidances"]))
            if triggered and outcome == "soft_penalty":
                factor = CONFIDENCE_FACTOR[conf]
                item["configured_penalty"] = rule["penalty_weight"]
                item["confidence_multiplier"] = factor
                item["applied_penalty"] = round(rule["penalty_weight"] * factor, 6)
            result.append(item)
        return result


def validate_catalog(movies: list[dict], rules: Rules) -> None:
    if not movies:
        raise ValueError("Movie catalog cannot be empty")
    seen = set()
    all_fields = {"age_rating", "flashing_strobe_content", "content_warnings", "subjective_estimates", "accessibility"}
    for movie in movies:
        mid = movie.get("movie_id")
        if not isinstance(mid, str) or not mid or mid in seen:
            raise ValueError(f"Missing or duplicate movie_id: {mid}")
        seen.add(mid)
        if not isinstance(movie.get("title"), str) or not movie["title"].strip():
            raise ValueError(f"Missing title: {mid}")
        if type(movie.get("runtime_minutes")) not in (int, float) or movie["runtime_minutes"] <= 0:
            raise ValueError(f"Invalid runtime: {mid}")
        if not isinstance(movie.get("short_premise"), str) or not movie["short_premise"].strip():
            raise ValueError(f"Missing synopsis: {mid}")
        norm_genres(movie.get("genres"))
        rating = movie.get("age_rating")
        if not isinstance(rating, dict) or rating.get("value") not in RATING_VALUES.get(rating.get("system"), set()):
            raise ValueError(f"Missing or unknown age classification: {mid}")
        tags = movie.get("sensitivity_tags")
        confidence = movie.get("annotation_confidence")
        if not isinstance(tags, dict) or not isinstance(confidence, dict) or not all_fields <= set(confidence):
            raise ValueError(f"Missing sensitivity or confidence metadata: {mid}")
        if any(confidence[k] not in CONFIDENCE_FACTOR for k in all_fields):
            raise ValueError(f"Invalid annotation confidence: {mid}")
        if confidence["age_rating"] == "unknown":
            raise ValueError(f"Age classification unverified: {mid}")
        if tags.get("flashing_strobe_content") not in {"confirmed_present", "none", "unknown"}:
            raise ValueError(f"Invalid flashing-content label: {mid}")
        if tags["flashing_strobe_content"] == "none" and confidence["flashing_strobe_content"] == "high":
            raise ValueError(f"Current catalog has no verified no-flashing clearance: {mid}")
        if not isinstance(tags.get("content_warnings"), list) or any(not isinstance(x, str) for x in tags["content_warnings"]):
            raise ValueError(f"Bad content warnings: {mid}")
        if tags.get("plot_complexity_estimate") not in {"simple", "moderate", "dense"}:
            raise ValueError(f"Invalid plot complexity: {mid}")
        if tags.get("threat_intensity_estimate") not in {None, "very_mild", "mild", "moderate", "strong"}:
            raise ValueError(f"Invalid threat intensity: {mid}")
        access = tags.get("accessibility")
        if not isinstance(access, dict) or any(not (type(access.get(k)) is bool or access.get(k) == "unknown") for k in ("subtitles_available", "audio_description_available")):
            raise ValueError(f"Invalid accessibility attributes: {mid}")
        # Evaluation occurs with empty arrays/age, testing every rule path for missing fields.
        rules.evaluate(validate_patient({"age": 30}), movie)


class Scorer:
    """Meaning-aware content scoring with strict genre fallbacks.

    Does not use diagnosis, treatment phase, symptoms, or rule text as taste
    inputs. Profiles are never sent outside the running application.
    """

    def __init__(self, movies: list[dict], encoder=None):
        self.movies = {m["movie_id"]: m for m in movies}
        self.genres = {mid: norm_genres(m["genres"]) for mid, m in self.movies.items()}
        self.supported_genres = set().union(*self.genres.values())
        self.encoder = encoder if encoder is not None else SemanticEncoder()
        self._movie_vectors = None
        self._movie_lock = Lock()
        # Only catalog information is sent to the pretrained, locally run encoder.
        self._texts = [
            "Movie genres: " + ", ".join(m["genres"]) + ". Story: " + m["short_premise"]
            for m in movies
        ]
        self._movie_ids = [m["movie_id"] for m in movies]
        self._movie_rows = {m["movie_id"]: i for i, m in enumerate(movies)}

    def _movie_embeddings(self):
        # Load catalog vectors once even if concurrent FastAPI requests arrive.
        if self._movie_vectors is None:
            with self._movie_lock:
                if self._movie_vectors is None:
                    vectors = np.asarray(self.encoder.encode(self._texts), dtype=np.float32)
                    if vectors.shape[0] != len(self._texts) or vectors.ndim != 2:
                        raise SemanticUnavailable("Movie encoder returned the wrong vector dimensions")
                    self._movie_vectors = vectors
        return self._movie_vectors

    @staticmethod
    def intent(patient: dict, supported_genres: set[str]) -> str:
        """Only actual interest text and noncatalog genre labels form the query."""
        provided = norm_genres(patient["preferred_genres"])
        unmatched = sorted(provided - supported_genres)
        description = patient.get("interest_text", "").strip()
        if not unmatched:
            return description
        genre_intent = "I enjoy movies with themes or genre: " + ", ".join(unmatched) + "."
        return (description + " " + genre_intent).strip() if description else genre_intent

    def semantic_scores(self, patient: dict) -> dict[str, float] | None:
        query = self.intent(patient, self.supported_genres)
        if not query:
            return None
        movie_embeddings = self._movie_embeddings()
        query_embedding = np.asarray(self.encoder.encode([query]), dtype=np.float32)
        if query_embedding.shape != (1, movie_embeddings.shape[1]):
            raise SemanticUnavailable("Query and movie embeddings use different dimensions")
        similarities = movie_embeddings @ query_embedding[0]
        if not np.isfinite(similarities).all():
            raise SemanticUnavailable("Invalid semantic-similarity values")
        return {mid: round(float(max(0.0, min(1.0, value))), 6)
                for mid, value in zip(self._movie_ids, similarities)}

    def score(self, patient: dict, movie: dict, semantic_scores: dict[str, float] | None = None) -> dict:
        preferences = norm_genres(patient["preferred_genres"])
        supported_preferences = preferences & self.supported_genres
        film_genres = self.genres[movie["movie_id"]]
        shared = film_genres & supported_preferences
        coverage = len(shared) / len(supported_preferences) if supported_preferences else 0.0
        focus = len(shared) / len(film_genres) if film_genres else 0.0
        semantic = semantic_scores.get(movie["movie_id"], 0.0) if semantic_scores is not None else None
        has_text = bool(patient.get("interest_text", "").strip())
        unmatched_genres = preferences - self.supported_genres
        if semantic is None:
            weights = WEIGHTS_NO_TEXT if supported_preferences else {"semantic_similarity": 0.0, "genre_coverage": 0.0, "genre_focus": 0.0}
        elif not supported_preferences:
            weights = {"semantic_similarity": 1.0, "genre_coverage": 0.0, "genre_focus": 0.0}
        elif has_text:
            weights = WEIGHTS_WITH_TEXT
        elif unmatched_genres:
            weights = WEIGHTS_MIXED_UNKNOWN
        else:
            weights = WEIGHTS_NO_TEXT
        features = {
            "semantic_similarity": semantic,
            "genre_coverage": round(coverage, 6) if supported_preferences else None,
            "genre_focus": round(focus, 6) if supported_preferences else None,
        }
        contributions = {name: round((features[name] or 0.0) * weight, 6) for name, weight in weights.items()}
        score = round(sum(contributions.values()), 6)
        return {
            "taste_score": score,
            "taste_breakdown": features,
            "taste_contributions": contributions,
            "taste_baseline": 0.0,
            "weights": dict(weights),
            "matched_genres": sorted(shared),
        }

    def similarity(self, one_id: str, two_id: str) -> float:
        genres_a, genres_b = self.genres[one_id], self.genres[two_id]
        union = genres_a | genres_b
        genre_jaccard = len(genres_a & genres_b) / len(union) if union else 0.0
        semantic = 0.0
        if self._movie_vectors is not None:
            semantic = float(np.clip(np.dot(
                self._movie_vectors[self._movie_rows[one_id]],
                self._movie_vectors[self._movie_rows[two_id]]), 0.0, 1.0))
        # Same-title-family is a weak lexical cue, never considered proof of a franchise.
        prefix = lambda name: re.sub(r"\s+(?:\d+|ii|iii|iv)$", "", name.casefold())
        same_title = prefix(self.movies[one_id]["title"]) == prefix(self.movies[two_id]["title"])
        if self._movie_vectors is not None:
            return min(1.0, 0.45 * genre_jaccard + 0.50 * semantic + 0.05 * float(same_title))
        return min(1.0, 0.95 * genre_jaccard + 0.05 * float(same_title))


def _explanation(row: dict) -> str:
    """No medical promises, no undocumented plot claims, no leaked audit IDs."""
    genres = ", ".join(row["matched_genres"][:3])
    sem = row["taste_breakdown"].get("semantic_similarity")
    if genres and sem is not None and sem >= MIN_SEMANTIC_AFFINITY:
        reason = f"Matches your interest in {genres} and the themes you described."
    elif genres:
        reason = f"Matches your preference for {genres}."
    elif sem is not None and sem >= MIN_SEMANTIC_AFFINITY:
        reason = "Its synopsis is semantically related to the kind of story you described."
    else:
        reason = "No strong preference match is available."
    if any(x["rule_id"] == "R-10" for x in row["soft_penalties"]):
        reason += " Its longer runtime may be less comfortable with severe fatigue."
    elif row["soft_penalties"]:
        reason += " Some of its content may be a less comfortable fit for your stated sensitivities."
    return reason

class MovieRecommender:
    def __init__(self, movies: list[dict], rules: list[dict], semantic_encoder=None):
        self.rules = Rules(rules)
        validate_catalog(movies, self.rules)
        self.movies = tuple(movies)
        self.by_id = {m["movie_id"]: m for m in movies}
        self.scorer = Scorer(movies, encoder=semantic_encoder)
        self.rule_definitions = rules
        self.known_content_tags = {tag for m in movies for tag in m["sensitivity_tags"]["content_warnings"]}

    def _hard_rule_ids(self, patient: dict, movie: dict) -> set[str]:
        return {r["rule_id"] for r in self.rules.evaluate(patient, movie) if r["outcome"] == "hard_exclude"}

    def recommend(self, profile: dict, top_k: int = 5, diversify: bool = True) -> dict:
        patient = validate_patient(profile)
        unsupported_avoidances = set(patient["content_avoidances"]) - self.known_content_tags
        if unsupported_avoidances:
            raise ValueError(f"Unsupported content_avoidances: {sorted(unsupported_avoidances)}; the catalog has no corresponding annotated warning category")
        if type(top_k) is not int or not 1 <= top_k <= 20:
            raise ValueError("top_k must be an integer between 1 and 20")
        if type(diversify) is not bool:
            raise ValueError("diversify must be true or false")
        excluded = []
        eligible_raw = []
        for movie in self.movies:
            outcomes = self.rules.evaluate(patient, movie)
            hard = [r for r in outcomes if r["outcome"] == "hard_exclude"]
            if hard:
                excluded.append({"movie_id": movie["movie_id"], "title": movie["title"], "rule_evaluations": outcomes,
                                 "hard_exclusion_rule_ids": [r["rule_id"] for r in hard]})
                continue
            eligible_raw.append((movie, outcomes))

        # Unsupported known sensory factors have no film-specific metadata or rule.
        # Refuse recommendations rather than imply they were assessed (coverage veto,
        # not a new sourced clinical rule). The raw 16-rule trace remains auditable.
        coverage_gap = bool(set(patient["known_sensitivities"]) & UNMODELED_SENSITIVITIES)
        # Safety decisions come first. Semantic inference never sees excluded movies
        # as candidates, and NEVER modifies the underlying rule outcomes.
        semantic_scores = self.scorer.semantic_scores(patient) if eligible_raw and not coverage_gap else None
        scores_for_gate = sorted(semantic_scores[m["movie_id"]] for m, _ in eligible_raw) if semantic_scores else []
        semantic_floor = max(MIN_SEMANTIC_AFFINITY,
                             (median(scores_for_gate) + MIN_SEMANTIC_ADVANTAGE)
                             if len(scores_for_gate) >= 4 else MIN_SEMANTIC_AFFINITY)
        eligible = []
        no_preference = not patient["preferred_genres"] and not patient.get("interest_text", "").strip()
        for movie, outcomes in eligible_raw:
            taste = self.scorer.score(patient, movie, semantic_scores=semantic_scores)
            soft = [r for r in outcomes if r["outcome"] == "soft_penalty"]
            total_penalty = round(sum(r["applied_penalty"] for r in soft), 6)
            adjusted = round(taste["taste_score"] + total_penalty, 6)
            semantic = taste["taste_breakdown"]["semantic_similarity"]
            # A high embedding score can qualify even without exact genre tokens,
            # but weak semantic and nonexistent exact matches lead to abstention.
            relevant = bool(taste["matched_genres"]) or (
                semantic is not None and semantic >= semantic_floor
            )
            if no_preference or coverage_gap or not relevant:
                continue
            eligible.append({
                "movie_id": movie["movie_id"], "title": movie["title"], "genres": movie["genres"],
                "runtime_minutes": movie["runtime_minutes"], "age_rating": movie["age_rating"],
                **taste, "soft_penalties": soft, "total_penalty": total_penalty,
                "final_score": adjusted, "rule_evaluations": outcomes,
            })
        eligible.sort(key=lambda m: (-m["final_score"], -m["taste_score"], m["movie_id"]))
        if diversify:
            # Greedy MMR over top-ranked eligible candidates only, NEVER excluded titles.
            # Candidate pool is at least five times top_k to allow alternative genres.
            candidates = eligible[:max(25, 5*top_k)]
            chosen = []
            while candidates and len(chosen) < top_k:
                def score(row):
                    penalty = max((self.scorer.similarity(row["movie_id"], prev["movie_id"]) for prev in chosen), default=0.0)
                    return (0.88*row["final_score"] - 0.12*penalty, row["final_score"], row["taste_score"])
                best = min(candidates, key=lambda row: (-score(row)[0], -row["final_score"], -row["taste_score"], row["movie_id"]))
                best = dict(best)
                best["diversity_utility"] = round(score(best)[0], 6)
                chosen.append(best)
                candidates = [x for x in candidates if x["movie_id"] != best["movie_id"]]
        else:
            chosen = [dict(r, diversity_utility=None) for r in eligible[:top_k]]
        excluded_ids = {r["movie_id"] for r in excluded}
        if len(chosen) != len({r["movie_id"] for r in chosen}):
            raise RuntimeError("Duplicate recommendation escaped ranking")
        # Defense in depth: re-check hard rules AFTER every transformation (MMR, scoring).
        for row in chosen:
            if row["movie_id"] in excluded_ids or self._hard_rule_ids(patient, self.by_id[row["movie_id"]]):
                raise RuntimeError("Hard-excluded movie appeared in recommendation output")
            row["explanation"] = _explanation(row)
        warnings = []
        if len(chosen) < top_k:
            warnings.append(f"Only {len(chosen)} recommendations pass both the explicit restrictions and the preference-match gate; no unrelated movies were added.")
        if "photosensitive_seizure_trigger" in patient["known_sensitivities"]:
            warnings.append("No titles in this catalogue have verified no-flashing clearance. Unknown and low-confidence community 'none' reports are not proof of safety.")
        if patient["accessibility_requirements"]:
            warnings.append("Accessibility data is provider/version-specific and currently unverified; unknown is not available.")
        if patient["content_avoidances"]:
            warnings.append("Content-warning tags are positive observations; absence is not verified absence of a theme.")
        unmodeled_sensitivity = set(patient["known_sensitivities"]) & UNMODELED_SENSITIVITIES
        unmodeled_symptom = set(patient["current_symptoms"]) & UNMODELED_SYMPTOMS
        if unmodeled_sensitivity or unmodeled_symptom:
            warnings.append(f"No film-specific rule/evidence for reported factors: {', '.join(sorted(unmodeled_sensitivity | unmodeled_symptom))}. Do not interpret output as clearance for these factors.")
        if coverage_gap:
            warnings.append("No film-specific evidence/rule for reported sound or visual-motion sensitivities; recommendations withheld rather than treating them as cleared.")
        if no_preference:
            warnings.append("No movie preferences supplied; no movies were selected arbitrarily.")
        elif not chosen and eligible_raw:
            warnings.append("No strong match for the stated movie preferences. Try another genre or a short description.")
        return {
            "profile_id": patient.get("profile_id"), "requested_count": top_k, "returned_count": len(chosen),
            "recommendations": chosen, "excluded_candidates": excluded,
            "audit": {"catalog_size": len(self.movies), "eligible_count": len(eligible_raw), "preference_matched_count": len(eligible), "excluded_count": len(excluded),
                      "rule_count": len(self.rule_definitions), "hard_rule_ids_triggered": sorted({rid for m in excluded for rid in m["hard_exclusion_rule_ids"]}),
                      "soft_rule_ids_triggered": sorted({r["rule_id"] for m in eligible for r in m["soft_penalties"]}),
                      "diversity_enabled": diversify,
                      "all_recommendations_rechecked": True},
            "warnings": warnings,
            "disclaimer": "Synthetic-data demonstration, not medical advice or a certification of film/streaming-version safety.",
        }


def load_default(root: str | Path | None = None) -> MovieRecommender:
    project_root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    return MovieRecommender(read_records(project_root / "dataset" / "movies.json"), read_records(project_root / "rules" / "rules.json"))
