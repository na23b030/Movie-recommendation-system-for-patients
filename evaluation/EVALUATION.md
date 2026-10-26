# Evaluation Summary

Run `python evaluation/evaluate.py` to reproduce these numbers from the included movies, rules and patient profiles.

## Results

| Measure | Result |
|---|---:|
| Movies / profiles | 72 / 16 (15 synthetic + 1 control) |
| Recommendations returned | 60 |
| Hard-rule violations | **0 observed** |
| Profiles receiving 5 films | 12/16 |
| Profiles receiving none | 4/16 |
| Rules | 9 hard, 7 soft |
| Evidence classification | 3 sourced, 13 inferred |

Every returned title was checked against the hard rules. Exclusions occur before ranking and are rechecked after diversity selection; soft penalties affect scores only.

## Four manual inspections

- **P002 — child:** Toy Story, Inside Out 2, Ratatouille. Child-appropriate genres remain after age exclusions.
- **P005 — concentration difficulty:** The Martian, Knives Out, Interstellar. Dense plots can rank lower, but are not automatically banned.
- **P009 — adult thriller preference:** Joker, Asthram, Knives Out. Adult selections differ from the child profile.
- **P014 — bereavement/self-harm avoidances:** Julie & Julia, La La Land, Chef. 22 tagged titles excluded while remaining preferences still matter.

## Variety and limitations

- Mean genre overlap **0.597 with MMR vs. 0.646 without**; this measures variety, not accuracy or safety.
- These profiles contain **genre preferences only**: this run does **not** test live pretrained semantic embeddings. Run `python -m recommender.semantic` separately, then validate meaningful free-text examples.
- Age/content evidence is version-dependent and incomplete; untagged content is not proven absent. There is **no clinician review, real patient outcome or ground-truth recommendation label**.
- **Weak rule R-02:** unknown flashing is treated as a veto for a photosensitive viewer—an inferred, deliberately precautionary choice that can return zero titles.
- **Weak rule R-14:** subjective threat intensity only creates an inferred soft penalty; its weight is not clinically calibrated.
- **Weak rule R-04:** the under-17 MPA R policy does not model guardian accompaniment, so it is stricter than the rating system.

Further sources and provenance: [`../rules/Rule_sources.md`](../rules/Rule_sources.md), [`../rules/Rules_notes.md`](../rules/Rules_notes.md), and [`../dataset/DATASET_NOTES.md`](../dataset/DATASET_NOTES.md).
