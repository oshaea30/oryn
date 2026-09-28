'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {runAssemblyTest,angle,MODEL} = require('./xr_assembly_test.cjs');
const clone = value=>JSON.parse(JSON.stringify(value));

function fixture(options={}) {
  const model=options.owner?'Oryn 39-part model '+options.owner:MODEL;
  let factor=1, token=0, phase='baseline', selected='', isolated=false, partsMode=false;
  const sent=[], polls=[], calls=[];
  const state=()=>({serial:'quest',state:{schema:1,session:'a'.repeat(32),contextToken:String(token).repeat(32),utc:Math.floor(Date.now()/1000),
    context:{owner:options.owner||1,ready:true,partsMode,isolated,selectedPartId:selected,assetSha256:'b'.repeat(64),
      parts:Array.from({length:39},(_,i)=>({partId:(i+1).toString(16).padStart(64,'0'),number:i+1,label:'',revision:0,status:'unidentified',error:''}))}}});
  const bridge={async request(request){
    if(request.operation==='snapshot') return options.state?options.state(state(),phase):state();
    if(request.operation==='resolve') {
      const target={partId:request.number.toString(16).padStart(64,'0'),number:request.number,geometryName:'island_'+String(request.number).padStart(3,'0')};
      return options.resolve?options.resolve(target):target;
    }
    if(request.operation==='apply') {
      sent.push(clone(request));
      if(options.transfer) return {status:options.transfer};
      phase={explode:'exploded',reassemble:'reassembled',select:'selected',isolate:'isolated'}[request.action];
      factor=phase==='exploded'?2.1:1;partsMode=phase!=='reassembled';
      isolated=phase==='isolated';selected=['selected','isolated'].includes(phase)?request.partId:'';token++;
      return {status:'waiting'};
    }
    if(request.operation==='receipt'){polls.push(request.id);return {status:options.receipt||'executed'};}
    throw Error('Unexpected USB call');
  }};
  const roots=['Oryn Workspace','Workspace Panel','OVRCameraRig','Passthrough',model];
  const names=Array.from({length:39},(_,i)=>'Part island_'+String(i+1).padStart(3,'0'));
  const client={async connect(){},async call(name,args={}){
    calls.push(name);let data;
    if(name==='openxr_get_session_info') data={session:{handle:options.session?options.session(phase):'82'},state:{name:'XR_SESSION_STATE_FOCUSED'}};
    else if(name==='openxr_get_instance_info') data={application:{name:'Oryn Workspace'},engine:{name:'Unity'}};
    else if(name==='unity_get_scene_root_objects') data={rootObjects:roots.map(name=>({name,active:true}))};
    else if(name==='unity_get_children') data={children:names.map((name,index)=>{
      const child={name,path:model+'/'+name,active:!isolated||(index+1).toString(16).padStart(64,'0')===selected};
      if(options.child)options.child(child,phase,index+1);
      return child;
    })};
    else if(name==='unity_get_world_pose') {
      const i=names.indexOf(args.path.slice(model.length+1))+1;
      const pose={path:args.path,active:i===0||!isolated||i.toString(16).padStart(64,'0')===selected,position:{x:1+i*.01*factor,y:1+i*.005*factor,z:-2+i*.003*factor},rotation:{x:10,y:250,z:5},scale:{x:.3,y:.3,z:.3}};
      if(options.refuseHidden && !pose.active)throw Error('SDK cannot query hidden transforms');
      if(options.pose) options.pose(pose,phase,i);
      data={matchCount:1,matches:[pose]};
    } else throw Error('Unexpected tool');
    return {content:[{type:'text',text:JSON.stringify(data)}]};
  }};
  return {client,bridge,sent,polls,calls,execute:true,wait:async()=>{}};
}

test('explicit later owner and asset binding never fall back to the old fixture',async()=>{
  const f=fixture({owner:3});
  assert.equal((await runAssemblyTest({...f,owner:3,expectedAssetHash:'b'.repeat(64)})).status,'PASS');
  const wrongHash=fixture({owner:3});
  assert.equal((await runAssemblyTest({...wrongHash,owner:3,expectedAssetHash:'c'.repeat(64)})).status,'BLOCKED');
  assert.equal(wrongHash.sent.length,0);
  const wrongOwner=fixture();
  assert.equal((await runAssemblyTest({...wrongOwner,owner:3,expectedAssetHash:'b'.repeat(64)})).status,'BLOCKED');
  assert.equal(wrongOwner.sent.length,0);
});

test('one confirmed explode/reassemble cycle checks all 39 parts and restores baseline',async()=>{
  const f=fixture(),report=await runAssemblyTest(f);
  assert.equal(report.status,'PASS');assert.deepEqual(f.sent.map(s=>s.action),['explode','reassemble']);
  assert.notEqual(f.sent[0].id,f.sent[1].id);
  assert.equal(report.checks[1].partsChecked,39);assert.equal(report.checks[1].movedParts,39);
  assert.equal(report.checks[2].movedParts,0);assert.match(report.recovery,/verified/);
  assert.ok(f.calls.every(name=>!name.includes('set_')&&!name.includes('capture')));
});
test('without explicit execution no connection or commands',async()=>{
  const f=fixture();f.execute=false;f.client.connect=()=>{throw Error('should not connect');};
  assert.equal((await runAssemblyTest(f)).status,'BLOCKED');assert.equal(f.sent.length,0);assert.equal(f.calls.length,0);
});
test('unsafe or stale initial states block before mutation',async()=>{
  const modifiers=[s=>s.state.context.ready=false,s=>s.state.context.partsMode=true,s=>s.state.context.isolated=true,
    s=>s.state.context.selectedPartId='c'.repeat(64),s=>s.state.context.owner=2,s=>s.state.utc-=20,
    s=>s.state.context.parts.pop(),s=>s.state.context.parts[1]=s.state.context.parts[0]];
  for(const change of modifiers){const f=fixture({state:s=>{change(s);return s;}});assert.equal((await runAssemblyTest(f)).status,'BLOCKED');assert.equal(f.sent.length,0);}
});
test('transfer uncertainty or rejected/uncertain/missing receipt never resends or reassembles blindly',async()=>{
  for(const options of [{transfer:'uncertain'},{receipt:'rejected'},{receipt:'uncertain'},{receipt:'waiting'}]){
    const f=fixture(options),r=await runAssemblyTest(f);assert.equal(r.status,'BLOCKED');assert.equal(f.sent.length,1);assert.ok(f.polls.length<=12);
    assert.match(r.recovery,/pending/);
  }
});
test('changed identity, records, session, selection or focus aborts before next action',async()=>{
  const modifiers=[s=>s.serial='another-quest',s=>s.state.session='c'.repeat(32),s=>s.state.context.assetSha256='d'.repeat(64),
    s=>s.state.context.parts[0].label='changed',s=>s.state.context.ready=false,s=>s.state.context.selectedPartId='e'.repeat(64)];
  for(const change of modifiers){const f=fixture({state:(s,p)=>{if(p==='exploded')change(s);return s;}});assert.equal((await runAssemblyTest(f)).status,'BLOCKED');assert.equal(f.sent.length,1);}
  const f=fixture({session:p=>p==='baseline'?'82':'83'});assert.equal((await runAssemblyTest(f)).status,'BLOCKED');assert.equal(f.sent.length,1);
});
test('context changes while sampling block before action',async()=>{
  let reads=0;const f=fixture({state:s=>{if(++reads===2)s.state.contextToken='f'.repeat(32);return s;}});
  assert.equal((await runAssemblyTest(f)).status,'BLOCKED');assert.equal(f.sent.length,0);
});
test('wrong spread fails even with successful receipts; planned guarded reassembly still runs',async()=>{
  const f=fixture({pose:(p,phase,i)=>{if(phase==='exploded'&&i===5)p.position.x+=.04;}}),r=await runAssemblyTest(f);
  assert.equal(r.status,'FAIL');assert.equal(r.checks[1].failures.length,1);assert.equal(f.sent.length,2);assert.match(r.recovery,/verified/);
});
test('root movement prevents attribution and aborts next command',async()=>{
  const f=fixture({pose:(p,phase,i)=>{if(phase==='exploded'&&i===0)p.position.x+=.03;}});
  assert.equal((await runAssemblyTest(f)).status,'BLOCKED');assert.equal(f.sent.length,1);
});
test('reassembly position, rotation or scale regressions fail independently',async()=>{
  for(const change of [p=>p.position.z+=.03,p=>p.rotation.x+=2,p=>p.scale.y*=1.1]){
    const f=fixture({pose:(p,phase,i)=>{if(phase==='reassembled'&&i===10)change(p);}}),r=await runAssemblyTest(f);
    assert.equal(r.status,'FAIL');assert.equal(r.checks.at(-1).failures.length,1);assert.match(r.recovery,/differs/);
  }
});
test('inactive or missing part is not a successful regression',async()=>{
  const f=fixture({pose:(p,phase,i)=>{if(phase==='exploded'&&i===3)p.active=false;}});
  assert.equal((await runAssemblyTest(f)).status,'FAIL');assert.equal(f.sent.length,2);
});
test('Euler wraparound and gimbal-equivalent rotations compare as orientations',()=>{
  assert.ok(angle({x:0,y:359.99,z:0},{x:0,y:-.01,z:360})<.00001);
  assert.ok(angle({x:90,y:30,z:0},{x:90,y:60,z:30})<.00001);
  assert.ok(Math.abs(angle({x:0,y:0,z:0},{x:0,y:90,z:0})-90)<.00001);
});
test('persist command ID before dispatch; failed report save prevents action',async()=>{
  const f=fixture(),saved=[];
  const original=f.bridge.request;f.bridge.request=async request=>{
    if(request.operation==='apply')assert.ok(saved.some(r=>r.actions.some(a=>a.id===request.id&&a.status==='dispatching')));
    return original(request);
  };
  await runAssemblyTest({...f,save:r=>saved.push(clone(r))});assert.equal(f.sent.length,2);
  const g=fixture();let failed=false;
  const r=await runAssemblyTest({...g,save:()=>{if(!failed){failed=true;throw Error('disk full');}}});
  assert.equal(r.status,'BLOCKED');assert.equal(g.sent.length,0);
});
test('bounded run stops without commands when preflight exhausts budget',async()=>{
  const f=fixture();let clock=Date.now();f.now=()=>{clock+=80000;return clock;};
  assert.equal((await runAssemblyTest(f)).status,'BLOCKED');assert.equal(f.sent.length,0);
});

test('isolation selects the bound part, leaves exactly it active, and restores all 39',async()=>{
  const f=fixture(),r=await runAssemblyTest({...f,test:'isolation',targetNumber:4});
  assert.equal(r.status,'PASS');assert.deepEqual(f.sent.map(s=>s.action),['select','isolate','reassemble']);
  assert.deepEqual(r.checks[2].activeParts,[MODEL+'/Part island_004']);
  assert.equal(r.checks[3].activeParts.length,39);assert.equal(r.checks[2].movedParts,0);
  assert.equal(f.sent[0].partId,'4'.padStart(64,'0'));assert.equal(f.sent[1].partId,f.sent[0].partId);assert.equal(f.sent[2].partId,'');
  assert.match(r.recovery,/verified/);
});
test('isolation geometry bindings must match the requested ID, number and scene',async()=>{
  for(const change of [t=>({...t,partId:'f'.repeat(64)}),t=>({...t,number:2}),t=>({...t,geometryName:'island_999'}),t=>({...t,geometryName:'../secret'})]){
    const f=fixture({resolve:change});assert.equal((await runAssemblyTest({...f,test:'isolation'})).status,'BLOCKED');assert.equal(f.sent.length,0);
  }
});
test('wrong isolated target, extra active parts and none active fail, then restore',async()=>{
  for(const change of [(p,i)=>{p.active=i===2;},(p,i)=>{if(i===2)p.active=true;},p=>{p.active=false;}]){
    const f=fixture({child:(p,phase,i)=>{if(phase==='isolated')change(p,i);},pose:(p,phase,i)=>{if(phase==='isolated'&&i>0)change(p,i);}}),r=await runAssemblyTest({...f,test:'isolation'});
    assert.equal(r.status,'FAIL');assert.equal(r.checks[2].status,'FAIL');assert.equal(f.sent.length,3);assert.match(r.recovery,/verified/);
  }
});
test('active target movement fails; hidden transforms are explicitly unobserved',async()=>{
  const f=fixture({pose:(p,phase,i)=>{if(phase==='isolated'&&i===1)p.position.x+=.1;}});
  assert.equal((await runAssemblyTest({...f,test:'isolation'})).status,'FAIL');
  const g=fixture({refuseHidden:true}),r=await runAssemblyTest({...g,test:'isolation'});
  assert.equal(r.status,'PASS');assert.equal(r.checks[2].hiddenTransforms,'NOT_OBSERVED');
  assert.equal(r.snapshots.isolated.unobservedTransforms.length,38);assert.equal(r.snapshots.isolated.poses.length,2);
});
test('missing hierarchy flags and changing active state block isolation sampling',async()=>{
  const f=fixture({child:(p,phase)=>{if(phase==='isolated')delete p.active;}});
  assert.equal((await runAssemblyTest({...f,test:'isolation'})).status,'FAIL');
  let count=0;const g=fixture({child:(p,phase,i)=>{if(phase==='isolated'&&i===1&&++count>1)p.active=false;}});
  assert.equal((await runAssemblyTest({...g,test:'isolation'})).status,'BLOCKED');
});
test('selection-side transform failure skips isolation and performs guarded restoration',async()=>{
  const f=fixture({pose:(p,phase,i)=>{if(phase==='selected'&&i===3)p.position.x+=.1;}}),r=await runAssemblyTest({...f,test:'isolation'});
  assert.equal(r.status,'FAIL');assert.deepEqual(f.sent.map(s=>s.action),['select','reassemble']);
});
test('changed selected ID or lost focus after selection stops without isolating',async()=>{
  for(const change of [s=>s.state.context.selectedPartId='f'.repeat(64),s=>s.state.context.ready=false]){
    const f=fixture({state:(s,p)=>{if(p==='selected')change(s);return s;}});
    assert.equal((await runAssemblyTest({...f,test:'isolation'})).status,'BLOCKED');assert.equal(f.sent.length,1);
  }
});
test('incomplete restoration of hidden parts is a failure',async()=>{
  const f=fixture({pose:(p,phase,i)=>{if(phase==='reassembled'&&i===3)p.active=false;}}),r=await runAssemblyTest({...f,test:'isolation'});
  assert.equal(r.status,'FAIL');assert.equal(r.checks.at(-1).activeParts.length,38);assert.match(r.recovery,/differs/);
});
test('isolation uncertain delivery never retries or sends cleanup blindly',async()=>{
  const f=fixture(),request=f.bridge.request;
  f.bridge.request=async r=>r.operation==='apply'&&r.action==='isolate'?{status:'uncertain'}:request(r);
  const r=await runAssemblyTest({...f,test:'isolation'});
  assert.equal(r.status,'BLOCKED');assert.deepEqual(r.actions.map(a=>a.action),['select','isolate']);
});
