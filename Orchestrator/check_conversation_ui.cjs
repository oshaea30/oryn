// Mock all application routes; no provider calls or headset operations.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1050,height:1000}}),posts=[],errors=[];
  let result=null,lost=false;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname;
   if(name==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'conversation.html'),'utf8')});
   if(name==='/api/conversation-session')return route.fulfill({json:{token:'fixture',contract:1}});
   if(name==='/api/conversation'){
    const body=route.request().postDataJSON();posts.push(body);
    result={id:body.id,status:'pending',answer:'<img src=x> Opening drone.',action:'show_drone',evidence:[],timing:{interpretation_ms:80}};
    if(lost)return route.abort();return route.fulfill({json:result});
   }
   if(name.startsWith('/api/conversation/'))return route.fulfill({json:result});
   return route.abort();
  });
  await page.goto('http://127.0.0.1:8765/');
  await page.locator('#question').fill('Show me a drone');await page.locator('#send').click();
  await page.waitForFunction(()=>document.querySelector('#status').textContent==='Waiting for Quest…');
  assert.equal(posts.length,1);assert.deepEqual(Object.keys(posts[0]).sort(),['id','question']);
  assert.equal(await page.locator('#send').isDisabled(),true);
  assert.equal(await page.locator('#answer img').count(),0);
  result.status='completed';result.answer='The authored drone is ready.';result.timing.receipt_ms=120;
  await page.evaluate(()=>poll());assert.equal(await page.locator('#send').isDisabled(),false);
  lost=true;await page.locator('#question').fill('Take it apart');await page.locator('#send').click();
  await page.waitForFunction(()=>document.querySelector('#error').textContent.length>0);
  await page.reload();await page.waitForFunction(()=>document.querySelector('#status').textContent==='Waiting for Quest…');
  assert.equal(posts.length,2,'Reload recovers the same request without posting again');
  result.status='rejected';result.answer='Selection changed; ask again.';await page.evaluate(()=>poll());
  await page.locator('#question').fill('Try again');assert.equal(await page.locator('#send').isDisabled(),false);
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('oryn-conversation-pending')),null);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'/private/tmp/oryn-conversation-preview.png',fullPage:true});
  console.log('ORYN_CONVERSATION_UI_OK');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
