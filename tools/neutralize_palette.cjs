/* Keep original artwork and remove its legacy violet lighting. */
const fs=require('node:fs'),path=require('node:path');
const sharp=require(process.env.SHARP_MODULE||'sharp');
const root=path.resolve(__dirname,'../web');
function recolor(r,g,b){
  r/=255;g/=255;b/=255;const hi=Math.max(r,g,b),lo=Math.min(r,g,b),diff=hi-lo;
  if(diff<.01||hi===0)return null;
  let h=hi===r?60*((g-b)/diff%6):hi===g?60*((b-r)/diff+2):60*((r-g)/diff+4);if(h<0)h+=360;
  if(h<235||h>335||diff/hi<.10)return null;
  const s=Math.min(.76,diff/hi),c=hi*s,x=c*.7,m=hi-c;
  return [(c+m)*255,(x+m)*255,m*255].map(Math.round);
}
function files(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(path.join(dir,e.name)):[path.join(dir,e.name)]);}
(async()=>{
  let changed=0;
  for(const file of files(path.join(root,'assets')).filter(f=>/\.(jpg|png)$/i.test(f))){
    const {data,info}=await sharp(fs.readFileSync(file)).ensureAlpha().raw().toBuffer({resolveWithObject:true});let count=0;
    for(let i=0;i<data.length;i+=4){const value=recolor(data[i],data[i+1],data[i+2]);if(value){data[i]=value[0];data[i+1]=value[1];data[i+2]=value[2];count++;}}
    if(count){let output=sharp(data,{raw:{width:info.width,height:info.height,channels:4}});output=/\.png$/i.test(file)?output.png():output.jpeg({quality:94,chromaSubsampling:'4:4:4'});fs.writeFileSync(file,await output.toBuffer());changed++;}
  }
  for(const file of files(root).filter(f=>/\.(css|svg)$/i.test(f))){
    const original=fs.readFileSync(file,'utf8');
    let text=original.replace(/#([a-f0-9]{6}|[a-f0-9]{3})(?![a-f0-9])/gi,(full,hex)=>{
      if(hex.length===3)hex=[...hex].map(s=>s+s).join('');const c=recolor(parseInt(hex.slice(0,2),16),parseInt(hex.slice(2,4),16),parseInt(hex.slice(4,6),16));return c?'#'+c.map(v=>v.toString(16).padStart(2,'0')).join(''):full;
    }).replace(/rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)([^)]*)\)/g,(full,r,g,b,tail)=>{const c=recolor(+r,+g,+b);return c?`${full.startsWith('rgba')?'rgba':'rgb'}(${c.join(',')}${tail})`:full;});
    if(text!==original){fs.writeFileSync(file,text);changed++;}
  }
  console.log('Neutral palette applied to',changed,'existing assets/styles');
})().catch(e=>{console.error(e);process.exit(1)});
