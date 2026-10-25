# Guideline Rules — Notes

The 16 rules in `rules.json` combine reported patient needs with movie attributes: **9 hard exclusions** and **7 soft penalties**. Rules **R-01, R-03, and R-05** are labelled `sourced` for their underlying risk or age-classification basis; the other **13 are `inferred`**. Even sourced rules require implementation choices. Source links are in `RULE_SOURCES.md`.

- **Hard exclusions** (R-01–R-06, R-09, R-15–R-16) remove a movie before taste scoring. They cannot be reversed by ranking, reranking, or an LLM.
- **Soft penalties** (R-07–R-08, R-10–R-14) reduce the taste score by their listed weights. The weights and runtime/complexity thresholds are **our heuristics, not clinical measurements**.
- **Age ratings** must be interpreted within their own systems (MPA, BBFC, CBFC). R-04 and R-06 are deliberately conservative about accompaniment; they are not blanket legal bans.
- **Uncertain evidence:** `unknown` flashing or low-confidence community reports of `none` are not safety clearances for photosensitive patients (R-02). Required captions/audio description must be verified `true` (R-15/R-16). These policies may leave **zero eligible movies**.
- **Content and confidence:** A recorded warning is a positive observation; a missing tag does not prove content is absent. Subjective threat/complexity estimates are low-confidence and used **only for soft penalties**.
- **Patient attributes:** Rules activate from explicit age, symptoms, sensitivities, avoidances, and accessibility needs—not diagnosis or treatment labels alone. No rule uses deleted patient fields such as `guardian_present`, `available_minutes`, or `viewing_region`.
