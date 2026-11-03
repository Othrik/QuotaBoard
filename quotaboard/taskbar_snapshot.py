"""Export only public-facing quota data, never configuration or credentials."""
import json
from datetime import datetime,timezone
from pathlib import Path

def export_snapshot(config, rows):
    if not getattr(config,'path',None): return
    payload={'updated_at':datetime.now(timezone.utc).isoformat(),'items':[]}
    for r in rows:
        payload['items'].append({'platform':r.platform,'label':r.label,'display':r.display if r.ok else '请求失败','ok':r.ok,'percent':r.percent,'updated_at':r.updated_at,'metrics':[{'label':m.get('label',''),'percent':m.get('percent'),'note':m.get('note','')} for m in (r.metrics or [])]})
    target=Path(config.path).with_name('taskbar-snapshot.json')
    temp=target.with_suffix('.tmp')
    try:
        target.parent.mkdir(parents=True,exist_ok=True)
        temp.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
        temp.replace(target)
    except OSError:
        pass
