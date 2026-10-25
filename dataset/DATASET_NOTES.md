# Dataset Construction Notes

## 1. Files provided

**1. `movies.json`** — Main 72-movie dataset for the recommendation system. Contains movie ID, title, release year, language, genre, runtime, short premise, documented age rating, sensitivity tags, subjective complexity/intensity estimates, unknown accessibility flags, and short per-attribute annotation confidence summaries.

**2. `annotation_evidence.csv`** — Movie-level evidence and provenance.It contains the sources from which the data is taken. It links each movie ID to supporting URLs, evidence method, confidence, version/scope, and limitations.

**3. `build_dataset.py`** — Standard-library Python script that reconstructs `movies.json` and `annotation_evidence.csv` from the curated source records. It checks data consistency.

**4. `source_records.json`** — Manually curated inputs from the sources needed to reproduce the dataset, including source links and annotation notes. 

**5. `patient_profiles.json`** - Synthetic patient records generated to test the recommendations sytem.

**6. `DATASET_NOTES.md(This file)`** — Dataset file description,construction, coverage, evidence-quality and missing-data explanations.

## 2. Dataset construction

We selected a deliberate mix of animated/family films, comedies, dramas, thrillers, action and science fiction, with different runtimes and content intensities. This is an **evaluation-oriented demonstration catalog** rather than a statistically representative sample of cinema or patient taste. 

The film metadata was compiled into `source_records.json` through manual curation and editorial summarization, with BBFC film classification entries as references for selected content-advice tags. Ratings were added when an identifiable published classification was located.

Content-warning tags are **selected positive manual mappings** from public film advice rather than exhaustive annotations. Plot complexity and threat/violence intensity estimates are subjective and assigned **low** confidence; they are not clinically tested. Some version and classification records differ from the intended playback version. Film runtimes are feature-only where supporting information distinguished them from a cinema program bundled with a short.

Flashing content is recorded as follows:

- **`confirmed_present`** — A BBFC listing explicitly reports flashing/flickering (high confidence *for the cited classified version*) or a community report specifically describes flashes (low/medium confidence, **not** a clinical test). Check `annotation_confidence` and the evidence CSV; the label alone is not a measured clinical flash-risk threshold.
- **`none`** — Only a small number of films have crowdsourced *no-flashing* votes and no positive reports on the inspected page. These are recorded with **low confidence**. **They are not independently certified flashing-free** and must not automatically be approved for a patient with a photosensitive seizure trigger.
- **`unknown`** — No sufficiently specific positive or negative report was recorded. This does **not** mean the film is safe.

Accessibility fields (`subtitles_available`, `audio_description_available`) are present for all movies but set to `unknown`: availability changes by platform, territory, language, and release version. No dependable provider-specific availability was verified. Sudden loud noises and camera-motion intensity are not asserted as verified features.

## 3. Provenance, completeness and gaps

- **Core movie fields:** 72/72 movies have title, internal ID, year, original language, genre, runtime and brief editorial premise. Source-level film links and caveats appear in `annotation_evidence.csv`.
- **Age ratings:** **72/72** now have a recorded published classification: **62 MPA (U.S.), 8 CBFC (India), and 2 BBFC (UK)**. Each recorded rating has an evidence row; ratings have **high** confidence for directly cited official classification lists and **medium** for secondary listings. The classification is a country/version-specific label, not a patient-safety guarantee.
- **Flashing-content reports:** **18/72** have positive flashing reports with mixed confidence (official classification vs. community observations); **4/72** have *low-confidence community no-flashing reports*; **50/72** remain `unknown`. **Zero movies are independently certified photosensitivity-safe.**
- **Content-warning tags:** **66/72** have at least one positive mapped tag. Missing tags never prove absence of the corresponding theme.
- **Subjective estimates:** 72/72 have plot complexity estimates, 44/72 have a violence-intensity estimate, and 47/72 have a threat-intensity estimate. They are low-confidence and should only contribute to soft personalization/comfort scoring.
- **Accessibility:** 72/72 marked `unknown` for captions/subtitles and audio description; none is certified available for a specified platform/region/cut.

**Ambiguities:** BBFC often classifies feature releases, trailers, home-media cuts and screenings with shorts separately. The evidence CSV retains the reviewed `version_or_scope`. An official or community source link is not a guarantee that every editorial mapping is correct. A given title can differ between playback versions. The entire catalog was not independently reviewed scene by scene.

**Runtimes:** The builder uses feature-only lengths for *Finding Nemo* (100 minutes) and *Encanto* (102 minutes, as listed by Disney), and the 92-minute home-entertainment feature of *Up*, rather than longer screening-program listings that include accompanying shorts. These choices are documented in source record fields and evidence.

## 4. Downstream limitations

This is a **technical demonstration dataset, not clinical safety certification**. The recommendation engine must apply deterministic hard excludes to established prohibited conditions independently of taste matching or diversity. For critical risk factors, an unresolved or low-confidence no-flashing report should **not** be considered a verified clearance, even if that leaves fewer than five (or zero) recommendations. Subjective complexity and intensity labels should only be used as transparently weighted soft signals. The evaluation should report failure to establish suitable candidates honestly rather than silently relaxing constraints.
