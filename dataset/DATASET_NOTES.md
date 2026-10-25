# Dataset Construction Notes

## Files Provided

### 1. movies.json

- **Final movie-data** Contains 72 records with movie ID, title, release year, language, genres, runtime, short premise, and age rating when documented.
- Includes sensitivity attributes such as flashing status, recorded content warnings, estimated violence, threat and plot complexity, and accessibility placeholders (subtitles and audio description both `unknown`).
- Contains concise attribute-confidence flags and serves as the main input to the recommender.

### 2. annotation_evidence.csv

- **Evidence file.** Contains 248 entries linked by `movie_id`.
- Records the attribute group, collection or annotation method, source URL, confidence, applicable version or scope, and known limitations.
- Keeps detailed provenance separate from the main JSON dataset.

### 3. build_dataset.py

- **Construction code.** An offline Python script that reads curated records, normalizes values, applies documented runtime corrections, checks consistency, and generates `movies.json` and `annotation_evidence.csv`.

### 4. source_records.json

- **Required code input.** Contains the 72 curated intermediate records, including original annotation fields and film-reference links.It is the raw json file which contains all the information.It is then cleaned to get the evidence file and final movie json file.

### 5. DATASET_NOTES.md(This file)

- **Documentation file.** Explains dataset construction, sources, completeness, missing information, and the assumptions behind the annotations.

**To reproduce:** Keep all five files in the same `dataset/` folder and run `python build_dataset.py`. Python 3 standard library is sufficient. The script regenerates the movie JSON and evidence CSV from `source_records.json`.

## Confidence Flags in `movies.json`

`annotation_confidence` is a small operational summary for the ranking and filtering code.It is present in the 'movies.json' file The full source URLs, confidence methods, and limitations remain in `annotation_evidence.csv`.

These levels describe the **quality of evidence for an annotation**, not the probability that a film is safe or that a patient will enjoy it.

- `age_rating`: `high` for a source-recorded published classification, otherwise `unknown`.
- `flashing_strobe_content`: `high` only for an explicitly recorded flashing warning, otherwise `unknown`.
- `content_warnings`: `medium` for positive tags manually mapped from source advice, otherwise `unknown`.
- `subjective_estimates`: `low` for curator-derived intensity or complexity estimates. These must not trigger hard safety exclusions.
- `accessibility`: `unknown`, because no provider-, country-, language-, or version-specific availability was verified.

The recommendation engine should use deterministic hard exclusions for known prohibited content and a separate policy for critical unknowns. Confidence can qualify soft-ranking explanations and evidence handling; it must **not** convert unknown flashing status into a safety clearance.

## How the Dataset Was Constructed

The catalogue was intentionally limited to **72 films**. Titles cover different genres, runtimes, age categories, and potentially sensitive themes. This is a designed test catalogue, **not** a representative sample of patients' movie preferences.

Film-specific [BBFC](https://www.bbfc.co.uk/) classification pages were used as primary references for selected content advice. Titles, genres, language, short premises, and runtimes were manually assembled and normalized in `source_records.json`; no live metadata API populated these fields.

Classification ratings were included only when a distinct published source was recorded (MPA ratings linked to film pages or a BBFC classification linked to BFI Player). The evidence file identifies the actual URL for each claim.

## Tagging Decisions

- A flashing/flickering warning explicitly recorded for a title was coded `confirmed_present`. All other flashing statuses were coded `unknown`, **not** `none` or verified safe.
- Content-warning labels were manually mapped from positive BBFC content advice. They are **selected positive observations**, not a comprehensive scene audit. An absent tag never proves the content is absent.
- `violence_intensity_estimate`, `threat_intensity_estimate`, and `plot_complexity_estimate` are **subjective curator estimates**. They are low-confidence features intended for exploratory or soft ranking, not clinical facts or justification for hard safety exclusions.
- The builder standardizes lists and IDs (`MV001`–`MV072`), preserves missing age ratings as `null`, adds `unknown` accessibility placeholders for every movie, and emits source-level caveats in the separate evidence file.

## Provenance and Completeness

### 1. Core Movie Descriptions

- All **72/72 movies** have a movie ID, title, release year, genre, language, runtime, and brief premise.
- These were compiled from curated film records and editorial summaries, with film links available in `annotation_evidence.csv`.

### 2. Flashing-Content Warnings

- **14/72 movies** have recorded positive BBFC flashing-content warnings.
- The remaining **58/72 movies** are marked as `unknown`.
- No movie is certified as completely free from flashing content.

### 3. Age Certifications

- **22/72 movies** have recorded classifications with supporting sources.
- The remaining **50/72 movies** have `null` values.
- Different rating systems are kept separate rather than treated as interchangeable.

### 4. Content-Warning Tags

- **66/72 movies** have at least one recorded positive content-warning category.
- Missing or unrecorded warnings are not treated as confirmation that the content is absent.

### 5. Subjective Estimates

- All **72/72 movies** have plot-complexity and intensity estimates.
- These are based on editorial interpretation and are marked as low-confidence annotations rather than verified facts.

### 6. Captions and Audio Description

- All **72/72 movies** have accessibility attributes under `sensitivity_tags.accessibility`, with both values marked `unknown`.
- No provider- and version-specific availability was verified, so these attributes cannot currently confirm accessibility.

### 7. Sudden Loud Sounds and Camera-Motion Intensity

- These are not included as verified attributes.
- Consistent film-version-specific evidence was unavailable across the catalogue.

## Handling Missing and Ambiguous Information

BBFC sometimes classifies different versions or cuts of the same movie separately. The `version_or_scope` field in `annotation_evidence.csv` records the source scope and identifies cases where the eventual playback version has not been matched.

Missing or uncertain values were retained as `unknown` or `null` rather than replaced with assumptions. No missing value was silently converted into proof of safety.

## 4. Limitations for Downstream Recommendations

The recommender must treat explicit positive warnings as evidence, retain uncertainty for unverified features, and enforce its hard-exclusion policy independently of taste scores.

For patients with critical sensitivities, the system may have fewer than five candidates with adequate evidence. Subjective plot and intensity estimates should be used only as explainable soft signals.
