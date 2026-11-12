"""Build a deterministic Freeciv scenario using the upstream save schema."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
src = ROOT / 'upstream/freeciv-3.2.6'
template = (src / 'data/scenarios/british-isles.sav').read_text(encoding='utf-8')
header = template.split('[game]')[0]
header = re.sub(r'^name=.*$', 'name="Border Keep / 边境要塞"', header, flags=re.M)
header = re.sub(r'authors=.*', 'authors="Freeciv contributors; local demonstration adaptation"', header)
header = re.sub(r'description=.*', 'description="Capture income sites, recruit four unit roles, defend Westwatch, and besiege Border Keep."', header)
header = header.replace('rulesetdir="classic"','rulesetdir="gaze_war"')
header = header.replace('ruleset_locked=FALSE', 'ruleset_locked=TRUE')
script = (ROOT/'scenario/campaign.lua').read_text(encoding='utf-8')
settings = {
    'aifill': 2, 'ailevel': 'Easy', 'generator':'SCENARIO', 'mapsize':'XYSIZE',
    'xsize':24, 'ysize':40, 'topology':'ISO', 'wrap':'', 'maxplayers':2,
    'minplayers':1, 'nationset':'all', 'startunits':'c', 'techlevel':0,
    'gold':100, 'fogofwar':True, 'timeout':0, 'endturn':80,
    'victories':'', 'barbarians':'DISABLED', 'diplomacy':'DISABLED',
    'phasemode':'PLAYER', 'citymindist':2, 'saveturns':0,
    'gameseed':3576, 'mapseed':3576, 'huts':0, 'animals':0, 'disasters':0,
}
def val(x):
    if isinstance(x,bool): return str(x).upper()
    return str(x) if isinstance(x,int) else '"'+x+'"'
game = template.split('[game]')[1].split('[random]')[0]
game = re.sub(r'(?m)^rulesetdir=.*$', 'rulesetdir="gaze_war"', game)
out = header+'[game]'+game+'[random]\nsaved=FALSE\n\n[script]\ncode=$\ncampaign_hotseat=false\n'+script+'$\nvars=$$\n\n[settings]\nset={"name","value"\n'
out += '\n'.join('"'+k+'",'+val(v) for k,v in settings.items())
out += '\n}\nset_count='+str(len(settings))+'\ngamestart_valid=FALSE\n\n[map]\nhave_huts=FALSE\nhave_resources=FALSE\n'
for y in range(40):
    row = []
    for x in range(24):
        t = 'g'
        if x < 2 or x > 21 or y < 2 or y > 37: t = ' '
        elif y < 15 or y > 24: t = 'f' if (x+y)%3 else 'h'
        elif x in (3,4,19,20) and y % 3: t = 'f'
        elif y in (16,22) and x%4 == 0: t = 'h'
        row.append(t)
    out += f't{y:04d}="'+''.join(row)+'"\n'
out += 'startpos_count=2\nstartpos={"x","y","exclude","nations"\n7,19,FALSE,"Roman"\n17,19,FALSE,"Greek"\n}\n'
for layer in range(9):
    for y in range(40):
        out += f'e{layer:02d}_{y:04d}="'+('0'*24)+'"\n'
target=ROOT/'scenario/border-keep.sav'
target.parent.mkdir(exist_ok=True)
target.write_text(out,encoding='utf-8',newline='\n')
print(target)
duel=out.replace('campaign_hotseat=false\n','campaign_hotseat=true\n',1).replace(
    'name="Border Keep / 边境要塞"','name="Border War / 双人轮战"',1)
target=ROOT/'scenario/duel-hotseat.sav';target.write_text(duel,encoding='utf-8',newline='\n');print(target)
