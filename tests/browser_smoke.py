"""Optional end-to-end checks. Requires playwright and a running demo server."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
URL=os.getenv('COOLING_TEST_URL','http://127.0.0.1:8765')


def main():
    with sync_playwright() as p:
        # Prefer normal Playwright browser installation; allow an explicit existing binary.
        executable=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE')
        browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
        page=browser.new_page(viewport={'width':1440,'height':1080},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.request.post(URL+'/api/consent',data={'consent':False})
        page.goto(URL,wait_until='networkidle')
        assert page.title()=='Hostel Cooling Lab'
        page.locator('#recommend-top').click();page.locator('#recommend-result').wait_for(state='visible')
        assert 'TSV proxy' in page.locator('#comfort').inner_text()
        page.locator('#rain').check();page.locator('#recommend-top').click()
        page.locator('#recommend-result').wait_for(state='visible')
        assert page.locator('#window-action').inner_text()=='Closed'
        page.locator('#rain').uncheck()
        page.locator('#consent').check()
        page.wait_for_function("() => document.getElementById('memory-profile').textContent.includes('Study target')")
        page.locator('#message').fill('I prefer 27 C. I want airflow.')
        page.locator('#save-preference').click()
        page.wait_for_function("() => document.getElementById('memory-profile').textContent.includes('Study target 27')")
        page.locator('[data-activity=sleep]').click()
        page.locator('#message').fill('I prefer 29 C. I need quiet when sleeping.')
        page.locator('#save-preference').click()
        page.wait_for_function("() => document.getElementById('memory-profile').textContent.includes('Sleep target 29')")
        page.locator('#recommend-top').click();page.locator('#recommend-result').wait_for(state='visible')
        assert page.locator('#fan-action').inner_text() in ('Off','Low · 1')
        page.locator('#accept').click()
        page.wait_for_function("() => document.getElementById('feedback-status').textContent.includes('stored separately')")
        exported=page.request.get(URL+'/api/profile/export').json()
        assert exported['preference']['activity_targets']=={'study':27.0,'sleep':29.0}
        assert len(exported['feedback'])==1
        page.reload(wait_until='networkidle')
        assert 'Study target 27' in page.locator('#memory-profile').inner_text()
        page.locator('#recommend-top').click();page.locator('#recommend-result').wait_for(state='visible')
        page.locator('#toast').evaluate("n => n.classList.remove('visible')")
        page.screenshot(path=str(ROOT/'outputs/demo/dashboard.png'),full_page=True)
        page.locator('[data-view=evidence]').click();page.locator('#results tr').first.wait_for()
        assert page.locator('#results tr').count()==8
        page.locator('#toast').evaluate("n => n.classList.remove('visible')")
        page.screenshot(path=str(ROOT/'outputs/demo/comparison-dashboard.png'),full_page=True)
        assert page.request.get(URL+'/report').status==200
        page.locator('[data-view=pilot]').click()
        page.locator('#pilot-file').set_input_files(str(ROOT/'data/synthetic_pilot.csv'))
        page.locator('#validate-pilot').click()
        page.wait_for_function("() => document.getElementById('pilot-status').textContent.includes('Valid: 672')")
        page.locator('#erase').click()
        page.wait_for_function("() => document.getElementById('privacy-status').textContent.includes('erased')")
        data=page.request.get(URL+'/api/profile/export').json()
        assert data['events']==[] and data['feedback']==[] and not data['consent']
        denied=page.request.post(URL+'/api/preferences',data={'activity':'study','message':'I prefer 25 C'})
        assert denied.status==403
        cross=page.request.post(URL+'/api/consent',data={'consent':True},headers={'Origin':'https://example.com'})
        assert cross.status==403
        page.locator('[data-view=lab]').click();page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('#toast').evaluate("n => n.classList.remove('visible')")
        page.screenshot(path=str(ROOT/'outputs/demo/mobile-dashboard.png'),full_page=True)
        assert not errors,errors
        browser.close()
        print(json.dumps({'browser':'Chromium headless','checks':'recommendation, rain constraint, consent, activity memory, persistence, feedback, comparison, CSV validation, erasure, cross-origin rejection, responsive layout','javascript_errors':errors,'status':'passed'},indent=2))


if __name__=='__main__':main()
