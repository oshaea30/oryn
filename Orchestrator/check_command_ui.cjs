// Optional browser regression. Requires Playwright and installed Chrome on macOS.
// All API routes are mocked: no ADB actions, provider requests or credentials.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const page = await browser.newPage({viewport:{width:1100,height:1050}});
    const posts = [], errors = [];
    let stateAvailable=true, ready=true, fingerprint='stable-context', busyApply=false;
    const snapshot={capturedUtc:Math.floor(Date.now()/1000),owner:1,selectedPartNumber:4,partCount:39};
    page.on('pageerror', error => errors.push(error.message));
    // Serve the checked-out UI as a fixture too; a running command/ADB service
    // should not be a prerequisite for this mocked browser regression.
    for (const [url,name,mime] of [['/','command.html','text/html'],['/command.js','command.js','text/javascript'],['/command.css','command.css','text/css']]) {
      await page.route('http://127.0.0.1:8767'+url, route => route.fulfill({contentType:mime,body:fs.readFileSync(path.join(__dirname,name),'utf8')}));
    }
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      let result = {};
      if (path === '/api/session') result = {token:'fixture-only',commandContract:2};
      if (path === '/api/budget') result = {day:'2026-09-27',halted:false,daily_limit_nanos:2000000000,charged_and_reserved_nanos:0,remaining_nanos:2000000000,recent:[]};
      if (path === '/api/quote') result = {snapshot,contextFingerprint:fingerprint,request_id:'e'.repeat(32),model:'gpt-6-sol',effort:'medium',input_tokens:500,max_output_tokens:1024,reserved_nanos:11490000,ceiling_nanos:30000000,daily_remaining_nanos:2000000000,expires:Math.floor(Date.now()/1000)+120,note:'Fixture cost quote'};
      if (path === '/api/state') result = stateAvailable?{contextFingerprint:fingerprint,configured:{},state:{session:'a'.repeat(32),contextToken:(ready?'b':'c').repeat(32),context:{
        owner:1,ready,partsMode:true,isolated:false,selectedPartId:'d'.repeat(64),
        parts:[{partId:'d'.repeat(64),number:4,label:'Other',revision:1,error:''}]}}}:{configured:{openai:'routine'},state:null,stateError:'Headset unavailable'};
      if (path === '/api/ask') {
        posts.push(route.request().postDataJSON());
        result = {snapshot,contextFingerprint:fingerprint,id:'f'.repeat(32),provider:'offline',model:'fixture',answer:'Other — unverified user annotation. <img src=x>',action:'isolate'};
      }
      if (path === '/api/apply') {
        if(busyApply) return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:'Headset busy; confirm again when ready.'})});
        posts.push(route.request().postDataJSON());
        result = {id:'f'.repeat(32),status:'waiting',message:'Fixture transfer'};
      }
      if (path.startsWith('/api/receipt/')) result = {status:'executed',message:'Fixture execution'};
      await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
    });
    await page.goto('http://127.0.0.1:8767/');
    assert.deepEqual(await page.locator('#provider option').evaluateAll(options => options.map(o=>o.value)),['offline','openai','gemini']);
    await page.getByRole('button',{name:'Isolate this',exact:true}).click();
    await page.locator('#ask').click();
    await page.waitForFunction(()=>!document.querySelector('#apply').disabled);
    assert.equal(posts.length,1,'No action before confirmation');
    assert.equal(await page.locator('#answer img').count(),0,'Untrusted text must not become markup');
    await page.locator('#apply').click();
    await page.waitForFunction(()=>document.querySelector('#receipt').textContent.startsWith('EXECUTED'));
    assert.equal(posts.length,2);
    assert.deepEqual(posts[1],{id:'f'.repeat(32)},'Browser sends only the server-owned proposal ID');
    await page.locator('#provider').selectOption('openai');
    assert.equal(await page.locator('#paid').isChecked(),false);
    assert.equal(await page.locator('#paid').isDisabled(),true,'Cannot approve without a quote');
    await page.locator('#quote').click();
    await page.waitForFunction(()=>!document.querySelector('#paid').disabled);
    assert.ok((await page.locator('#quoteDetails').innerText()).includes('$0.011490'));
    await page.locator('#paid').check();
    await page.locator('#question').fill('Explode');
    assert.equal(await page.locator('#paid').isChecked(),false,'Editing input invalidates quote');
    assert.equal(await page.locator('#paid').isDisabled(),true);
    await page.locator('#quote').click();
    await page.waitForFunction(()=>!document.querySelector('#paid').disabled);
    await page.locator('#paid').check();
    ready=false;
    await page.locator('#refresh').click();
    await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('release objects'));
    assert.equal(await page.locator('#paid').isChecked(),true,'Temporary readiness must not invalidate quote consent');
    stateAvailable=false;
    await page.locator('#refresh').click();
    await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('unavailable'));
    assert.equal(await page.locator('#paid').isChecked(),true,'Disconnection preserves approval of the frozen snapshot');
    await page.locator('#ask').click();
    await page.waitForFunction(()=>!document.querySelector('#ask').disabled);
    assert.equal(posts.length,3);
    assert.equal(posts[2].id,'e'.repeat(32));
    assert.equal(posts[2].approvedCostNanos,11490000);
    assert.equal(posts[2].approvePaid,true);
    assert.equal(await page.locator('#paid').isDisabled(),true,'Approval consumed once');
    assert.ok((await page.locator('#attribution').innerText()).includes('Part 4'),'Response identifies frozen target');
    busyApply=true;
    await page.locator('#apply').click();
    await page.waitForFunction(()=>document.querySelector('#receipt').textContent.includes('Headset busy'));
    assert.equal(await page.locator('#apply').isDisabled(),false,'Definite busy rejection preserves proposal for manual confirmation');
    assert.equal(posts.length,3,'Busy rejection does not reinterpret');
    busyApply=false;stateAvailable=true;ready=true;
    await page.locator('#refresh').click();
    await page.waitForFunction(()=>document.querySelector('#connection').textContent==='Connected / ready');
    assert.equal(await page.locator('#apply').isDisabled(),false,'Readiness recovery preserves action proposal');
    fingerprint='different-target';
    await page.locator('#refresh').click();
    await page.waitForFunction(()=>document.querySelector('#apply').disabled);
    await page.locator('#provider').selectOption('gemini');
    assert.equal(await page.locator('#paid').isChecked(),false,'Consent is not carried across providers');
    assert.equal(await page.locator('#quote').isDisabled(),true,'Unpriced provider cannot get a quote');
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No mobile overflow');
    assert.deepEqual(errors,[]);
    console.log('ORYN_COMMAND_UI_OK frozen quotes, offline interpretation, fresh-action gate, manual busy retry, target changes, confirmation, receipts, escaping, mobile layout');
  } finally { await browser.close(); }
})().catch(error=>{ console.error(error.message); process.exitCode=1; });
