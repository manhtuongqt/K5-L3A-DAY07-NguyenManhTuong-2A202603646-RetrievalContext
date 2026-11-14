"""Record an explicit student's review statement against exact reviewed artifact bytes.

This command does not perform a review. Use only after the student has actually
confirmed the corresponding packet in the conversation or a signed review file.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.lab_common import ROOT,read_json,sha256,write_json,now

def confirm(kind,statement,files,reviewer,root=ROOT):
    if not statement.strip() or not files:
        raise ValueError('An explicit review statement and exact artifact files are required.')
    checks={str(Path(f).as_posix()):sha256(root/f) for f in files}
    if kind=='benchmark':
        cases=read_json(root/'benchmark/questions.json')
        items=[{'id':c['id'],'sha256':hashlib.sha256(json.dumps(c,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()} for c in cases]
    else:
        items=[]
        for f in files:
            if Path(f).suffix.lower()!='.json':
                continue
            value=read_json(root/f)
            if isinstance(value,list):
                items.extend({'artifact':str(Path(f).as_posix()),'config_id':r.get('config_id'),'query_id':r.get('query_id'),
                              'sha256':hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()} for r in value)
    output={'kind':kind,'confirmed_at':now(),'reviewer':reviewer,'statement':statement,
            'source':'Explicit student confirmation in conversation; recorder does not itself constitute review.',
            'artifact_hashes':checks,'approved_items':items,'count':len(items),
            'draft_provenance':'AI-assisted preparation, reviewed and accepted by the student. Not independent blind annotations.'}
    write_json(root/f'results/audit/{kind}_human_confirmation.json',output)
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=['benchmark','dev','test'],required=True)
    p.add_argument('--statement-file',type=Path,required=True)
    p.add_argument('--reviewer',required=True)
    p.add_argument('--files',nargs='+',required=True)
    args=p.parse_args()
    print(json.dumps(confirm(args.kind,args.statement_file.read_text(encoding='utf-8'),args.files,args.reviewer),ensure_ascii=True,indent=2))
if __name__=='__main__':main()
