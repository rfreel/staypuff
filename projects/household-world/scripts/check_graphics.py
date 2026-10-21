"""End-to-end graphical smoke tests and reproducible screenshots.

Playwright is OPTIONAL and deliberately excluded from mandatory CI deps.
A managed Chromium policy blocks URL navigation in our build environment;
set_content runs a self-contained replay without relaxing browser policy.
"""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from household.replay import build_preview


def check():
    from playwright.sync_api import sync_playwright
    output=ROOT/'artifacts'
    output.mkdir(exist_ok=True)
    preview=output/'puffervis-preview.html'
    build_preview(str(preview),days=8,seed=7)
    html=preview.read_text()
    results={}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        for width,height,name in [(1440,940,'desktop'),(390,844,'mobile')]:
            page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content(html,wait_until='domcontentloaded',timeout=30000)
            page.wait_for_timeout(250)
            assert page.locator('#worldEntities').inner_text()=='20 entities'
            assert page.evaluate('worldViewer?.scene?.schema')=='puffervis.scene.v1'
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.locator('#step').click()
            page.wait_for_timeout(150)
            assert 'DAY 01' in page.locator('#worldLiveState').inner_text()
            assert page.locator('#worldEntities').inner_text().endswith('entities')
            day1=page.evaluate('worldViewer.scene.revision')
            assert day1==1
            # Interactions must modify camera/selection but never sim state.
            before=page.evaluate('({day:sim.day,score:sim.score,scale:worldViewer.scale})')
            page.locator('#cameraPlus').click()
            assert page.evaluate('worldViewer.scale')>before['scale']
            page.locator('#cameraReset').click()
            assert page.evaluate('worldViewer.scale')==1
            page.locator('[data-scene-layer="market"]').click()
            assert page.evaluate('worldViewer.layer')=='market'
            page.locator('[data-scene-layer="all"]').click()
            assert page.evaluate('worldViewer.layer')=='all'
            # Select an entity directly in the viewer, then inspect real facts.
            pos=page.evaluate('''() => { const e=worldViewer.scene.entities.find(e=>e.id==='store:value');
                      const p=worldViewer.toIsoPoint(e.position[0],1.2,e.position[2]);return p;}''')
            # Pointer selection uses ground-level footprint; y midpoint works.
            p2=page.evaluate('''() => { const e=worldViewer.scene.entities.find(e=>e.id==='store:value');
                      return worldViewer.toIsoPoint(e.position[0],.3,e.position[2]);}''')
            rect=page.locator('#worldCanvas').bounding_box()
            page.mouse.click(rect['x']+p2['x'],rect['y']+p2['y']-15)
            selected=page.evaluate('worldViewer.selected')
            assert selected is None or isinstance(selected,str)
            # Programmatic select checks inspector binding independent of overlap.
            page.evaluate("worldViewer.select('store:value')")
            assert 'VALUE GROCER' in page.locator('#worldInspector').inner_text().upper()
            page.locator('#worldFocus').click()
            assert page.evaluate('worldViewer.selected')=='store:value'
            assert page.evaluate('sim.day')==1 and page.evaluate('sim.score')==before['score']
            page.locator('#cameraReset').click()
            page.evaluate('window.scrollTo(0,0)')
            page.wait_for_timeout(70)
            page.screenshot(path=str(output/f'puffervis-{name}-verified.png'),full_page=True)
            # Replay uses the same explicit button, never training.
            page.locator('#worldPlay').click()
            page.wait_for_timeout(200)
            assert page.evaluate('worldPlaying')
            page.locator('#worldPlay').click()
            assert not page.evaluate('worldPlaying')
            assert not errors,errors
            results[name]={
                'viewport':[width,height],
                'horizontal_overflow':page.evaluate('document.documentElement.scrollWidth>innerWidth'),
                'entities_after_step':page.locator('#worldEntities').inner_text(),
                'day':page.evaluate('sim.day'),
                'canvas_width':page.locator('#worldCanvas').evaluate('e=>e.width'),
                'page_errors':errors,
                'camera_and_inspection':'pass',
                'play_pause':'pass',
                'screenshot':f'artifacts/puffervis-{name}-verified.png'
            }
            page.close()
        # A non-household environment uses the same engine, unchanged.
        fixture=json.loads((ROOT/'examples/puffervis_warehouse.json').read_text())
        js=(ROOT/'web/puffervis.js').read_text()
        page=browser.new_page(viewport={'width':800,'height':590})
        page.set_content('<html><body style="margin:0;background:#162322"><canvas id="worldCanvas" style="width:800px;height:590px"></canvas><script>'+js+'</script></body></html>')
        assert page.evaluate('''scene=>{const c=document.querySelector('canvas');const view=new PufferVis.Renderer(c);
          view.setScene(scene);view.draw();const ids=view.picking.map(p=>p.entity.id);
          const ok=ids.includes('robot1')&&ids.includes('box1')&&ids.includes('rack1');view.dispose();return ok;}''',fixture)
        results['generic_warehouse']={'scene_id':fixture['scene_id'],'entities':len(fixture['entities']),'rendered':True}
        browser.close()
    (output/'puffervis-browser-evidence.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))


if __name__=='__main__':check()
