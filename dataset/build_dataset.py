from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECORDS = json.loads((ROOT / 'source_records.json').read_text(encoding='utf-8'))
REQUIRED_KEYS = {'title','release_year','original_language','genres','runtime_minutes','short_premise',
                 'age_rating','rating_system','age_rating_source','bbfc_url','flashing_status',
                 'evidenced_tags','violence_intensity','threat_intensity','complexity_estimate',
                 'annotated_version'}
EVIDENCE_COLUMNS = ['movie_id','attribute_group','evidence_method','source_url','confidence','version_or_scope','limitations']
VALID_FLASH = {'confirmed_present','none','unknown'}
VALID_RATING = {
    'MPA': {'G', 'PG', 'PG-13', 'R', 'NC-17'},
    'BBFC': {'U', 'PG', '12A', '12', '15', '18', 'R18'},
    # of age-marked UA certificates. 
    'CBFC': {'U', 'UA', 'UA 7+', 'UA 13+', 'UA 16+', 'A', 'S'},
}

assert len(RECORDS) == 72, 'Expected 72 curated movie inputs'
assert len({(r['title'],r['release_year']) for r in RECORDS}) == 72, 'Duplicate films'

movies=[]
evidence=[]

def add(mid, group, method, url, confidence, scope, limitations):
    evidence.append({'movie_id':mid,'attribute_group':group,'evidence_method':method,
                     'source_url':url,'confidence':confidence,'version_or_scope':scope,
                     'limitations':limitations})

for i, r in enumerate(RECORDS, 1):
    mid = f'MV{i:03d}'
    assert REQUIRED_KEYS <= r.keys(), (mid, REQUIRED_KEYS-r.keys())
    assert r['flashing_status'] in VALID_FLASH, (mid,r['flashing_status'])
    if r['age_rating']!='unknown':
        assert r['rating_system'] in VALID_RATING, (mid, 'unknown rating system')
        assert r['age_rating'] in VALID_RATING[r['rating_system']], (mid,'age_rating')
        assert r['age_rating_source'].startswith('https://'), (mid, 'no rating source')
        assert r.get('age_rating_confidence', 'medium') in {'high','medium','low'}
    else:
        assert r['rating_system']=='unknown' and not r['age_rating_source'], (mid, 'unknown rating must not carry an invented source')
    assert isinstance(r['runtime_minutes'],int) and 10<=r['runtime_minutes']<=300
    assert r['bbfc_url'].startswith('https://')
    scope=r.get('annotated_version') or 'BBFC film overview; playback version not verified'
    tags=sorted(set(r['evidenced_tags']))
    flash=r['flashing_status']
    flash_conf=r.get('flashing_confidence','unknown')
    if flash=='confirmed_present' and flash_conf=='unknown':
        flash_conf='high' if not r.get('flashing_source') or 'bbfc.co.uk' in r['flashing_source'] else 'medium'
    if flash=='none':
        assert flash_conf=='low', (mid,'community no-flash cannot be a high-confidence claim')
        assert r.get('flashing_method')=='community_reported_no_flashes'

    def estimate(k):
        return None if r[k] in (None,'','unknown') else r[k]

    rating={'system':r['rating_system'],'value':r['age_rating']} if r['age_rating']!='unknown' else None

    rating_conf=(r.get('age_rating_confidence') or 'medium') if rating else 'unknown'
    movie={
        'movie_id':mid,
        'title':r['title'],
        'release_year':r['release_year'],
        'original_language':r['original_language'],
        'genres':list(dict.fromkeys(g.strip() for g in r['genres'].split(';') if g.strip())),
        'runtime_minutes':r['runtime_minutes'],
        'short_premise':r['short_premise'],
        'age_rating':rating,
        'sensitivity_tags':{
            'flashing_strobe_content':flash,
            'content_warnings':tags,
            'violence_intensity_estimate':estimate('violence_intensity'),
            'threat_intensity_estimate':estimate('threat_intensity'),
            'plot_complexity_estimate':estimate('complexity_estimate'),
            'accessibility':{'subtitles_available':'unknown','audio_description_available':'unknown'},
        },
        'annotation_confidence':{
            'age_rating':rating_conf,
            'flashing_strobe_content':flash_conf if flash != 'unknown' else 'unknown',
            'content_warnings':'medium' if tags else 'unknown',
            'subjective_estimates':'low' if any(estimate(k) for k in ['violence_intensity','threat_intensity','complexity_estimate']) else 'unknown',
            'accessibility':'unknown',
        },
    }
    movies.append(movie)

    metadata_caveat=('Title, genres and premise were curated and normalized from film information. '
                     'Premise/genre may be editorial; source scope not necessarily playback cut.')
    if r.get('notes'):
        metadata_caveat += ' '+r['notes']
    add(mid,'movie_metadata','manual curation of film metadata and editorial premise',r['bbfc_url'],
        'medium',scope,metadata_caveat)
    if r.get('runtime_source'):
        add(mid,'runtime_minutes','feature runtime from cited source',r['runtime_source'],
            'medium','Film feature (not bundled screening programme)',
            r.get('runtime_basis','Runtime may vary by version.'))
    if rating:
        add(mid,'age_rating',r.get('age_rating_method') or 'published rating displayed on cited film page',
            r['age_rating_source'],rating_conf,
            r.get('age_rating_scope') or f'{r["rating_system"]} certificate',
            (r.get('age_rating_notes') or
             'Country-specific certificate; cannot translate mechanically into other countries. Secondary aggregator where stated.'))
    if flash!='unknown':
        method=r.get('flashing_method') or ('explicit_BBFC_flashing_warning' if flash=='confirmed_present' else 'community_reported_no_flashes')
        fsrc=r.get('flashing_source') or r['bbfc_url']
        limits=r.get('flashing_notes') or 'Flashing evidence may apply to only certain cuts.'
        if flash=='none':
            limits+=' Community no votes are not a photosensitivity safety clearance; no tested flash-free cut has been certified.'
        elif method!='explicit_BBFC_flashing_warning':
            limits+=' Community positive reports are not independently clinically calibrated.'
        else:
            limits+=' A positive BBFC warning is for the cited classified work/version.'
        add(mid,'flashing_strobe_content',method,fsrc,flash_conf,scope,limits)
    if tags:
        add(mid,'content_warnings','manually mapped positive content descriptions from BBFC advice',r['bbfc_url'],
            'medium',scope,
            'Non-exhaustive manual tags; absent tag does not prove content absent; no independent scene-by-scene verification.')
    if movie['annotation_confidence']['subjective_estimates']!='unknown':
        add(mid,'subjective_estimates','curator interpretation of premise/film advice',r['bbfc_url'],
            'low','Subjective interpretation',
            'Unvalidated estimates, not clinical facts; use for optional soft ranking only.')

assert len(movies)==72
assert all((m['annotation_confidence']['age_rating'] in {'high','medium','low'})
           if m['age_rating'] else m['annotation_confidence']['age_rating']=='unknown'
           for m in movies)
assert all(m['sensitivity_tags']['plot_complexity_estimate'] in {'simple','moderate','dense'} for m in movies)
assert all(m['sensitivity_tags'][k] in {None,'very_mild','mild','moderate','strong'}
           for m in movies for k in ('violence_intensity_estimate','threat_intensity_estimate'))
ids={m['movie_id'] for m in movies}
assert ids=={e['movie_id'] for e in evidence}
assert all(m['sensitivity_tags']['accessibility']=={'subtitles_available':'unknown','audio_description_available':'unknown'} for m in movies)
assert all(m['annotation_confidence']['flashing_strobe_content']=='low' for m in movies if m['sensitivity_tags']['flashing_strobe_content']=='none')
assert all(e['source_url'].startswith('https://') for e in evidence)
assert all(any(e['movie_id']==m['movie_id'] and e['attribute_group']=='age_rating'
               and e['confidence']==m['annotation_confidence']['age_rating']
               for e in evidence) for m in movies if m['age_rating'] is not None)
assert all(not (e['attribute_group']=='age_rating' and e['confidence']=='high'
                and e['evidence_method']=='Indian_film_listing_certificate') for e in evidence)
(ROOT/'movies.json').write_text(json.dumps(movies,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (ROOT/'annotation_evidence.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=EVIDENCE_COLUMNS)
    writer.writeheader();writer.writerows(evidence)
print('Movies:',len(movies),'Evidence records:',len(evidence))
print('Ratings:',sum(m['age_rating'] is not None for m in movies))
print('Flashing:',dict(Counter(m['sensitivity_tags']['flashing_strobe_content'] for m in movies)))
