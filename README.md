# Movie-recommendation-system-for-patients

A prototype that recommends **up to five movies** based on a patient's interests and reported sensitivities. It can also return no movies when there is not enough information to recommend responsibly. **This is a student demonstration, not a clinically validated tool.** All patient profiles are synthetic.

## 1. Where the data came from

The dataset contains **72 curated movies** with genres, short descriptions, runtimes, age classifications and content-sensitivity tags. Film information and recorded content warnings were researched using film-specific [BBFC](https://www.bbfc.co.uk/) pages; individual source links are saved in [`dataset/source_records.json`](dataset/source_records.json).

**Gaps are documented:** only **22/72** films have separately sourced age classifications; flashing status is **unknown for 58/72**; and subtitle/audio-description availability has not been verified. Plot complexity and threat intensity are human estimates. A missing warning **does not mean** a movie is confirmed safe. Details: [`dataset/DATASET_NOTES.md`](dataset/DATASET_NOTES.md).

## 2. Where the rules came from

I defined **16 rules: 9 hard exclusions and 7 soft penalties**.

- **Hard exclusion:** removes a movie regardless of how well it matches the patient's interests (for example, a recorded flashing risk for someone who reports photosensitivity).
- **Soft penalty:** lowers a movie's rank without banning it (for example, a long film for someone reporting severe fatigue).

**3 rules are labeled source-grounded; 13 are explicitly labeled inferred.** Public context includes [Epilepsy Foundation guidance](https://www.epilepsy.com/what-is-epilepsy/seizure-triggers/photosensitivity), [film rating guidance](https://www.filmratings.com/ratings-guide/) and [cancer-related fatigue guidance](https://www.cancer.gov/about-cancer/treatment/side-effects/fatigue). Their application to movie selection, including exact thresholds and penalty weights, involves **my engineering judgments**, not clinical advice. Specific rule conditions, justifications and source references are recorded in [`rules/rules.json`](rules/rules.json),[`rules/Rules_notes.md`](rules/Rules_notes.md) and [`rules/Rule_sources.md`](rules/Rule_sources.md). Research decisions and weak-rule concerns are in [`research/decisions_log.md`](research/decisions_log.md).

## 3. Why this recommendation approach?

I chose **semantic content matching with separate, deterministic safety rules**:

1. Apply hard exclusions **before** ranking.
2. Match patient interests to movie descriptions using the pretrained **Sentence Transformer (`all-MiniLM-L6-v2`)** and/or preferred genres.
3. Subtract soft penalties **separately** from the preference score.
4. Add limited variety through **MMR reranking**, then check hard exclusions again before returning results.

An initial **TF-IDF** method was replaced because different words can express the same interest. Semantic embeddings capture more of that meaning. Collaborative filtering would require viewing histories that we do not have; an LLM would add complexity to decisions that must remain auditable. The weights and thresholds are documented heuristics, **not medically validated scores**. The model runs locally after its first download, without an API key.

## 4. What the evaluation showed

On **15 synthetic patient profiles plus one control**, the system returned **60 recommendations with zero observed hard-rule violations**. Four profiles received no recommendations. Manually inspected cases showed different choices for children, adults and patients with specific content avoidances. Diversity reranking reduced average genre overlap from **0.646 to 0.597**.

**Important limit:** this evaluation used genre preferences, **not free-text semantic queries**. The pretrained semantic model still needs a separate live smoke test. No real-patient outcomes or clinician validation were available. See [`evaluation/EVALUATION.md`](evaluation/EVALUATION.md).

## 5. How to run and review

From the repository's main folder:

```bash
python -m pip install -r requirements.txt
python -m recommender.semantic
python evaluation/evaluate.py
python -m uvicorn api:app --reload
```

The model needs internet access on its first download. Open **http://127.0.0.1:8000/docs** to test the API with a patient profile entered directly as JSON.

- **`POST /recommendations`** — Up to five movies with explanations, taste-score breakdowns, each evaluated rule and its outcome (`pass`, `soft_penalty` or `hard_exclude`), plus a real excluded example **when one exists**. It keeps soft penalties distinct from taste scores and includes rule sources.
- **`POST /recommendations/audit`** — More detailed technical results, including the full list of excluded candidates.
- **`GET /health`** — Reports whether the API is running and the catalog/rule counts.

For the no-constraint control, no movie may be excluded; the API says so instead of inventing an excluded example.

## Repository guide

| Location | What it contains |
|---|---|
| `dataset/` | Movie catalog, patient profiles, evidence, sources and data-building script. |
| `rules/` | Safety/comfort rules, justifications and source links. |
| `recommender/` | Semantic model, matching, filtering, scoring and diversity logic. |
| `evaluation/` | Reproducible checks and a short evaluation summary. |
| `research/` | Timestamped research and design decisions. |
| `api.py` | The recommendation, audit and health endpoints. |
| `requirements.txt` | Packages needed to run the project. |
| `README.md` | Project overview and usage instructions. |
