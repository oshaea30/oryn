#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {randomUUID}=require('node:crypto');
const {McpClient}=require('./xr_inspection.cjs');
const {UsbBridge,runAssemblyTest}=require('./xr_assembly_test.cjs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));

function readyForTarget(snapshot,hash){
  const c=snapshot?.state?.context;
  return snapshot?.state?.testGuideAvailable===true && c?.ready===true && c.assetSha256===hash &&
    Number.isInteger(c.owner)&&c.owner>0 && c.parts?.length===39 && !c.partsMode && !c.isolated && c.selectedPartId==='';
}
function instruction(snapshot,hash){
  const c=snapshot?.state?.context;
  if(c?.assetSha256!==hash)return 'Grab the newly prepared drone, then release.\nWaiting for the correct model selection.';
  if(c.partsMode||c.isolated||c.selectedPartId)return 'Reassemble the drone first.\nSelect the whole model, then release.';
  return 'Release the drone and relax both hands.\nKeep ORYN open. The test will start shortly.';
}
function blockedText(reason){
  const safe=String(reason||'Test could not complete.').replace(/[<>\x00-\x1f]/g,' ').slice(0,120);
  const words=safe.split(/\s+/);const lines=[''];
  for(const word of words){if((lines.at(-1)+' '+word).length>43)lines.push(word);else lines[lines.length-1]+=(lines.at(-1)?' ':'')+word;}
  return lines.slice(0,3).join('\n')+'\nStopped. You can remove the headset.';
}

async function guided({bridge,client,hash,save,wait=sleep,now=Date.now,readyTimeout=300000,run=runAssemblyTest}){
  const id=randomUUID().replaceAll('-','');
  let serial,session,sequence=0,phase='ready',message='',heartbeat,displayError,chain=Promise.resolve(),report;
  const publish=()=>{
    const notice={operation:'guide',id,serial,session,sequence:++sequence,phase,message};
    const task=chain.then(async()=>{
      if(displayError)throw displayError;
      await bridge.request(notice);
      for(let n=0;n<8;n++){
        const ack=await bridge.request({operation:'guide_receipt',id,serial,session});
        if(ack.sequence===notice.sequence&&ack.phase===notice.phase)return;
        await wait(200);
      }
      throw Error('Headset did not acknowledge test instructions; no further action.');
    });
    chain=task.catch(e=>{displayError=e;});return task;
  };
  const show=async(p,m)=>{phase=p;message=m;await publish();};
  const snapshot=async()=>{
    const s=await bridge.request({operation:'snapshot'});
    if(session&&(s.serial!==serial||s.state.session!==session))throw Error('Headset session changed; test stopped.');
    return s;
  };
  try{
    if(!/^[a-f0-9]{64}$/.test(hash))throw Error('Explicit prepared-asset checksum required.');
    const opening=now();let state;
    while(!state){
      try{state=await snapshot();}catch(error){if(now()-opening>=readyTimeout)throw error;await wait(1000);}
    }
    serial=state.serial;session=state.state.session;
    if(!state.state.testGuideAvailable)throw Error('Install the development build with the headset test guide first.');
    await show('ready',instruction(state,hash));
    const started=now();let stableSince=null,owner=null,lastRefresh=now();
    while(true){
      if(now()-started>readyTimeout)throw Error('Ready window expired. No test actions were started.');
      state=await snapshot();
      if(readyForTarget(state,hash)){
        if(owner!==state.state.context.owner){stableSince=null;owner=state.state.context.owner;}
        if(stableSince===null){stableSince=now();await show('ready','Correct drone selected. Hands off.\nTesting begins after 5 seconds of readiness.');lastRefresh=now();}
        if(now()-stableSince>=5000)break;
      }else{
        stableSince=null;const next=instruction(state,hash);
        if(next!==message){await show('ready',next);lastRefresh=now();}
      }
      if(now()-lastRefresh>=3000){await publish();lastRefresh=now();}
      await wait(500);
    }
    await show('testing','Hands off. Measuring all 39 parts.\nThe drone will explode, then reassemble.');
    heartbeat=setInterval(()=>{publish().catch(()=>{});},4000);
    report=await run({client,bridge,execute:true,owner,expectedAssetHash:hash,save,
      progress:async text=>{
        if(displayError)throw displayError;
        if(text.startsWith('Sending explode'))await show('testing','Hands off. Exploding the drone now.\nChecking every geometric piece.');
        if(text.startsWith('Sending reassemble'))await show('testing','Hands off. Reassembling the drone now.\nChecking its original positions.');
      }});
    clearInterval(heartbeat);heartbeat=null;
    if(displayError)throw displayError;
    const passed=report.status==='PASS';
    await show(passed?'passed':report.status==='FAIL'?'failed':'blocked',passed?
      '39 parts exploded and returned correctly.\nTesting finished. You can remove the headset.':
      blockedText(report.message||report.recovery||'Part verification did not pass.'));
    report.testGuide={id,terminalAcknowledged:true};await save(report);return report;
  }catch(error){
    if(heartbeat)clearInterval(heartbeat);
    let notified=false;
    if(session&&!displayError){try{await show('blocked',blockedText(error.message));notified=true;}catch{}}
    if(report){report.verificationStatus=report.status;report.status='BLOCKED';}
    report=report||{status:'BLOCKED',actions:[],message:error.message};
    report.testGuide={id,terminalAcknowledged:notified,error:error.message};await save(report);return report;
  }finally{if(heartbeat)clearInterval(heartbeat);await chain;}
}

async function main(){
  const args=process.argv.slice(2);
  if(args.length!==3||args[0]!=='--execute'||args[1]!=='--asset-sha256'||!/^[a-f0-9]{64}$/.test(args[2]))throw Error('Usage: xr_guided_test.cjs --execute --asset-sha256 <prepared SHA-256>');
  const root=path.resolve(__dirname,'..','.oryn-inspection');fs.mkdirSync(root,{recursive:true,mode:0o700});
  const folder=fs.mkdtempSync(path.join(root,'guided-')),file=path.join(folder,'report.json');
  const save=r=>{fs.writeFileSync(file+'.partial',JSON.stringify(r,null,2),{mode:0o600});fs.renameSync(file+'.partial',file);};
  const client=new McpClient(path.join(os.homedir(),'meta-xr-operator','meta-xr-operator-mcp-proxy'));
  try{
    const r=await guided({bridge:new UsbBridge('/opt/homebrew/bin/python3'),client,hash:args[2],save});
    console.log(JSON.stringify({status:r.status,message:r.message,guide:r.testGuide,report:file}));process.exitCode=r.status==='PASS'?0:2;
  }finally{client.stop();}
}
if(require.main===module)main().catch(e=>{console.error(e.message);process.exitCode=2});
module.exports={guided,readyForTarget,instruction};
