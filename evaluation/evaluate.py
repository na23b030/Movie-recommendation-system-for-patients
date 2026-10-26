from __future__ import annotations

import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recommender.engine import load_default, read_records, norm_genres


def genre_overlap(items):
    if len(items) < 2:
        return None
    genres = [norm_genres(i['genres']) for i in items]
    return mean(len(x & y) / len(x | y) if x | y else 0.0
                for i, x in enumerate(genres) for y in genres[i+1:])


def run():
    engine = load_default(ROOT)
    profiles = read_records(ROOT / 'dataset/patient_profiles.json')
    if len(profiles) != 16:
        raise AssertionError('Expected exactly 15 synthetic cases and 1 no-constraint control')
    rows, full_results, violations, checked = [], {}, [], 0
    diversity, baseline = [], []
    for p in profiles:
        pid = p['profile_id']
        result = engine.recommend(p, top_k=5, diversify=True)
        plain = engine.recommend(p, top_k=5, diversify=False)
        full_results[pid] = result
        banned = {x['movie_id'] for x in result['excluded_candidates']}
        for item in result['recommendations']:
            checked += 1
            if item['movie_id'] in banned or engine._hard_rule_ids(p, engine.by_id[item['movie_id']]):
                violations.append((pid, item['movie_id']))
        a, b = genre_overlap(result['recommendations']), genre_overlap(plain['recommendations'])
        if a is not None:
            diversity.append(a)
        if b is not None:
            baseline.append(b)
        rows.append((pid, result['returned_count'], result['audit']['eligible_count'],
                     result['audit']['excluded_count'], result['audit']['preference_matched_count']))
    if violations:
        raise AssertionError(f'HARD-RULE VIOLATIONS: {violations}')
    assert full_results['P016']['audit']['excluded_count'] == 0
    hard = sum(x['severity'] == 'hard_exclude' for x in engine.rule_definitions)
    sourced = sum(x['justification_type'] == 'sourced' for x in engine.rule_definitions)
    # Keep this generated summary concise and synchronized with the actual API.
    def title_list(pid):
        names = [item['title'] for item in full_results[pid]['recommendations']]
        return ', '.join(names[:3]) if names else 'None'

    with_diversity = mean(diversity) if diversity else None
    without_diversity = mean(baseline) if baseline else None
    summary_rows = [
        '| Measure | Result |', '|---|---:|',
        f'| Movies / profiles | {len(engine.movies)} / {len(profiles)} (15 synthetic + 1 control) |',
        f'| Recommendations returned | {checked} |',
        '| Hard-rule violations | **0 observed** |',
        f'| Profiles receiving 5 films | {sum(n == 5 for _,n,*_ in rows)}/16 |',
        f'| Profiles receiving none | {sum(n == 0 for _,n,*_ in rows)}/16 |',
        f'| Rules | {hard} hard, {len(engine.rule_definitions)-hard} soft |',
        f'| Evidence classification | {sourced} sourced, {len(engine.rule_definitions)-sourced} inferred |',
    ]
    content = [
        '# Evaluation Summary', '',
        'Run `python evaluation/evaluate.py` to reproduce these numbers from the included movies, rules and patient profiles.', '',
        '## Results', '', *summary_rows, '',
        'Every returned title was checked against the hard rules. Exclusions occur before ranking and are rechecked after diversity selection; soft penalties affect scores only.', '',
        '## Four manual inspections', '',
        f'- **P002 — child:** {title_list("P002")}. Child-appropriate genres remain after age exclusions.',
        f'- **P005 — concentration difficulty:** {title_list("P005")}. Dense plots can rank lower, but are not automatically banned.',
        f'- **P009 — adult thriller preference:** {title_list("P009")}. Adult selections differ from the child profile.',
        f'- **P014 — bereavement/self-harm avoidances:** {title_list("P014")}. {full_results["P014"]["audit"]["excluded_count"]} tagged titles excluded while remaining preferences still matter.', '',
        '## Variety and limitations', '',
        f'- Mean genre overlap **{with_diversity:.3f} with MMR vs. {without_diversity:.3f} without**; this measures variety, not accuracy or safety.' if with_diversity is not None and without_diversity is not None else '- Insufficient lists to compare diversity.',
        '- These profiles contain **genre preferences only**: this run does **not** test live pretrained semantic embeddings. Run `python -m recommender.semantic` separately, then validate meaningful free-text examples.',
        '- Age/content evidence is version-dependent and incomplete; untagged content is not proven absent. There is **no clinician review, real patient outcome or ground-truth recommendation label**.',
        '- **Weak rule R-02:** unknown flashing is treated as a veto for a photosensitive viewer—an inferred, deliberately precautionary choice that can return zero titles.',
        '- **Weak rule R-14:** subjective threat intensity only creates an inferred soft penalty; its weight is not clinically calibrated.',
        '- **Weak rule R-04:** the under-17 MPA R policy does not model guardian accompaniment, so it is stricter than the rating system.', '',
        'Further sources and provenance: [`../rules/Rule_sources.md`](../rules/Rule_sources.md), [`../rules/Rules_notes.md`](../rules/Rules_notes.md), and [`../dataset/DATASET_NOTES.md`](../dataset/DATASET_NOTES.md).', '',
    ]
    path = ROOT / 'evaluation' / 'EVALUATION.md'
    path.write_text('\n'.join(content), encoding='utf-8')
    print(f'Wrote {path}; evaluated {len(rows)} profiles, {checked} recommendations, zero hard-rule violations')
    return rows


if __name__ == '__main__':
    run()
