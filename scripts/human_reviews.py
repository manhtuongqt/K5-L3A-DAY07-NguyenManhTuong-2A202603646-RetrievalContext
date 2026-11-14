"""Bind approved draft labels to the student's exact explicit artifact confirmation."""
from copy import deepcopy
from src.lab_common import ROOT,read_json,sha256

def confirmed_reviews(split,config_id,root=ROOT):
    filename=f'results/audit/{split}/{config_id}_reviews.json'
    record_name=f'results/audit/{split}_human_confirmation.json'
    record=read_json(root/record_name)
    if filename not in record['artifact_hashes']:
        raise ValueError(f'{filename}: not included in student confirmation')
    for name,expected in record['artifact_hashes'].items():
        if sha256(root/name)!=expected:
            raise ValueError(f'Approved artifact changed: {name}')
    rows=deepcopy(read_json(root/filename))
    for row in rows:
        if row.get('trace') and sha256(root/row['trace'])!=row['trace_sha256']:
            raise ValueError(f"Reviewed trace changed: {row['query_id']}")
        row['draft_reviewer']=row.get('reviewer')
        row.update(human_confirmed=True,reviewer=record['reviewer'],
                   review_status='AI-assisted draft reviewed and accepted by the student',
                   human_confirmation_file=record_name)
    return rows
