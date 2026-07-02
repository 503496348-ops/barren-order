import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.stage_gate_manifest import StageEvidence, write_stage_manifest

def test_passed_stage_requires_artifact(tmp_path):
    data=write_stage_manifest(tmp_path/'m.json',[StageEvidence('A','passed',[], 'qa')])
    assert not data['ok'] and 'artifacts' in data['errors'][0]

def test_passed_stage_accepts_verified_artifact(tmp_path):
    data=write_stage_manifest(tmp_path/'m.json',[StageEvidence('A','passed',['out.md'], 'qa')])
    assert data['ok'], data
