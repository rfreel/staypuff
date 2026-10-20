"""Verify actual FastAPI transitions driving the live browser UI, with fetch bridged via TestClient.
The container's Chromium network policy blocks navigation even to mocked local origins;
its rendering and JavaScript are real, but network transport is substituted.
"""
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from household.api import app,state

SHIM="""<script>
window.fetch = async (uri, options={}) => {
  const data = await window.__python_api_fetch(String(uri), JSON.stringify(options));
  return {ok:data.status>=200&&data.status<300, status:data.status, statusText:data.status_text,
          json: async()=> JSON.parse(data.body)};
};
</script>"""

def main():
    state.reset()
    client=TestClient(app)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':900})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def handle_api(source, uri, raw_options):
            import json
            options=json.loads(raw_options)
            resp=client.request(options.get('method','GET'),uri,
                                content=options.get('body'), headers={'Content-Type':'application/json'})
            return {'status':resp.status_code,'body':resp.text,'status_text':'OK' if resp.status_code<400 else 'HTTP ERROR'}
        page.expose_binding('__python_api_fetch',handle_api)
        html=(ROOT/'web/index.html').read_text()
        html=html.replace('<link rel="stylesheet" href="/static/style.css">',
                          '<style>'+(ROOT/'web/style.css').read_text()+'</style>')
        html=html.replace('<script src="/static/app.js"></script>',
                          SHIM+'<script>'+(ROOT/'web/app.js').read_text()+'</script>')
        page.set_content(html,wait_until='load')
        page.wait_for_function("document.querySelector('#peopleCards .person')?.textContent.includes('HUSBAND')",timeout=10000)
        assert page.locator('#peopleCards .person').count()==3
        assert page.locator('#nowIndicator').inner_text()=='DAY 00 / 30'
        page.locator('#step').click()
        page.wait_for_function("document.querySelector('#nowIndicator').textContent.includes('DAY 01')",timeout=10000)
        assert state.world.day==1
        page.locator('[data-view="beads"]').click()
        assert page.locator('.bead-node').count()>=60
        page.locator('[data-view="counterfactual"]').click()
        page.wait_for_function("document.querySelectorAll('.comparison-card').length === 8",timeout=10000)
        assert state.world.day==1, 'counterfactual should not mutate world'
        page.locator('#reset').click()
        page.wait_for_function("document.querySelector('#nowIndicator').textContent.includes('DAY 00')",timeout=10000)
        assert state.world.day==0
        page.locator('#configure').click()
        assert page.locator('#configDialog').is_visible()
        page.locator('#budgetInput').fill('178')
        page.locator('.config-person').nth(2).locator('.input-age').fill('4')
        page.locator('#configForm button[type=submit]').click()
        page.wait_for_function("document.querySelector('#configDialog').open===false",timeout=10000)
        assert state.world.weekly_budget_cents==17800
        assert state.world.people[2].age_years==4
        assert state.world.day==0
        assert not errors,errors
        browser.close()
    print('BROWSER + REAL API LOGIC PASS / Chromium UI, injected fetch transport -> FastAPI TestClient: reset, step, Beads, eight branches, configure household')
if __name__=='__main__':main()
