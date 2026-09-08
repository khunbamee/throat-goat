#!/usr/bin/env python3
import json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
PLAN=json.loads((ROOT/"source"/"plan.json").read_text(encoding="utf-8"))
QUESTIONS=ROOT/"data"/"questions.json"
ALLOWED={10,20,40,60,80,100}

def normalize(text):
    text=text.casefold().strip().replace("’","").replace("'","").replace("&"," and ")
    text=re.sub(r"[-–—:;/,.!?()\[\]{}]+"," ",text); text=re.sub(r"^(the|a|an)\s+","",text)
    return re.sub(r"\s+"," ",text).strip()

def main():
    questions=json.loads(QUESTIONS.read_text(encoding="utf-8")); expected=int(PLAN["target_questions"])
    assert len(questions)==expected,f"expected {expected}, found {len(questions)}"
    ids=[q["id"] for q in questions]; assert len(ids)==len(set(ids)),"duplicate question IDs"
    total=0
    for q in questions:
        path=ROOT/q["answer_file"]; assert path.exists(),f"missing {path}"
        payload=json.loads(path.read_text(encoding="utf-8")); answers=payload["answers"]
        assert len(answers)==q["answer_count"]
        assert int(PLAN["minimum_answers"])<=len(answers)<=int(PLAN["maximum_answers"])
        seen=set()
        for a in answers:
            assert a["score"] in ALLOWED,f"bad score in {q['id']}"
            key=normalize(a["name"]); assert key and key not in seen,f"duplicate answer in {q['id']}: {a['name']}"
            seen.add(key)
        total+=len(answers)
    print(f"OK: {len(questions)} questions, {total} answer records")

if __name__=="__main__": main()
