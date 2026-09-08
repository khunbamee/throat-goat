#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, math, random, re, time
from datetime import datetime, timezone
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parent.parent
PLAN=json.loads((ROOT/'source'/'plan.json').read_text(encoding='utf-8'))
DATA=ROOT/'data'; ANSWERS=DATA/'answers'; CACHE=ROOT/'.build_cache'
for d in (DATA,ANSWERS,CACHE): d.mkdir(exist_ok=True)
MIN=int(PLAN['minimum_answers']); MAX=int(PLAN['maximum_answers'])
WDQS='https://query.wikidata.org/sparql'; HEADERS={'User-Agent':'DeepAnswerGame/1.0 educational trivia builder'}
SCORES=((.20,10),(.40,20),(.60,40),(.75,60),(.90,80),(1.01,100))
Q={'human':'Q5','film':'Q11424','album':'Q482994','song':'Q7366','country':'Q6256','river':'Q4022','mountain':'Q8502','game':'Q7889','software':'Q7397','taxon':'Q16521','species':'Q7432','family':'Q35409','animalia':'Q729'}

def sparql(query):
    path=CACHE/(hashlib.sha256(query.encode()).hexdigest()+'.json')
    if path.exists(): return json.loads(path.read_text(encoding='utf-8'))
    last=None
    for attempt in range(5):
        try:
            r=requests.get(WDQS,params={'query':query,'format':'json'},headers=HEADERS,timeout=60)
            if r.status_code in {429,500,502,503,504}: raise RuntimeError(f'HTTP {r.status_code}')
            r.raise_for_status(); data=r.json(); path.write_text(json.dumps(data),encoding='utf-8'); time.sleep(.2); return data
        except Exception as e:
            last=e; wait=min(20,2*(attempt+1)); print(f'WDQS retry: {e}; {wait}s',flush=True); time.sleep(wait)
    raise RuntimeError(f'Wikidata failed: {last}')

def norm(s):
    s=s.casefold().strip().replace('’','').replace("'",'').replace('&',' and ')
    s=re.sub(r'[-–—:;/,.!?()\[\]{}]+',' ',s); s=re.sub(r'^(the|a|an)\s+','',s)
    return re.sub(r'\s+',' ',s).strip()
def alias_list(name):
    out=[]; low=name.casefold()
    if low.startswith('the '): out.append(name[4:])
    elif low.startswith('an '): out.append(name[3:])
    elif low.startswith('a '): out.append(name[2:])
    return out

def parse_subjects(data):
    out=[]; seen=set()
    for row in data['results']['bindings']:
        if 'subjectLabel' not in row: continue
        qid=row['subject']['value'].rsplit('/',1)[-1]; name=row['subjectLabel']['value'].strip()
        if qid in seen or re.fullmatch(r'Q\d+',name): continue
        seen.add(qid); out.append({'qid':qid,'name':name})
    return out

def parse_answers(data):
    buckets={}
    for row in data['results']['bindings']:
        if not {'subject','answer','answerLabel'}<=row.keys(): continue
        sq=row['subject']['value'].rsplit('/',1)[-1]; aq=row['answer']['value'].rsplit('/',1)[-1]; name=row['answerLabel']['value'].strip()
        if re.fullmatch(r'Q\d+',name): continue
        try: pop=int(float(row.get('sitelinks',{}).get('value',0)))
        except: pop=0
        buckets.setdefault(sq,{})[aq]={'qid':aq,'name':name,'aliases':alias_list(name),'popularity':pop}
    result={}
    for sq,items in buckets.items():
        vals=[]; seen=set()
        for a in sorted(items.values(),key=lambda x:(-x['popularity'],x['name'].casefold())):
            k=norm(a['name'])
            if k and k not in seen: seen.add(k); vals.append(a)
        n=len(vals)
        for i,a in enumerate(vals):
            pct=i/max(n-1,1); a['score']=next(score for cut,score in SCORES if pct<cut)
        result[sq]=vals
    return result

def discover(pattern,limit,min_links=3):
    q=f'''SELECT DISTINCT ?subject ?subjectLabel WHERE {{ {pattern} ?subject wikibase:sitelinks ?links . FILTER(?links >= {min_links}) SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} LIMIT {limit}'''
    return parse_subjects(sparql(q))
def countries(limit): return discover(f'?subject wdt:P31 wd:{Q["country"]} .',limit,1)
def animals(limit): return discover(f'?subject wdt:P31 wd:{Q["taxon"]}; wdt:P105 wd:{Q["family"]}; wdt:P171+ wd:{Q["animalia"]} .',limit,1)
def science(limit): return discover(f'?person wdt:P31 wd:{Q["human"]}; wdt:P101 ?subject .',limit,3)
def sports(limit): return discover('?person wdt:P54 ?subject .',limit,3)
def vals(batch): return ' '.join('wd:'+x['qid'] for x in batch)

def answer_query(t,batch):
    P={'actor_movies':f'?answer wdt:P161 ?subject; wdt:P31/wdt:P279* wd:{Q["film"]} .','director_movies':f'?answer wdt:P57 ?subject; wdt:P31/wdt:P279* wd:{Q["film"]} .','movie_cast':f'?subject wdt:P161 ?answer . ?answer wdt:P31 wd:{Q["human"]} .','artist_songs':f'?answer wdt:P175 ?subject; wdt:P31/wdt:P279* wd:{Q["song"]} .','artist_albums':f'?answer wdt:P175 ?subject; wdt:P31/wdt:P279* wd:{Q["album"]} .','country_rivers':f'?answer wdt:P17 ?subject; wdt:P31/wdt:P279* wd:{Q["river"]} .','country_mountains':f'?answer wdt:P17 ?subject; wdt:P31/wdt:P279* wd:{Q["mountain"]} .','country_subdivisions':'?subject wdt:P150 ?answer .','animal_family_species':f'?answer wdt:P31 wd:{Q["taxon"]}; wdt:P105 wd:{Q["species"]}; wdt:P171+ ?subject .','science_field_scientists':f'?answer wdt:P31 wd:{Q["human"]}; wdt:P101 ?subject .','sports_team_players':f'?answer wdt:P31 wd:{Q["human"]}; wdt:P54 ?subject .','author_works':'?answer wdt:P50 ?subject .','game_developer_titles':f'?answer wdt:P178 ?subject; wdt:P31/wdt:P279* wd:{Q["game"]} .','software_developer_products':f'?answer wdt:P178 ?subject; wdt:P31/wdt:P279* wd:{Q["software"]} .','historical_heads_of_state':f'?subject p:P35 ?st . ?st ps:P35 ?answer . ?answer wdt:P31 wd:{Q["human"]} .','historical_heads_of_government':f'?subject p:P6 ?st . ?st ps:P6 ?answer . ?answer wdt:P31 wd:{Q["human"]} .'}
    return f'''SELECT DISTINCT ?subject ?answer ?answerLabel ?sitelinks WHERE {{ VALUES ?subject {{ {vals(batch)} }} {P[t]} OPTIONAL {{ ?answer wikibase:sitelinks ?sitelinks . }} SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}'''

DISC={'actor_movies':lambda n:discover('?work wdt:P161 ?subject .',n,8),'director_movies':lambda n:discover('?work wdt:P57 ?subject .',n,8),'movie_cast':lambda n:discover(f'?subject wdt:P31 wd:{Q["film"]}; wdt:P161 ?cast .',n,8),'artist_songs':lambda n:discover('?work wdt:P175 ?subject .',n,8),'artist_albums':lambda n:discover('?work wdt:P175 ?subject .',n,8),'country_rivers':countries,'country_mountains':countries,'country_subdivisions':countries,'animal_family_species':animals,'science_field_scientists':science,'sports_team_players':sports,'author_works':lambda n:discover('?work wdt:P50 ?subject .',n,6),'game_developer_titles':lambda n:discover('?work wdt:P178 ?subject .',n,4),'software_developer_products':lambda n:discover('?work wdt:P178 ?subject .',n,4),'historical_heads_of_state':countries,'historical_heads_of_government':countries}
T={'actor_movies':('movies','Name a movie {name} acted in'),'director_movies':('movies','Name a movie directed by {name}'),'movie_cast':('movies','Name an actor in {name}'),'artist_songs':('music','Name a song by {name}'),'artist_albums':('music','Name an album by {name}'),'country_rivers':('geography','Name a river in {name}'),'country_mountains':('geography','Name a mountain in {name}'),'country_subdivisions':('geography','Name a first-level administrative subdivision of {name}'),'animal_family_species':('animals','Name an animal species in the family {name}'),'science_field_scientists':('science','Name a scientist whose field of work includes {name}'),'sports_team_players':('sports','Name an athlete who has played for {name}'),'author_works':('literature','Name a work written by {name}'),'game_developer_titles':('games','Name a video game developed by {name}'),'software_developer_products':('technology','Name software developed by {name}'),'historical_heads_of_state':('history','Name a head of state of {name}'),'historical_heads_of_government':('history','Name a head of government of {name}')}
OVER={k:3 for k in T}; OVER.update({'animal_family_species':4,'science_field_scientists':4,'software_developer_products':4})
BATCH={'animal_family_species':5,'science_field_scientists':8,'sports_team_players':10,'country_rivers':12,'country_mountains':12,'historical_heads_of_state':12,'historical_heads_of_government':12}

def build_type(t,target):
    try: cand=DISC[t](max(target+20,math.ceil(target*OVER[t])))
    except Exception as e: print(f'DISCOVERY FAILED {t}: {e}',flush=True); return []
    accepted=[]; bs=BATCH.get(t,20)
    for start in range(0,len(cand),bs):
        batch=cand[start:start+bs]
        try: by=parse_answers(sparql(answer_query(t,batch)))
        except Exception as e: print(f'batch skipped {t}: {e}',flush=True); continue
        for s in batch:
            a=by.get(s['qid'],[])
            if MIN<=len(a)<=MAX:
                accepted.append((s,a)); print(f'{t}: {len(accepted)}/{target} {s["name"]} ({len(a)})',flush=True)
                if len(accepted)>=target: return accepted
    return accepted

def main():
    if sum(PLAN['types'].values())!=PLAN['target_questions']: raise ValueError('plan does not total target')
    for f in ANSWERS.glob('*.json'): f.unlink()
    questions=[]; shortages=[]
    for t,target in PLAN['types'].items():
        print(f'### {t} target {target}',flush=True); got=build_type(t,int(target))
        if len(got)<target: shortages.append((t,target-len(got)))
        cat,template=T[t]
        for s,a in got:
            qid=f'{t}__{s["qid"].casefold()}'
            (ANSWERS/f'{qid}.json').write_text(json.dumps({'question_id':qid,'source':'Wikidata','answers':a},indent=2,ensure_ascii=False),encoding='utf-8')
            questions.append({'id':qid,'question':template.format(name=s['name']),'category':cat,'type':t,'subject':s,'answer_count':len(a),'answer_file':f'data/answers/{qid}.json','source':'Wikidata'})
    random.Random(42).shuffle(questions)
    (DATA/'questions.json').write_text(json.dumps(questions,indent=2,ensure_ascii=False),encoding='utf-8')
    (DATA/'bank.json').write_text(json.dumps({'version':1,'built_at':datetime.now(timezone.utc).isoformat(),'question_count':len(questions),'questions':questions},indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'Built {len(questions)} questions',flush=True)
    if shortages:
        for t,n in shortages: print(f'SHORTAGE {t}: {n}',flush=True)
        raise SystemExit(2)
if __name__=='__main__': main()
