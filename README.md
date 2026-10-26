# Patient-Appropriate Movie Recommender

A student prototype that suggests **up to five movies** based on a patient's stated interests, age, sensitivities and accessibility needs. It applies explicit eligibility rules before ranking; when the available evidence is insufficient, it can return **no recommendations**. This is **not a clinically validated or medically certified system**. All patient profiles are synthetic.

## 1. Dataset: where the movie information came from

The catalog contains **72 manually curated films**, selected to cover different genres, ages, runtimes and content themes so that the rules can be tested on varied cases. Each film has a short editorial premise, genres, runtime, an age-classification label and recorded sensitivity information.

- **Sources:** Individual [BBFC film pages](https://www.bbfc.co.uk/) support selected content-advice annotations; classification labels are linked separately to their recorded sources, **often secondary film listings**, rather than assuming a BBFC rating is equivalent to an MPA or CBFC rating. Film-by-film URLs and methods appear in [`dataset/source_records.json`](dataset/source_records.json) and [`dataset/annotation_evidence.csv`](dataset/annotation_evidence.csv).

- **Coverage:** 72/72 have a recorded age classification (**62 MPA, 8 CBFC, 2 BBFC**), but confidence and the classified film version vary. Flashing status is **18 positive reports, 4 low-confidence community reports of no flashes, and 50 unknown**. **No film has independently verified no-flashing clearance.** Subtitle/audio-description availability is unknown for every title.

- **Uncertainty:** Content-warning tags are non-exhaustive. Plot complexity and threat estimates are subjective. A missing warning **never proves a movie is free of that content**; the ratings and warning labels are not universal medical safety certificates.

The reproducible data-building script and the remaining gaps are described in [`dataset/DATASET_NOTES.md`](dataset/DATASET_NOTES.md).

## 2. Rules: sources and decisions

The system has **16 rules: 9 hard exclusions and 7 soft penalties**. **Three are labeled sourced; 13 are explicitly inferred.** A cited source may establish a general risk, but the decision to apply it to movie selection can still be our own policy.

- **Hard exclusions** remove movies that conflict with a reported flashing trigger (R-01–R-02), age restrictions (R-03–R-06), stated content avoidances (R-09), or required accessibility (R-15–R-16).

 Public grounding includes [Epilepsy Foundation](https://www.epilepsy.com/what-is-epilepsy/seizure-triggers/photosensitivity) guidance and the [MPA](https://www.filmratings.com/ratings-guide/), [BBFC](https://www.bbfc.co.uk/our-age-ratings) and [CBFC](https://cbfcindia.gov.in/cbfcAdmin/certification.php) rating systems.

- **Soft penalties** lower—but do not prohibit—movies that may be less comfortable because of age-rating cautions (R-07–R-08), fatigue, concentration difficulty, nausea, light sensitivity or distress (R-10–R-14). Translating general symptom guidance into film preferences is **an inference**, not a clinical rule.


**Why separate them?** Hard exclusions are never overridden by taste scores or diversity reranking. Soft penalties stay separate from the taste score and are adjusted for annotation confidence. Their numerical weights are engineering estimates, **not medical risk probabilities**.


**Limits acknowledged:** R-02 conservatively rejects unverified flashing status and may leave no eligible movies; R-04 simplifies guardian circumstances; R-14 relies on subjective threat ratings. Missing content warnings do not prove content is absent.

The full conditions, weights and justifications are in [`rules.json`](rules/rules.json), with [rule notes](rules/Rules_notes.md), [source links](rules/Rule_sources.md) and a [research log](research/decisions_log.md).

## 3. Recommendation method: 

I chose **semantic content matching + deterministic rules**, rather than having an LLM decide safety:

1. **Filter first:** Run all 16 rules on every film and remove any hard-excluded candidate.
2. **Match interests:** When a patient supplies free-text interests, use local `all-MiniLM-L6-v2` Sentence Transformer embeddings to compare meaning with each movie's genre and premise; preferred genres also contribute. For the provided **genre-only test profiles**, use direct genre coverage and genre focus without inventing a text query.
3. **Adjust comfort:** Subtract visible, evidence-confidence-adjusted soft penalties from the separate taste score.
4. **Add limited variety:** Apply MMR to eligible candidates, then **re-check hard exclusions** before returning results. If no meaningful or adequately supported match remains, return fewer than five—or zero.

**Why this approach instead of alternatives?** TF-IDF relies on word overlap and may miss similar meanings expressed differently, whereas semantic embeddings can capture these relationships. Collaborative filtering was unsuitable because patient interaction history was unavailable. An LLM or RAG approach would introduce additional complexity and dependencies without being necessary for deterministic, auditable safety filtering. Semantic relevance has not yet been validated using human preference labels.

### Scoring and retrieval logic 

The recommendation system combines semantic similarity and genre matching to calculate a taste score. The weights depend on the information provided by the patient.

| Patient Preferences | Semantic Similarity | Genre Coverage | Genre Focus |
|---|---:|---:|---:|
| Free-text interests + known genres | 0.72 | 0.22 | 0.06 |
| Known genres only | 0.00 | 0.80 | 0.20 |
| Known + unknown genres | 0.60 | 0.32 | 0.08 |
| Only free-text interests or unknown genres | 1.00 | 0.00 | 0.00 |

**1. Taste Score**

$$
\text{Taste Score} = w_s S + w_c C + w_f F
$$

Where:
- **S:** Semantic cosine similarity between patient interests and movie descriptions.
- **C:** Proportion of preferred genres matched by the movie.
- **F:** Proportion of the movie's genres matching patient preferences.
- **w_s, w_c, w_f:** Weights shown in the table above.

**2. Final Score with Soft Penalties**

$$
\text{Final Score} = \text{Taste Score} + \sum_i p_i c_i
$$

Where:
- **p_i:** Negative penalty assigned to a triggered soft rule.
- **c_i:** Confidence multiplier for the corresponding movie annotation.

Confidence multipliers are 1.0 (high), 0.85 (medium), 0.5 (low), and 0 (unknown). Soft penalties reduce ranking scores without automatically excluding movies.

**3. Diversity Reranking (MMR)**

$$
\text{MMR Score} = 0.88 \times \text{Final Score} - 0.12 \times \text{Maximum Similarity to Selected Movies}
$$

The 0.88 weight prioritizes relevance, while 0.12 encourages variety. MMR operates only on eligible movies and cannot override hard exclusions.

**Weight and Threshold Justification:** Semantic similarity receives greater weight when free-text interests are available, while genre matching is prioritized for genre-only preferences. For movies without an exact genre match, a conservative semantic threshold (cosine similarity ≥ 0.27, with a 0.05 margin above the catalog median when applicable) helps prevent weak recommendations. These weights and thresholds are engineering heuristics, not clinically validated or optimized using real patient preference data.


## 4. Evaluation: 

The reproducible evaluation used **15 synthetic profiles and one no-constraint control**: **60 movies returned, zero observed hard-rule violations**, four profiles with no recommendations. Four examples were manually reviewed to check that pediatric, adult and avoidance-driven profiles do not all receive the same generic list. MMR reduced mean genre overlap from **0.646 to 0.597**; lower overlap indicates variety, **not** better safety or accuracy.

**Important:** The supplied profiles contain only genre preferences, so those results test filtering, genre scoring and diversity—**not the live semantic encoder**. There are no patient outcomes, clinician assessments or ground-truth relevance labels. See [`evaluation/EVALUATION.md`](evaluation/EVALUATION.md).

## 5. Run and inspect

From the repository root (first model use needs internet):

```bash
python -m pip install -r requirements.txt
python -m recommender.semantic
python evaluation/evaluate.py
python -m uvicorn api:app --reload
```

Open **http://127.0.0.1:8000/docs**. Use **`POST /recommendations`** with an **inline patient JSON object**, not a patient ID. It returns up to five movies with genre/text feature breakdowns, separate soft penalties, outcomes of all 16 rules, rule provenance with direct source URLs and **one genuine hard-excluded example when exclusions exist**. The unrestricted control has no excluded example to show. **`POST /recommendations/audit`** provides the full candidate trace; **`GET /health`** shows catalog and rule counts. Neither endpoint needs an LLM API key.

## Repository guide

| Location | Purpose |
|---|---|
| `dataset/` | Film catalog, 16 test profiles, evidence and reproducible dataset builder. |
| `rules/` | 16 machine-readable rules, rationale and independently checkable links. |
| `recommender/` | Semantic embeddings, genre matching, hard filtering, scoring and MMR. |
| `evaluation/` | Executable checks and concise evaluation summary. |
| `research/` | Timestamped research decisions and acknowledged uncertainty. |
| `api.py` | Recommendation, audit and health API endpoints. |
| `requirements.txt` | Python dependencies. |
| `README.md` | Project explanation and running instructions. |

### Main files inside the folders

| Folder | File(s) | Purpose |
|---|---|---|
| `dataset/` | `movies.json`, `patient_profiles.json`, `source_records.json`, `annotation_evidence.csv`, `build_dataset.py`, `DATASET_NOTES.md` | Movie annotations, synthetic patient profiles, source evidence, dataset construction and documentation of data gaps. |
| `rules/` | `rules.json`, `Rules_notes.md`, `Rule_sources.md` | Rules, their logic, limitations and source links. |
| `recommender/` | `engine.py`, `semantic.py`, `__init__.py` | Safety/ranking engine, embedding model and Python package marker. |
| `evaluation/` | `evaluate.py`, `EVALUATION.md` | Reproducible evaluation and its short summary. |
| `research/` | `decisions_log.md` | Research and architecture decisions. |
