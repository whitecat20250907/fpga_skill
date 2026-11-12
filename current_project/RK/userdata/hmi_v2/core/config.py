from pathlib import Path
import os
import json
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load(path=None):
    path = Path(path or os.environ.get('HMI_CONFIG', ROOT/'config/hmi.yaml'))
    config = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(config, dict) or config.get('schema') != 1:
        raise ValueError('Unsupported configuration schema')
    # Keep interaction tuning separate from board paths, hardware and users'
    # saved gesture bindings. All consumers load the same thresholds.
    tuning=ROOT/'config/interaction.json'
    if tuning.exists():
        for section,values in json.loads(tuning.read_text('utf-8')).items():
            if section not in ('gestures','interaction'):raise ValueError('Unknown interaction tuning section')
            dest=config.setdefault(section,{})
            for key,value in values.items():
                if isinstance(value,dict):dest.setdefault(key,{}).update(value)
                else:dest[key]=value
    for name, limit in [('gaze_action',250),('hand',350)]:
        if not 0 < config['freshness_ms'][name] <= limit:
            raise ValueError('Freshness limit cannot exceed design contract')
    if any(config.get('features',{}).values()):
        raise ValueError('P6 experimental features require an implemented and board-validated variant; this build supports false only')
    app_cpus=config.get('applications',{}).get('cpu_affinity',[0,1])
    if not isinstance(app_cpus,list) or not app_cpus or any(type(v) is not int or not 0<=v<8 for v in app_cpus) or len(set(app_cpus))!=len(app_cpus):
        raise ValueError('Application CPU affinity must be a nonempty unique list of RK CPU indices 0..7')
    config.setdefault('actions',{}).setdefault('BASIC',{})
    from .bindings import defaults,validate
    saved=ROOT/'config/bindings.json'
    config['bindings']=validate(json.loads(saved.read_text('utf-8'))) if saved.exists() else defaults(config)
    return config
