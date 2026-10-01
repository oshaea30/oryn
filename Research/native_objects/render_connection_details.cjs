// Offline inspection only: isolate each declared pair without changing its geometry.
const fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
(async()=>{
 const folder=process.argv[2];if(!folder)throw Error('Experiment output folder required');
 const pkg=JSON.parse(fs.readFileSync(path.join(folder,'package.json'),'utf8'));
 const plan=JSON.parse(fs.readFileSync(path.join(folder,'proposal.json'),'utf8'));
 const ports=new Map(plan.ports.map(p=>[p.id,p.part]));
 const pairs=plan.mates.map(m=>({id:m.id,kind:m.kind,a:ports.get(m.a),b:ports.get(m.b)}));
 if(pairs.length>64)throw Error('Too many connection views');
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const page=await browser.newPage();await page.setContent(fs.readFileSync(path.join(__dirname,'viewer.html'),'utf8'));
  const output=path.join(folder,'connection-views');fs.mkdirSync(output,{recursive:true});
  for(const pair of pairs){
   if(!/^[a-z][a-z0-9_]{0,47}$/.test(pair.id))throw Error('Invalid connection ID');
   const encoded=await page.evaluate(({data,pair})=>{
    pkg={...data,parts:data.parts.filter(p=>p.id===pair.a||p.id===pair.b)};
    if(pkg.parts.length!==2)throw Error('Missing connection parts');
    playing=false;phase=0;zoom=1.3;$('spread').value=0;$('part').replaceChildren(new Option('All',''));
    const sheet=document.createElement('canvas');sheet.width=1800;sheet.height=550;
    const ctx=sheet.getContext('2d');ctx.fillStyle='#15232e';ctx.fillRect(0,0,1800,550);
    const angles=[[.65,.45],[3.8,.45],[.65,1.3]];
    angles.forEach(([a,b],i)=>{yaw=a;pitch=b;draw();ctx.drawImage(canvas,300,0,600,510,i*600,0,600,510);});
    ctx.fillStyle='#eef4f8';ctx.font='17px system-ui';
    ctx.fillText(pair.id+' | '+pair.kind+' | '+pair.a+' + '+pair.b+' | isolated pair, original assembly positions',20,538,1760);
    return sheet.toDataURL('image/png').split(',')[1];
   },{data:pkg,pair});
   fs.writeFileSync(path.join(output,pair.id+'.png'),Buffer.from(encoded,'base64'));
  }
  console.log('Rendered '+pairs.length+' original connection pairs');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1)});
