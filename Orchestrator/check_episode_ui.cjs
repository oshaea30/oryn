// Fixture-only history and review tests. No real provider or user reviews.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1000}}),id='a'.repeat(64),gid='b'.repeat(64)+':island:001';
  const posts=[],errors=[],dispatches=[],assessments=[];let lose=false;
  const record={id,status:'waiting_policy',candidate_revision_id:'c'.repeat(64),events:[{id:'opened',sequence:1,kind:'episode_opened',created_at:1,payload:{question:'<img src=x> Untrusted query'}}]};
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url());
   if(url.pathname==='/investigation-episode')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'investigation_episode.html'),'utf8')});
   if(url.pathname==='/api/episode')return route.fulfill({json:record});
   if(url.pathname==='/api/state')return route.fulfill({json:{token:'fixture-token'}});
   if(url.pathname==='/api/assess-candidates'){
    assessments.push(request.postDataJSON());assert.equal(request.headers()['x-oryn-token'],'fixture-token');
    record.assessment={status:'running',assessments:[],sources:[]};return route.abort();
   }
   if(url.pathname==='/api/investigate-episode'){
    dispatches.push(request.postDataJSON());record.status='running';
    assert.equal(request.headers()['x-oryn-token'],'fixture-token');
    return route.fulfill({json:{status:'running',dispatched:true}});
   }
   if(url.pathname==='/api/episode-review'){
    const body=request.postDataJSON();posts.push(body);
    assert.equal(request.headers()['x-oryn-token'],'fixture-token');
    record.events.push({id:'review-'+posts.length,sequence:record.events.length+1,kind:'human_review',created_at:2,payload:body.review});
    if(lose)return route.abort();return route.fulfill({json:{event_id:'review-'+posts.length}});
   }
   return route.abort();
  });
  await page.goto('http://127.0.0.1:8765/investigation-episode?id='+id);
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Prepared locally'));
  assert.equal(await page.locator('#reviewArea').isVisible(),false);assert.equal(posts.length,0);
  assert.equal(await page.locator('#events img').count(),0);
  assert.equal(await page.locator('#investigate').isEnabled(),false);
  record.vision={connected:true,policy_ready:true,busy:false};
  record.events.push({id:'observed',sequence:2,kind:'observations_prepared',created_at:1,payload:{images:[]}});
  await page.locator('#refresh').click();await page.waitForFunction(()=>!document.querySelector('#investigate').disabled);
  await page.locator('#investigate').click();await page.waitForFunction(()=>document.querySelector('#status').textContent==='running');
  assert.equal(dispatches.length,1);assert.equal(dispatches[0].episode_id,id);
  assert.equal(await page.locator('#investigate').isEnabled(),false);
  record.status='completed';record.events.push({id:'published',sequence:2,kind:'candidates_persisted',created_at:2,payload:{mappings:[{geometry_id:gid,candidate_name:'<img src=x> Fixture candidate',rationale:'Unverified fixture.'}]}});
  await page.locator('#refresh').click();await page.locator('#reason').fill('Reference mismatch.');await page.locator('#save').click();
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Review event saved'));
  assert.equal(posts.length,1);assert.equal(posts[0].review.previous_review_id,null);
  assert.equal(await page.locator('#candidates img').count(),0);
  await page.locator('#decision').selectOption('corrected');await page.locator('#replacement').fill('Fixture rocker arm');
  await page.locator('#reason').fill('New observation, still a candidate.');lose=true;await page.locator('#save').click();
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Saved review confirmed'));
  assert.equal(posts.length,2);assert.equal(posts[1].review.previous_review_id,'review-1');
  assert.match(await page.locator('#candidates').innerText(),/Fixture rocker arm/);
  assert.equal(record.events.filter(e=>e.kind==='human_review').length,2);
  await page.locator('#assess').click();await page.waitForFunction(()=>document.querySelector('#assessmentStatus').textContent==='running');
  assert.equal(assessments.length,1);assert.equal(await page.locator('#assess').isEnabled(),false);
  record.assessment={status:'completed',assessments:[{geometry_id:gid,outcome:'insufficient_evidence',observation:'<img src=x> Fixture observation',comparison:'Not enough evidence.',missing_evidence:['An exact reference.'],evidence:[{source_id:'r1',quote:'Fixture quote.'}]}],sources:[{id:'r1',title:'<img src=x> Reference',url:'https://example.org/reference',source_type:'test_fixture'},{id:'bad',title:'Unsafe',url:'javascript:alert(1)',source_type:'test_fixture'}]};
  await page.locator('#refresh').click();await page.waitForFunction(()=>document.querySelector('#assessmentStatus').textContent==='completed');
  assert.match(await page.locator('#assessments').innerText(),/Still unknown/);
  assert.equal(await page.locator('#assessments img').count(),0);assert.equal(await page.locator('#references img').count(),0);
  assert.equal(await page.locator('#references a').count(),1);assert.equal(assessments.length,1);
  assert.match(await page.locator('#candidates').innerText(),/Fixture rocker arm/);
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.deepEqual(errors,[]);
  console.log('ORYN_EPISODE_UI_OK waiting-policy, escaping, append-only review, correction, lost-response recovery, mobile');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
