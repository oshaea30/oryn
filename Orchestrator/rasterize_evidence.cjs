// Object-only rasterizer: stdin contains checksum-validated generated SVGs.
// No URL, browser context, room capture, page screenshot, credentials or network.
const {chromium}=require('playwright');
let input='';process.stdin.setEncoding('utf8');
process.stdin.on('data',part=>{input+=part;if(input.length>50*1024*1024)process.exit(2);});
process.stdin.on('end',async()=>{
  let browser;
  try{
    const value=JSON.parse(input);
    if(!Array.isArray(value.views)||!value.views.length||value.views.length>3)throw Error();
    const options={headless:true};
    if(process.env.ORYN_CHROMIUM)options.executablePath=process.env.ORYN_CHROMIUM;
    browser=await chromium.launch(options);
    const page=await browser.newPage({viewport:{width:1000,height:540},deviceScaleFactor:1});
    await page.route('**/*',route=>route.abort());
    await page.setContent('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'"><style>body{margin:0}img{display:block;width:1000px;height:540px}</style><img id="object" alt="Object geometry evidence">');
    const images=[];
    for(const svg of value.views){
      if(typeof svg!=='string'||svg.length>16*1024*1024)throw Error();
      await page.evaluate(async uri=>{const img=document.getElementById('object');img.src=uri;await img.decode();},'data:image/svg+xml;base64,'+Buffer.from(svg).toString('base64'));
      const png=await page.locator('#object').screenshot({type:'png',timeout:10000});
      if(png.length>3*1024*1024)throw Error();
      images.push(png.toString('base64'));
    }
    process.stdout.write(JSON.stringify({images}));
  }catch{process.stderr.write('Local object rasterization failed.');process.exitCode=1;}
  finally{if(browser)await browser.close();}
});
