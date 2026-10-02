"""Verify the live localhost UI and media in a clean, headless browser context."""
import json
from explainer.config import settings
from playwright.sync_api import sync_playwright

def main():
    config=settings(); screenshots=config.scratch/'ui-check';screenshots.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1080});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:8090');page.locator('#topic').wait_for()
        assert page.locator('#mode').input_value()=='offline'
        page.screenshot(path=str(screenshots/'desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(screenshots/'mobile.png'),full_page=True)
        page.set_viewport_size({'width':1440,'height':1080})
        page.locator('[data-job="lesson_9e31ab954709"]').click()
        page.locator('video').wait_for()
        page.wait_for_function('document.querySelector("video").readyState>=1')
        dimensions=page.locator('video').evaluate('(video)=>[video.videoWidth,video.videoHeight]')
        assert dimensions==[1920,1080]
        page.locator('#adjust').click();page.locator('dialog select').select_option('scene_2_1')
        assert page.locator('#revise-button').inner_text()=='Regenerate this scene'
        page.locator('#close-dialog').click()
        page.screenshot(path=str(screenshots/'completed.png'),full_page=True)
        page.locator('[data-job="lesson_373089dbde59"]').click();page.locator('#generate').wait_for()
        assert page.locator('h1').inner_text().startswith('Tavern')
        page.screenshot(path=str(screenshots/'tavern-outline.png'),full_page=True)
        assert not errors,errors
        browser.close()
    print(json.dumps({'ui_errors':errors,'video_dimensions':dimensions,'screenshots':str(screenshots),'mobile_no_horizontal_overflow':True},indent=2))

if __name__=='__main__':main()
