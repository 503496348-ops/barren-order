from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, time
@dataclass
class StageEvidence:
    stage:str; status:str; artifacts:list[str]; verifier:str; notes:str=''
    def validate(self)->list[str]:
        errors=[]
        if self.status not in {'pending','blocked','passed','failed'}: errors.append(f'{self.stage}: invalid status')
        if self.status=='passed' and not self.artifacts: errors.append(f'{self.stage}: passed stage needs artifacts')
        if self.status=='passed' and not self.verifier: errors.append(f'{self.stage}: passed stage needs verifier')
        return errors
def write_stage_manifest(path:str|Path, stages:list[StageEvidence])->dict:
    errors=[]
    for s in stages: errors.extend(s.validate())
    data={'created_at':time.time(),'ok':not errors,'errors':errors,'stages':[asdict(s) for s in stages]}
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data
