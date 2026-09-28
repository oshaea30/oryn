const {test}=require('node:test');
const assert=require('node:assert/strict');
const {guided,readyForTarget}=require('./xr_guided_test.cjs');
const hash='c'.repeat(64);
function fixture(options={}){
  let time=0,notice,runs=0;const notices=[],reports=[];
  const snapshot=()=>({serial:'quest',state:{session:'a'.repeat(32),testGuideAvailable:true,
    context:{ready:true,owner:3,parts:Array(39).fill({}),assetSha256:hash,partsMode:false,isolated:false,selectedPartId:''}}});
  const bridge={request:async r=>{
    if(r.operation==='snapshot'){const s=snapshot();if(options.state)options.state(s,time);return s;}
    if(r.operation==='guide'){notice={...r};notices.push(notice);return {status:'waiting'};}
    if(r.operation==='guide_receipt')return options.noAck?{}:{sequence:notice.sequence,phase:notice.phase};
    throw Error('Unexpected request');
  }};
  return {bridge,client:{},hash,save:async r=>reports.push(JSON.parse(JSON.stringify(r))),now:()=>time,wait:async ms=>{time+=ms;},readyTimeout:15000,
    run:async args=>{runs++;assert.equal(args.owner,3);assert.equal(args.expectedAssetHash,hash);
      assert.ok(time>=5000);await args.progress('Sending explode once');await args.progress('Sending reassemble once');
      return {status:'PASS',actions:[{action:'explode'},{action:'reassemble'}]};},
    notices,reports,count:()=>runs};
}
test('correct target auto-starts once after countdown and acknowledges completion',async()=>{
  const f=fixture();const r=await guided(f);assert.equal(r.status,'PASS');assert.equal(f.count(),1);
  assert.ok(r.testGuide.terminalAcknowledged);assert.equal(f.notices.at(-1).phase,'passed');
  assert.ok(f.notices.some(n=>n.message.includes('Exploding')));
});
test('wrong asset, parts mode and held objects never trigger test actions',async()=>{
  for(const change of [s=>s.state.context.assetSha256='d'.repeat(64),s=>s.state.context.partsMode=true,s=>s.state.context.ready=false]){
    const f=fixture({state:change});const r=await guided(f);assert.equal(r.status,'BLOCKED');assert.equal(f.count(),0);assert.equal(f.notices.at(-1).phase,'blocked');
  }
});
test('display acknowledgement required before test can run',async()=>{
  const f=fixture({noAck:true});const r=await guided(f);assert.equal(r.status,'BLOCKED');assert.equal(f.count(),0);assert.equal(r.testGuide.terminalAcknowledged,false);
});
test('readiness interruption resets countdown and updates headset instruction',async()=>{
  const f=fixture({state:(s,t)=>{if(t>=2000&&t<4000)s.state.context.ready=false;}});await guided(f);
  assert.equal(f.count(),1);const countdown=f.notices.filter((n,i)=>n.message.includes('5 seconds')&&(i===0||f.notices[i-1].message!==n.message));assert.equal(countdown.length,2);
  assert.ok(f.notices.some(n=>n.message.startsWith('Release')));
});
test('app-session change stops the armed test',async()=>{
  const f=fixture({state:(s,t)=>{if(t>=1000)s.state.session='f'.repeat(32);}});assert.equal((await guided(f)).status,'BLOCKED');assert.equal(f.count(),0);
});
test('old build is never eligible',()=>{
  assert.equal(readyForTarget({state:{context:{ready:true,assetSha256:hash}}},hash),false);
});
