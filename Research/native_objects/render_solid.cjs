// Object-only research raster. No external page or room imagery.
const fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
(async()=>{
 const [input,output]=process.argv.slice(2);if(!input||!output)throw Error('package.json and output.png required');
 const data=JSON.parse(fs.readFileSync(input,'utf8'));
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1000}});
  await page.setContent(fs.readFileSync(path.join(__dirname,'viewer.html'),'utf8'));
  const png=await page.evaluate(data=>{
   pkg=data;playing=false;phase=0;$('part').replaceChildren(new Option('All',''));$('spread').value=0;
   const original=pkg,count=4+pkg.parts.length,cols=3,w=480,h=235;
   const sheet=document.createElement('canvas');sheet.width=cols*w;sheet.height=Math.ceil(count/cols)*h;
   const dest=sheet.getContext('2d');dest.fillStyle='#101921';dest.fillRect(0,0,sheet.width,sheet.height);
   function tile(i,label){draw();const x=i%cols*w,y=Math.floor(i/cols)*h;dest.fillStyle='#15232e';dest.fillRect(x,y,w,h);dest.drawImage(canvas,x,y,w,204);dest.fillStyle='#eef4f8';dest.font='14px system-ui';dest.fillText(label,x+8,y+222,w-16);}
   yaw=.65;pitch=.45;tile(0,'Assembled');yaw=3.8;tile(1,'Reverse');yaw=.65;pitch=1.2;tile(2,'Above');pitch=.45;$('spread').value=1;tile(3,'Exploded');$('spread').value=0;
   original.parts.forEach((part,i)=>{pkg={...original,parts:[part]};tile(i+4,part.id+' | isolated, fitted view');});
   return sheet.toDataURL('image/png').split(',')[1];
  },data);
  fs.writeFileSync(output,Buffer.from(png,'base64'));console.log('Rendered '+data.parts.length+' parts');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1)});
