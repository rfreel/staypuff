"""Generate self-contained, inspectable offline replay of fixed synthetic runs.
This viewer is explicitly not a live environment or adaptive policy executor.
"""
import json
from pathlib import Path
from .world import HouseholdWorld,ACTIONS
from .scene import with_scene

def build_preview(output='artifacts/preview.html',days=21,seed=7):
    root=Path(__file__).resolve().parent.parent
    episodes=[]
    for a,name in enumerate(ACTIONS):
        w=HouseholdWorld(seed=seed,horizon=days)
        timeline=[with_scene(w.state())]
        for _ in range(days):
            w.step(a);timeline.append(with_scene(w.state()))
        # Matched-world branch for first choice only; recorded as analysis.
        start=HouseholdWorld(seed=seed,horizon=days)
        alternatives=[start.fork(i) for i in range(len(ACTIONS))]
        episodes.append({'policy':name,'timeline':timeline,'alternatives':alternatives})
    html=(root/'web/index.html').read_text()
    css=(root/'web/style.css').read_text()
    js=(root/'web/puffervis.js').read_text()+'\n'+(root/'web/app.js').read_text()
    data=json.dumps({'seed':seed,'days':days,'scenarios':episodes},separators=(',',':'))
    data=data.replace('</','<\\/')
    html=html.replace('<link rel="stylesheet" href="/static/style.css">','<style>'+css+'</style>')
    html=html.replace('<script src="/static/puffervis.js"></script>','')
    html=html.replace('<script src="/static/app.js"></script>',
                      '<script>window.__REPLAY__='+data+';</script><script>'+js+'</script>')
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(html)
    return {'output':str(out),'bytes':out.stat().st_size,'mode':'offline recorded replay',
            'policies':len(episodes),'days':days}
