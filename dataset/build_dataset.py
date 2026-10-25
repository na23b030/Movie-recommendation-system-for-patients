import json,csv,collections,pathlib,zipfile
from datetime import date
out=pathlib.Path(__file__).resolve().parent
src=out/'source_records.json'
records=json.loads(src.read_text(encoding='utf-8'))
assert len(records)==72
fix_runtime={
 'Finding Nemo':(100,'https://www.rottentomatoes.com/m/finding_nemo', 'BBFC 107-minute 2013 cinema programme includes Partysaurus Rex short; feature-only runtime is 100 minutes (RT).'),
 'Encanto':(99,'https://www.rottentomatoes.com/m/encanto_2021', 'BBFC 109-minute cinema programme includes an accompanying short; feature-only runtime is 99 minutes (RT).'),
}
json_data=[]; ev=[]
cols=['movie_id','attribute_group','evidence_method','source_url','confidence','version_or_scope','limitations']

def add(movie_id,group,method,source,conf,version='',notes=''):
 ev.append(dict(movie_id=movie_id,attribute_group=group,evidence_method=method,source_url=source,
               confidence=conf,version_or_scope=version,limitations=notes))

for i,a in enumerate(records,1):
 mid=f'MV{i:03}'
 runtime=a['runtime_minutes']
 runtime_source=a['bbfc_url']
 extra=''
 if a['title'] in fix_runtime:
  runtime,runtime_source,extra=fix_runtime[a['title']]
 version=a['annotated_version']
 if version=='BBFC film overview':
  version='Film-level BBFC overview; exact playback cut not matched'
 # source tag is manually curated, not independently verified scene-by-scene; lower confidence accordingly.
 tags=sorted(set(a['evidenced_tags']))
 movie={
  'movie_id':mid,
  'title':a['title'],
  'release_year':a['release_year'],
  'original_language':a['original_language'],
  'genres':list(dict.fromkeys(a['genres'].split(';'))),
  'runtime_minutes':runtime,
  'short_premise':a['short_premise'],
  'age_rating': {'system':a['rating_system'],'value':a['age_rating']} if a['age_rating']!='unknown' else None,
  'sensitivity_tags': {
     'flashing_strobe_content':a['flashing_status'],
     'content_warnings':tags,
     'violence_intensity_estimate':None if a['violence_intensity']=='unknown' else a['violence_intensity'],
     'threat_intensity_estimate':None if a['threat_intensity']=='unknown' else a['threat_intensity'],
     'plot_complexity_estimate':None if a['complexity_estimate']=='unknown' else a['complexity_estimate'],
     # Availability is not verified for any provider, region, language or release.
     # "unknown" is deliberately distinct from False (verified unavailable).
     'accessibility': {
        'subtitles_available': 'unknown',
        'audio_description_available': 'unknown'
     }
  }
 }
 json_data.append(movie)
 notes='Film facts are compiled from the referenced film record; synopsis is a short editorial paraphrase. Runtime is approximate and may differ by cut.'
 if a['title'] in fix_runtime:
  notes += ' '+extra
 if a['notes']:
  notes+=' '+a['notes']
 add(mid,'movie_metadata','BBFC film record + curator-normalized genres and premise',a['bbfc_url'],'medium',version,notes)
 if runtime_source!=a['bbfc_url']:
  add(mid,'runtime_minutes','published feature-only running time',runtime_source,'high_for_listed_version','Feature only',extra)
 if a['age_rating']!='unknown':
  add(mid,'age_rating','published classification on cited film page',a['age_rating_source'],'high',
      f'{a["rating_system"]} rating system',
      'Rating belongs to this classification system; different systems must not be treated as interchangeable.')
 if a['flashing_status']=='confirmed_present':
  add(mid,'flashing_strobe_content','explicit BBFC flashing/flickering warning',a['bbfc_url'],'high_for_listed_classification',version,
      'Warning applies to the cited classified release(s), not proof of safety/absence in other cuts.')
 if tags:
  add(mid,'content_warnings','curator tag mapping from positive BBFC content advice',a['bbfc_url'],'medium',version,
      'Positive mentions only; tag absence does not prove absence of corresponding content. Mapping is not a scene-by-scene audit.')
 if movie['sensitivity_tags']['plot_complexity_estimate'] or movie['sensitivity_tags']['violence_intensity_estimate'] or movie['sensitivity_tags']['threat_intensity_estimate']:
  add(mid,'subjective_estimates','plot complexity from short premise; intensity inferred from content advice',a['bbfc_url'],'low','Curator interpretation',
      'Unvalidated editorial estimates, not clinical measurements; must not support mandatory exclusions.')

# Lightweight confidence flags used by the recommendation engine. The detailed
# evidence (methods, links, release scopes, caveats) remains in annotation_evidence.csv.
# These are *annotation-evidence levels*, NOT safety probabilities or ML predictions.
evidence_by_movie=collections.defaultdict(dict)
for evidence_row in ev:
 evidence_by_movie[evidence_row['movie_id']][evidence_row['attribute_group']]=evidence_row['confidence']
for movie in json_data:
 levels=evidence_by_movie[movie['movie_id']]
 sensitivity=movie['sensitivity_tags']
 movie['annotation_confidence']={
  'age_rating': 'high' if movie['age_rating'] is not None and 'age_rating' in levels else 'unknown',
  'flashing_strobe_content': 'high' if sensitivity['flashing_strobe_content']=='confirmed_present' and 'flashing_strobe_content' in levels else 'unknown',
  'content_warnings': 'medium' if sensitivity['content_warnings'] and 'content_warnings' in levels else 'unknown',
  'subjective_estimates': 'low' if 'subjective_estimates' in levels else 'unknown',
  'accessibility': 'unknown'
 }

assert {x['movie_id'] for x in json_data}=={x['movie_id'] for x in ev}
assert len(json_data)==72 and len({(x['title'],x['release_year']) for x in json_data})==72
assert all(x['sensitivity_tags']['flashing_strobe_content'] in {'unknown','confirmed_present'} for x in json_data)
assert all((m['age_rating'] is None) or (m['age_rating']['value'] in {'G','PG','PG-13','R','NC-17'} and m['age_rating']['system'] in {'MPA','BBFC'}) for m in json_data)
assert all(m['runtime_minutes']>0 for m in json_data)
assert all(set(m['annotation_confidence'])=={'age_rating','flashing_strobe_content','content_warnings','subjective_estimates','accessibility'} for m in json_data)
assert all(m['sensitivity_tags']['accessibility']=={'subtitles_available':'unknown','audio_description_available':'unknown'} and m['annotation_confidence']['accessibility']=='unknown' for m in json_data)
assert all(m['annotation_confidence']['flashing_strobe_content']=='unknown' if m['sensitivity_tags']['flashing_strobe_content']=='unknown' else m['annotation_confidence']['flashing_strobe_content']=='high' for m in json_data)
for m in json_data:
 es=[z for z in ev if z['movie_id']==m['movie_id']]
 types={z['attribute_group'] for z in es}
 assert 'movie_metadata' in types and 'subjective_estimates' in types
 assert ('flashing_strobe_content' in types)==(m['sensitivity_tags']['flashing_strobe_content']=='confirmed_present')
 assert ('age_rating' in types)==(m['age_rating'] is not None)
 assert ('content_warnings' in types)==bool(m['sensitivity_tags']['content_warnings'])
 assert all(z['source_url'].startswith('https://') for z in es)

j=out/'movies.json';e=out/'annotation_evidence.csv'
j.write_text(json.dumps(json_data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with e.open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(ev)
print('FILES',j,e)
print('SIZE',j.stat().st_size,e.stat().st_size)
print('COUNT movie',len(json_data),'evidence',len(ev),'kinds',collections.Counter(x['attribute_group'] for x in ev))
print('flashing',collections.Counter(x['sensitivity_tags']['flashing_strobe_content'] for x in json_data))
print('ratings',sum(x['age_rating'] is not None for x in json_data))
print('tag count',sum(len(x['sensitivity_tags']['content_warnings']) for x in json_data))
print('EXAMPLE',json.dumps(json_data[0],indent=2))
for x in json_data:
 if x['title'] in fix_runtime:print('FIX',x['title'],x['runtime_minutes'])
