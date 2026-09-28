// Mocked local evidence only. No providers, headset calls or credentials.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try{
    const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[],requests=[];
    const id='a'.repeat(64),g=id+':island:001';
    let record={id,status:'ready',latency_ms:42,targets:[g],views:[{geometry_id:g,nearest_bounds:[]}],
      measurements:[{geometry_id:g,triangles:4,vertices:5,bounds_local:{size:[1,2,3]}}],
      limitations:['<img src=x onerror=alert(1)> untrusted label'],candidate_revisions:[]};
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>{
      const request=route.request(),url=new URL(request.url());requests.push(request.method());
      if(url.pathname==='/geometry-evidence')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'geometry_evidence.html'),'utf8')});
      if(url.pathname==='/api/geometry-evidence')return route.fulfill({json:record});
      if(url.pathname==='/api/geometry-view')return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="540"><rect width="1000" height="540" fill="#6fe3bd"/></svg>'});
      return route.abort();
    });
    await page.goto('http://127.0.0.1:8765/geometry-evidence?id='+id);
    await page.waitForFunction(()=>document.querySelector('#views').naturalWidth>0);
    assert.match(await page.locator('#notice').innerText(),/\$0 provider cost/);
    assert.equal(await page.locator('#limitations img').count(),0);
    assert.match(await page.locator('#coverage').innerText(),/Original model and runtime capabilities are unchanged/);
    assert.match(await page.locator('#mapping').innerText(),/has not run/);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    record={id,status:'unavailable',error:'Original preserved.'};await page.locator('#reload').click();
    await page.waitForFunction(()=>document.querySelector('#evidence').hidden);
    await page.goto('http://127.0.0.1:8765/geometry-evidence?id=bad');
    await page.waitForFunction(()=>document.querySelector('#notice').textContent==='Invalid evidence link.');
    assert.ok(requests.every(method=>method==='GET'));assert.deepEqual(errors,[]);
    console.log('ORYN_GEOMETRY_EVIDENCE_UI_OK read-only, image rendering, escaping, mobile, unavailable states');
  }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
