#!/usr/bin/env python3
"""Build the Deep Answer static question bank from Wikidata."""
from __future__ import annotations
import hashlib, json, math, random, re, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import requests

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = ROOT / "source" / "plan.json"
DATA_DIR = ROOT / "data"
ANSWERS_DIR = DATA_DIR / "answers"
CACHE_DIR = ROOT / ".build_cache"
WDQS = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "DeepAnswerGame/1.0 (static trivia database builder)"}
SCORE_BUCKETS = ((0.20,10),(0.40,20),(0.60,40),(0.75,60),(0.90,80),(1.01,100))
Q_HUMAN="Q5"; Q_FILM="Q11424"; Q_ALBUM="Q482994"; Q_SONG="Q7366"; Q_COUNTRY="Q6256"; Q_RIVER="Q4022"; Q_MOUNTAIN="Q8502"; Q_SCIENTIST="Q901"; Q_SPORTS_TEAM="Q12973014"; Q_VIDEO_GAME="Q7889"; Q_SOFTWARE="Q7397"; Q_TAXON="Q16521"; Q_SPECIES_RANK="Q7432"; Q_FAMILY_RANK="Q35409"; Q_ANIMALIA="Q729"
DATA_DIR.mkdir(exist_ok=True); ANSWERS_DIR.mkdir(exist_ok=True); CACHE_DIR.mkdir(exist_ok=True)
PLAN=json.loads(PLAN_PATH.read_text(encoding="utf-8")); MIN_ANSWERS=int(PLAN["minimum_answers"]); MAX_ANSWERS=int(PLAN["maximum_answers"])

def cached_path(value): return CACHE_DIR / f"wdqs-{hashlib.sha256(value.encode()).hexdigest()}.json"
def sparql(query):
    path=cached_path(query)
    if path.exists(): return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(8):
        try:
            r=requests.get(WDQS,params={"query":query,"format":"json"},headers=HEADERS,timeout=120)
            if r.status_code in {429,500,502,503,504}:
                time.sleep(min(60,5*(attempt+1))); continue
            r.raise_for_status(); payload=r.json(); path.write_text(json.dumps(payload),encoding="utf-8"); time.sleep(.35); return payload
        except Exception:
            if attempt==7: raise
            time.sleep(min(60,5*(attempt+1)))
    raise RuntimeError("Wikidata query failed repeatedly")

def normalize(text):
    text=text.casefold().strip().replace("’","").replace("'","").replace("&"," and ")
    text=re.sub(r"[-–—:;/,.!?()\[\]{}]+"," ",text); text=re.sub(r"^(the|a|an)\s+","",text)
    return re.sub(r"\s+"," ",text).strip()
def automatic_aliases(name):
    out=[]; lower=name.casefold()
    if lower.startswith("the "): out.append(name[4:])
    elif lower.startswith("an "): out.append(name[3:])
    elif lower.startswith("a "): out.append(name[2:])
    if " & " in name: out.append(name.replace(" & "," and "))
    if re.search(r"\band\b",name,flags=re.I): out.append(re.sub(r"\band\b","&",name,flags=re.I))
    canonical=normalize(name); seen=set(); result=[]
    for alias in out:
        key=normalize(alias)
        if key and key!=canonical and key not in seen: seen.add(key); result.append(alias)
    return result

def parse_subjects(payload):
    result=[]; seen=set()
    for row in payload["results"]["bindings"]:
        if "subject" not in row or "subjectLabel" not in row: continue
        qid=row["subject"]["value"].rsplit("/",1)[-1]; name=row["subjectLabel"]["value"].strip()
        if qid in seen or not qid.startswith("Q") or re.fullmatch(r"Q\d+",name): continue
        seen.add(qid); result.append({"qid":qid,"name":name})
    return result

def parse_answers_by_subject(payload):
    buckets={}
    for row in payload["results"]["bindings"]:
        if not {"subject","answer","answerLabel"}.issubset(row): continue
        subject=row["subject"]["value"].rsplit("/",1)[-1]; qid=row["answer"]["value"].rsplit("/",1)[-1]; name=row["answerLabel"]["value"].strip()
        if not qid.startswith("Q") or re.fullmatch(r"Q\d+",name): continue
        popularity=0
        if "sitelinks" in row:
            try: popularity=int(float(row["sitelinks"]["value"]))
            except: pass
        answer=buckets.setdefault(subject,{}).setdefault(qid,{"qid":qid,"name":name,"aliases":automatic_aliases(name),"popularity":popularity})
        answer["popularity"]=max(answer["popularity"],popularity)
    output={}
    for subject,by_qid in buckets.items():
        seen=set(); answers=[]
        for answer in sorted(by_qid.values(),key=lambda x:(-x["popularity"],x["name"].casefold())):
            key=normalize(answer["name"])
            if not key or key in seen: continue
            seen.add(key); answers.append(answer)
        output[subject]=answers
    return output

def score_answers(answers):
    n=len(answers)
    for i,a in enumerate(answers):
        p=i/max(n-1,1)
        for threshold,score in SCORE_BUCKETS:
            if p<threshold: a["score"]=score; break
    return answers

def discover(query): return parse_subjects(sparql(query))
def discover_from_relation(pattern,limit):
    return discover(f'''SELECT DISTINCT ?subject ?subjectLabel ?subjectLinks WHERE {{ {pattern} ?subject wikibase:sitelinks ?subjectLinks . SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} ORDER BY DESC(?subjectLinks) LIMIT {limit}''')
def discover_countries(limit):
    return discover(f'''SELECT DISTINCT ?subject ?subjectLabel ?subjectLinks WHERE {{ ?subject wdt:P31/wdt:P279* wd:{Q_COUNTRY}; wikibase:sitelinks ?subjectLinks . SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} ORDER BY DESC(?subjectLinks) LIMIT {limit}''')
def discover_animal_families(limit):
    return discover(f'''SELECT DISTINCT ?subject ?subjectLabel ?subjectLinks WHERE {{ ?subject wdt:P31 wd:{Q_TAXON}; wdt:P105 wd:{Q_FAMILY_RANK}; wdt:P171+ wd:{Q_ANIMALIA}; wikibase:sitelinks ?subjectLinks . SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} ORDER BY DESC(?subjectLinks) LIMIT {limit}''')
def discover_science_fields(limit):
    return discover(f'''SELECT DISTINCT ?subject ?subjectLabel ?subjectLinks WHERE {{ ?person wdt:P31 wd:{Q_HUMAN}; wdt:P106/wdt:P279* wd:{Q_SCIENTIST}; wdt:P101 ?subject . ?subject wikibase:sitelinks ?subjectLinks . FILTER(?subjectLinks >= 3) SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} ORDER BY DESC(?subjectLinks) LIMIT {limit}''')
def discover_sports_teams(limit):
    return discover(f'''SELECT DISTINCT ?subject ?subjectLabel ?subjectLinks WHERE {{ ?player wdt:P31 wd:{Q_HUMAN}; wdt:P54 ?subject . ?subject wdt:P31/wdt:P279* wd:{Q_SPORTS_TEAM}; wikibase:sitelinks ?subjectLinks . SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} ORDER BY DESC(?subjectLinks) LIMIT {limit}''')

def values(subjects): return " ".join(f"wd:{x['qid']}" for x in subjects)
def answer_query(t,subjects):
    patterns={
      "actor_movies":f"?answer wdt:P161 ?subject; wdt:P31/wdt:P279* wd:{Q_FILM} .",
      "director_movies":f"?answer wdt:P57 ?subject; wdt:P31/wdt:P279* wd:{Q_FILM} .",
      "movie_cast":f"?subject wdt:P161 ?answer . ?answer wdt:P31 wd:{Q_HUMAN} .",
      "artist_songs":f"?answer wdt:P175 ?subject; wdt:P31/wdt:P279* wd:{Q_SONG} .",
      "artist_albums":f"?answer wdt:P175 ?subject; wdt:P31/wdt:P279* wd:{Q_ALBUM} .",
      "country_rivers":f"?answer wdt:P17 ?subject; wdt:P31/wdt:P279* wd:{Q_RIVER} .",
      "country_mountains":f"?answer wdt:P17 ?subject; wdt:P31/wdt:P279* wd:{Q_MOUNTAIN} .",
      "country_subdivisions":"?subject wdt:P150 ?answer .",
      "animal_family_species":f"?answer wdt:P31 wd:{Q_TAXON}; wdt:P105 wd:{Q_SPECIES_RANK}; wdt:P171+ ?subject .",
      "science_field_scientists":f"?answer wdt:P31 wd:{Q_HUMAN}; wdt:P106/wdt:P279* wd:{Q_SCIENTIST}; wdt:P101 ?subject .",
      "sports_team_players":f"?answer wdt:P31 wd:{Q_HUMAN}; wdt:P54 ?subject .",
      "author_works":"?answer wdt:P50 ?subject .",
      "game_developer_titles":f"?answer wdt:P178 ?subject; wdt:P31/wdt:P279* wd:{Q_VIDEO_GAME} .",
      "software_developer_products":f"?answer wdt:P178 ?subject; wdt:P31/wdt:P279* wd:{Q_SOFTWARE} .",
      "historical_heads_of_state":f"?subject p:P35 ?statement . ?statement ps:P35 ?answer . ?answer wdt:P31 wd:{Q_HUMAN} .",
      "historical_heads_of_government":f"?subject p:P6 ?statement . ?statement ps:P6 ?answer . ?answer wdt:P31 wd:{Q_HUMAN} ."}
    return f'''SELECT DISTINCT ?subject ?answer ?answerLabel ?sitelinks WHERE {{ VALUES ?subject {{ {values(subjects)} }} {patterns[t]} OPTIONAL {{ ?answer wikibase:sitelinks ?sitelinks . }} SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}'''

DISCOVERERS={
 "actor_movies":lambda n:discover_from_relation(f"?answer wdt:P161 ?subject; wdt:P31/wdt:P279* wd:{Q_FILM} .",n),
 "director_movies":lambda n:discover_from_relation(f"?answer wdt:P57 ?subject; wdt:P31/wdt:P279* wd:{Q_FILM} .",n),
 "movie_cast":lambda n:discover_from_relation(f"?subject wdt:P31/wdt:P279* wd:{Q_FILM}; wdt:P161 ?answer .",n),
 "artist_songs":lambda n:discover_from_relation(f"?answer wdt:P175 ?subject; wdt:P31/wdt:P279* wd:{Q_SONG} .",n),
 "artist_albums":lambda n:discover_from_relation(f"?answer wdt:P175 ?subject; wdt:P31/wdt:P279* wd:{Q_ALBUM} .",n),
 "country_rivers":discover_countries,"country_mountains":discover_countries,"country_subdivisions":discover_countries,
 "animal_family_species":discover_animal_families,"science_field_scientists":discover_science_fields,"sports_team_players":discover_sports_teams,
 "author_works":lambda n:discover_from_relation("?answer wdt:P50 ?subject .",n),
 "game_developer_titles":lambda n:discover_from_relation(f"?answer wdt:P178 ?subject; wdt:P31/wdt:P279* wd:{Q_VIDEO_GAME} .",n),
 "software_developer_products":lambda n:discover_from_relation(f"?answer wdt:P178 ?subject; wdt:P31/wdt:P279* wd:{Q_SOFTWARE} .",n),
 "historical_heads_of_state":discover_countries,"historical_heads_of_government":discover_countries}
TEMPLATES={
 "actor_movies":("movies","Name a movie {name} acted in"),"director_movies":("movies","Name a movie directed by {name}"),"movie_cast":("movies","Name an actor in {name}"),
 "artist_songs":("music","Name a song by {name}"),"artist_albums":("music","Name an album by {name}"),
 "country_rivers":("geography","Name a river in {name}"),"country_mountains":("geography","Name a mountain in {name}"),"country_subdivisions":("geography","Name a first-level administrative subdivision of {name}"),
 "animal_family_species":("animals","Name an animal species in the family {name}"),"science_field_scientists":("science","Name a scientist whose field of work includes {name}"),"sports_team_players":("sports","Name an athlete who has played for {name}"),
 "author_works":("literature","Name a work written by {name}"),"game_developer_titles":("games","Name a video game developed by {name}"),"software_developer_products":("technology","Name software developed by {name}"),
 "historical_heads_of_state":("history","Name a head of state of {name}"),"historical_heads_of_government":("history","Name a head of government of {name}")}
OVERSAMPLE={k:3.0 for k in TEMPLATES}; OVERSAMPLE.update({"animal_family_species":3.5,"science_field_scientists":3.5,"software_developer_products":3.5})
BATCH_SIZE={"animal_family_species":5,"science_field_scientists":8,"sports_team_players":10,"country_rivers":12,"country_mountains":12,"historical_heads_of_state":12,"historical_heads_of_government":12}

def stable_id(t,qid): return f"{t}__{qid.casefold()}"
def save_answer_file(qid,answers):
    (ANSWERS_DIR/f"{qid}.json").write_text(json.dumps({"question_id":qid,"source":"Wikidata","answers":answers},indent=2,ensure_ascii=False),encoding="utf-8")
def build_type(t,target,used):
    candidates=DISCOVERERS[t](max(target+20,math.ceil(target*OVERSAMPLE[t]))); accepted=[]; batch_size=BATCH_SIZE.get(t,20)
    for start in range(0,len(candidates),batch_size):
        batch=candidates[start:start+batch_size]; by_subject=parse_answers_by_subject(sparql(answer_query(t,batch)))
        for subject in batch:
            key=f"{t}:{subject['qid']}"; answers=by_subject.get(subject["qid"],[])
            if key in used or not (MIN_ANSWERS<=len(answers)<=MAX_ANSWERS): continue
            accepted.append({"subject":subject,"answers":score_answers(answers)}); used.add(key)
            print(f"{t}: {len(accepted)}/{target} {subject['name']} ({len(answers)} answers)")
            if len(accepted)>=target: break
        if len(accepted)>=target: break
    return accepted

def materialize(t,item):
    subject=item["subject"]; qid=stable_id(t,subject["qid"]); category,template=TEMPLATES[t]; save_answer_file(qid,item["answers"])
    return {"id":qid,"question":template.format(name=subject["name"]),"category":category,"type":t,"subject":subject,"answer_count":len(item["answers"]),"answer_file":f"data/answers/{qid}.json","source":"Wikidata"}

def main():
    planned=sum(int(v) for v in PLAN["types"].values())
    if planned!=int(PLAN["target_questions"]): raise ValueError(f"plan totals {planned}")
    for path in ANSWERS_DIR.glob("*.json"): path.unlink()
    used=set(); questions=[]; shortages=[]
    for t,target_raw in PLAN["types"].items():
        target=int(target_raw); print(f"\n### {t} target {target}"); accepted=build_type(t,target,used); questions.extend(materialize(t,x) for x in accepted)
        if len(accepted)<target: shortages.append((t,target-len(accepted)))
    random.Random(42).shuffle(questions)
    metadata={"version":1,"built_at":datetime.now(timezone.utc).isoformat(),"source":"Wikidata","question_count":len(questions),"questions":questions}
    (DATA_DIR/"bank.json").write_text(json.dumps(metadata,indent=2,ensure_ascii=False),encoding="utf-8")
    (DATA_DIR/"questions.json").write_text(json.dumps(questions,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"Built {len(questions)} questions and {sum(q['answer_count'] for q in questions)} answer records")
    if shortages:
        for t,missing in shortages: print(f"SHORTAGE {t}: {missing}")
        raise SystemExit(2)

if __name__=="__main__": main()
