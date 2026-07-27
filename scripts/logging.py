from __future__ import annotations
# Compatibility shim: this project requires scripts/logging.py, while many libraries
# import the Python stdlib `logging` module. Load stdlib logging explicitly and
# re-export its public API, then add factory event helpers.
import importlib.util, json, sysconfig
from datetime import datetime, timezone
from pathlib import Path
_spec = importlib.util.spec_from_file_location('_stdlib_logging', Path(sysconfig.get_paths()['stdlib'])/'logging'/'__init__.py')
_stdlib_logging = importlib.util.module_from_spec(_spec); assert _spec and _spec.loader; _spec.loader.exec_module(_stdlib_logging)
for _name in dir(_stdlib_logging):
    if not _name.startswith('__'): globals()[_name] = getattr(_stdlib_logging, _name)
from config import load_settings

def get_logger(name='ai_shorts_factory'):
    s=load_settings(); log_file=s.root / s.get('logging.file','logs/factory.log'); log_file.parent.mkdir(exist_ok=True)
    logger=_stdlib_logging.getLogger(name); logger.setLevel(s.get('logging.level','INFO'))
    if not logger.handlers:
        fmt=_stdlib_logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
        fh=_stdlib_logging.FileHandler(log_file, encoding='utf-8'); fh.setFormatter(fmt)
        sh=_stdlib_logging.StreamHandler(); sh.setFormatter(fmt)
        logger.addHandler(fh); logger.addHandler(sh)
    return logger

def write_event(event: str, payload: dict):
    s=load_settings(); p=s.path('logs')/'events.jsonl'
    rec={'ts':datetime.now(timezone.utc).isoformat(),'event':event,'payload':payload}
    with p.open('a',encoding='utf-8') as f: f.write(json.dumps(rec,ensure_ascii=False)+'\n')
