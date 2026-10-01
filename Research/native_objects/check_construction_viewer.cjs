const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1100}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(process.env.ORYN_RESEARCH_URL||'http://127.0.0.1:8775/construction-review-001/');
  await page.waitForFunction(()=>window.orynView?.parts>0);
  const occlusion=await page.evaluate(()=>{
   const saved=pkg,oldYaw=yaw,oldPitch=pitch;yaw=0;pitch=0;
   const far={id:'far',color:[1,0,0],vertices:[[-1,-1,-1],[1,-1,-1],[0,1,-1]],triangles:[0,1,2]};
   const near={id:'near',color:[0,0,1],vertices:[[-1,-1,1],[1,-1,1],[0,1,1]],triangles:[0,1,2]};
   const samples=[];
   for(const parts of [[near,far],[far,near]]){
    pkg={...saved,parts,frames:[]};draw();const pixel=new Uint8Array(4);gl.readPixels(600,255,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);samples.push([...pixel]);
   }
   pkg=saved;yaw=oldYaw;pitch=oldPitch;draw();return {samples,error:gl.getError()};
  });
  assert.equal(occlusion.error,0);assert.ok(occlusion.samples.every(pixel=>pixel[2]>pixel[0]+100));
  const cases=await page.locator('#case option').evaluateAll(options=>options.map(x=>x.value).filter(x=>x.endsWith('-coarse')));
  const output=process.env.ORYN_SCREENSHOT_DIR||'/private/tmp/oryn-construction-review';fs.mkdirSync(output,{recursive:true});
  const records=[];
  for(const name of cases){
   await page.locator('#case').selectOption(name);await page.waitForFunction(n=>window.orynView.case===n,name.replace(/-coarse$/,''));
   const ids=await page.locator('#part option').evaluateAll(options=>options.map(x=>x.value).filter(Boolean));
   const selected=ids[ids.length-1];await page.locator('#part').selectOption(selected);
   await page.locator('#spread').fill('0.65');await page.locator('#spread').dispatchEvent('input');
   const fine=name.replace(/-coarse$/,'-fine');await page.locator('#case').selectOption(fine);
   await page.waitForFunction(()=>window.orynView.resolution===24);
   assert.equal(await page.locator('#part').inputValue(),selected);assert.equal(await page.locator('#spread').inputValue(),'0.65');
   assert.equal(await page.locator('#motion').isDisabled(),true);
   await page.locator('#reset').click();assert.equal(await page.locator('#part').inputValue(),'');
   assert.equal(await page.locator('#spread').inputValue(),'0');
   const sheet=await page.evaluate(()=>{
    const original=pkg,originalYaw=yaw,originalPitch=pitch;
    const tiles=3+original.parts.length,columns=3,w=480,h=235;
    const sheet=document.createElement('canvas');sheet.width=columns*w;sheet.height=Math.ceil(tiles/columns)*h;
    const dest=sheet.getContext('2d');dest.fillStyle='#101921';dest.fillRect(0,0,sheet.width,sheet.height);
    function tile(index,label){draw();const x=index%columns*w,y=Math.floor(index/columns)*h;
     dest.fillStyle='#15232e';dest.fillRect(x,y,w,h);dest.drawImage(canvas,x,y,w,204);
     dest.fillStyle='#e5eff4';dest.font='14px system-ui';dest.fillText(label,x+10,y+223,w-20);}
    yaw=.65;pitch=.45;tile(0,'Assembled');yaw=3.8;tile(1,'Reverse');yaw=.65;$('spread').value=1;tile(2,'Exploded');$('spread').value=0;
    original.parts.forEach((part,i)=>{pkg={...original,parts:[part]};tile(i+3,part.id+' · isolated, fitted view');});
    pkg=original;yaw=originalYaw;pitch=originalPitch;draw();return sheet.toDataURL('image/png').split(',')[1];
   });
   fs.writeFileSync(output+'/'+name.replace(/-coarse$/,'')+'.png',Buffer.from(sheet,'base64'));
   records.push({case:name.replace(/-coarse$/,''),parts:ids.length,selection_preserved:true,spread_preserved:true,reset_passed:true,motion_disabled:true});
  }
  assert.deepEqual(errors,[]);fs.writeFileSync(output+'/browser-check.json',JSON.stringify({records,errors,occlusion},null,2));console.log(JSON.stringify(records));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
