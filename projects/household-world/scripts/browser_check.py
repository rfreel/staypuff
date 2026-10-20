"""End-to-end browser checks and actual visual screenshots; assumes local API running."""
from playwright.sync_api import sync_playwright
from pathlib import Path

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':960},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(Path('artifacts/preview.html').read_text(),wait_until='load',timeout=30000)
        assert 'Decisions' in page.locator('.hero-title').inner_text()
        assert page.locator('#nowIndicator').inner_text()=='DAY 00 / 21'
        page.screenshot(path='artifacts/screenshot-desktop-start.png',full_page=True)
        page.locator('#step').click()
        page.wait_for_function("document.querySelector('#nowIndicator').textContent.includes('DAY 01')",timeout=10000)
        assert 'DAY 01' in page.locator('#nowIndicator').inner_text()
        page.locator('[data-view="beads"]').click()
        assert page.locator('.bead-node').count()>60
        page.screenshot(path='artifacts/screenshot-beads.png',full_page=True)
        page.locator('[data-view="kitchen"]').click()
        assert page.locator('.gantt-row').count()>1
        page.screenshot(path='artifacts/screenshot-kitchen.png',full_page=True)
        page.locator('[data-view="counterfactual"]').click()
        page.locator('#compare').click()
        page.wait_for_function("document.querySelectorAll('.comparison-card').length === 8",timeout=15000)
        page.screenshot(path='artifacts/screenshot-counterfactual.png',full_page=True)
        page.locator('[data-view="overview"]').click()
        mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
        mobile.on('pageerror',lambda e:errors.append('mobile '+str(e)))
        mobile.set_content(Path('artifacts/preview.html').read_text(),wait_until='load',timeout=30000)
        mobile.screenshot(path='artifacts/screenshot-mobile.png',full_page=True)
        assert mobile.locator('#step').is_visible()
        assert mobile.locator('#peopleCards .person').count()==3
        mobile.locator('[data-view="market"]').click()
        assert mobile.locator('#marketTable tbody tr').count()>=12
        assert not errors,errors
        browser.close()
        print('BROWSER PASS / offline replay: desktop start, step, Beads, kitchen, alternatives; mobile market')
        print('5 screenshots saved; no JavaScript exceptions')
if __name__=='__main__':main()
