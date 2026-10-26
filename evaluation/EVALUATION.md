# Evaluation Summary

Tested **72 movies** with **15 synthetic patient profiles and one no-constraint control** using `python evaluation/evaluate.py`.

## Results

| Measure | Result |
|---|---:|
| Recommendations returned | **60** |
| Hard-rule violations observed | **0** |
| Profiles with five recommendations | **12/16** |
| Profiles with no recommendations | **4/16** |
| Rules | **9 hard, 7 soft** |
| Rule provenance | **3 sourced, 13 inferred** |

Hard exclusions are applied before ranking and checked again after diversity reranking. Soft penalties change the rank but **never override a hard exclusion**.

## Four manual checks

- **P002 (child):** *Toy Story* and *Ratatouille* remained relevant after age-related exclusions.
- **P005 (concentration difficulty):** Complex movies were penalized rather than automatically banned.
- **P009 (adult thriller preference):** Recommendations differed clearly from the child's list.
- **P014 (avoids bereavement/self-harm):** 22 tagged movies were excluded while preferences still influenced results.

Diversity reranking reduced average genre overlap from **0.646 to 0.597**; this measures variety, not safety or recommendation accuracy.

## Limitations

These tests used **genre preferences only**, so they **do not verify live semantic-embedding inference**. Content warnings and accessibility information are incomplete; unknown does not mean safe. Most thresholds are inferred, and no real patient outcomes or clinician review were available. Some profiles appropriately received no recommendations.

**Reproduce:** `python evaluation/evaluate.py`  
**Semantic model smoke test:** `python -m recommender.semantic`  
**Evidence and rule details:** [`../dataset/DATASET_NOTES.md`](../dataset/DATASET_NOTES.md) and [`../rules/rules.json`](../rules/rules.json).
