// All routes are mocked. No provider calls, keys or Quest writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const page=await browser.newPage({viewport:{width:1050,height:1000}});
    const errors=[],posts=[];let busy=false,deliveryPending=false,jobs=[],lost=false,reject=false;
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',async route=>{
      const name=new URL(route.request().url()).pathname;
      if(name==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'experience.html'),'utf8')});
      if(name==='/api/state')return route.fulfill({json:{token:'fixture',experienceContract:1,configured:true,busy,deliveryPending,jobs,experiencePolicy:{credits_per_generation:5,rolling_day_limit:50,reserved_last_day:5}}});
      if(name==='/api/request-object'){
        const body=route.request().postDataJSON();posts.push(body);
        if(reject)return route.fulfill({status:400,json:{error:'The automatic generation credit limit has been reached.'}});
        busy=true;jobs=[{id:body.request_id,experience:true,prompt:body.prompt,status:'generating_geometry',progress:30}];
        if(lost)return route.abort();
        return route.fulfill({status:202,json:jobs[0]});
      }
      return route.abort();
    });
    await page.goto('http://127.0.0.1:8765/');
    assert.equal(await page.locator('input[type=checkbox]').count(),0,'No approval controls');
    await page.locator('#prompt').fill('Show me a lamp <img src=x>');
    await page.locator('#show').click();
    await page.waitForFunction(()=>document.querySelector('#status').textContent==='Generating your object…');
    assert.equal(posts.length,1);
    assert.deepEqual(Object.keys(posts[0]).sort(),['prompt','request_id']);
    assert.equal(await page.locator('#show').isDisabled(),true,'Double submits blocked while busy');
    assert.equal(await page.locator('#object img').count(),0,'Prompt is rendered as text');
    jobs[0].status='waiting_for_headset';busy=false;deliveryPending=true;
    await page.evaluate(()=>refresh());
    assert.equal(await page.locator('#status').innerText(),'Ready for your headset');
    assert.equal(await page.locator('#show').isDisabled(),true,'Pending receipt blocks a second object');
    jobs[0].status='loaded_on_quest';deliveryPending=false;
    await page.evaluate(()=>refresh());
    assert.equal(await page.locator('#status').innerText(),'In your space');
    assert.equal(posts.length,1,'Loading never needs a second click or POST');
    jobs[0].ingestions={geometry:{piece_count:200,component_count:0,runtime:{sha256:'source'},capabilities:{geometric_explosion:{status:'unsupported',reason:'200 pieces exceed the active-part budget.'}}}};
    await page.evaluate(()=>refresh());
    assert.ok((await page.locator('#capabilities').innerText()).includes('Take-apart mode: unavailable'));
    assert.ok((await page.locator('#capabilities').innerText()).includes('200 geometric pieces recorded · 0 identified components'));
    jobs[0].ingestions.geometry={piece_count:39,component_count:0,runtime:{sha256:'prepared'},capabilities:{geometric_explosion:{status:'supported'}}};
    await page.evaluate(()=>refresh());
    assert.ok((await page.locator('#capabilities').innerText()).includes('has not been confirmed loaded'),'Old source delivery must not prove prepared assembly loaded');
    jobs[0].delivery_asset_sha256='prepared';await page.evaluate(()=>refresh());
    assert.ok((await page.locator('#capabilities').innerText()).includes('headset interaction not yet verified'));
    jobs[0].investigations={geometry:{id:'a'.repeat(64),status:'awaiting_research',selected_for_investigation:8}};
    await page.evaluate(()=>refresh());
    assert.ok((await page.locator('#capabilities').innerText()).includes('Research and semantic mapping are not connected yet'));
    assert.equal(await page.locator('#capabilities a').getAttribute('href'),'/api/workflow?id='+'a'.repeat(64));
    jobs[0].investigation_error='<img src=x> unavailable';await page.evaluate(()=>refresh());
    assert.equal(await page.locator('#capabilities img').count(),0,'Workflow errors rendered as text');
    jobs[0].research={status:'reference_notes_ready',sources:[{id:'safe',title:'Engine source',url:'https://en.wikipedia.org/?curid=1'},{id:'bad',title:'Unsafe',url:'javascript:alert(1)'}],
      findings:{overview:[{text:'<img src=x> candidate overview',source_ids:['safe','bad']}],component_families:[],unknowns:['Exact mesh identity remains unknown.']},
      stages:{synthesis:{cost:{status:'usage_estimate',calculated_nanos:4500000}}}};
    await page.evaluate(()=>refresh());
    assert.ok((await page.locator('#researchStatus').innerText()).includes('unverified candidates'));
    assert.equal(await page.locator('#researchNotes img').count(),0);
    assert.equal(await page.locator('#researchNotes a[href^="javascript:"]').count(),0);
    assert.equal(await page.locator('#researchNotes a[href^="https://en.wikipedia.org/"]').count(),2);
    assert.ok((await page.locator('#researchNotes').innerText()).includes('No geometry pieces have been labeled'));
    jobs[0].research={status:'awaiting_cognitive_provider',sources:[],stages:{}};
    await page.evaluate(()=>refresh());
    assert.ok((await page.locator('#researchStatus').innerText()).includes('connect OpenAI'));
    // Lost response after acceptance is recovered from job state, not resubmitted.
    lost=true;await page.locator('#prompt').fill('Show me a chair');await page.locator('#show').click();
    await page.waitForFunction(()=>sessionStorage.getItem('oryn-object-request')===null && document.querySelector('#object').textContent==='Show me a chair');
    assert.equal(posts.length,2);
    await page.reload();await page.waitForFunction(()=>document.querySelector('#object').textContent==='Show me a chair');
    assert.equal(posts.length,2,'Reload does not resend an accepted request');
    busy=false;jobs[0].status='loaded_on_quest';await page.evaluate(()=>refresh());
    lost=false;reject=true;await page.locator('#prompt').fill('Show me a table');await page.locator('#show').click();
    await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('limit'));
    assert.equal(posts.length,3,'Limit errors are not retried');
    assert.equal(await page.evaluate(()=>sessionStorage.getItem('oryn-object-request')),null,'Definite rejection clears unsent request ID');
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(errors,[]);
    console.log('ORYN_EXPERIENCE_UI_OK one-submit, no approvals, progress, receipt gating, recovery, escaping, mobile');
  } finally {await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1});
