/* This source is inserted inside the explorer closure by build_sl2z.py. */
const appearance={palette:"rainbow",region:0.55,depth:0.65,fills:true,lines:true,glow:true};
const indexByKey=new Map();
tiles.forEach((tile,i)=>{tile.id=i;indexByKey.set(key(tile.g),i);});
let gradientDefinitions=[],colourTable=[],colourStats={},playTimer=null,colourTimer=null;
const selectionHistory=[];
const extra=id=>root.querySelector("#sl2z-"+id);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const pack=c=>(c[0]<<16)|(c[1]<<8)|c[2];
const hex=c=>"#"+c.map(v=>Math.round(clamp(v,0,255)).toString(16).padStart(2,"0")).join("");
const mix=(a,b,t)=>a.map((v,i)=>v*(1-t)+b[i]*t);
function hashText(text) {
  let h=2166136261;
  for(let i=0;i<text.length;i++)h=Math.imul(h^text.charCodeAt(i),16777619);
  return h>>>0;
}
function hsv(h,s,v) {
  h=((h%1)+1)%1;
  const j=Math.floor(h*6),f=h*6-j,p=v*(1-s),q=v*(1-f*s),t=v*(1-(1-f)*s);
  return [[v,t,p],[q,v,p],[p,v,t],[p,q,v],[t,p,v],[v,p,q]][j%6].map(x=>Math.round(x*255));
}
function rawColour(tile) {
  const [x,y]=act(tile.g,[0.137,1.63]),den=x*x+(y+1)*(y+1);
  const u=(x*x+y*y-1)/den,v=-2*x/den;
  const r=Math.min(.999999999999,Math.hypot(u,v));
  const radius=1-Math.exp(-2*Math.atanh(r)/3),angle=Math.atan2(v,u);
  const phase=hashText(key(tile.g))/4294967296,phase2=hashText("s:"+key(tile.g))/4294967296;
  const d=tile.depth/18,A=appearance.depth,B=appearance.region;
  let h;
  if(appearance.palette==="cyan")h=.50+.09*A*d+.025*Math.sin(angle)+.015*Math.cos(angle)+.09*B*(phase-.5);
  else if(appearance.palette==="orchid")h=.71+.14*A*d+.04*Math.sin(angle)+.025*Math.cos(angle)+.12*B*(phase-.5);
  else h=.53+.62*A*d+.10*Math.sin(angle)+.055*Math.cos(angle)+.12*radius+.26*B*(phase-.5);
  const s=clamp(.40+.14*radius+.16*B*(phase2-.5),.22,.72);
  const value=clamp(.85-.16*A*d-.11*radius+.13*B*(phase-.5),.48,.91);
  return hsv(h,s,value);
}
const offsets=[];
for(let a=-4;a<=4;a++)for(let b=-4;b<=4;b++)for(let c=-4;c<=4;c++)offsets.push([a,b,c]);
offsets.sort((a,b)=>a.reduce((s,v)=>s+v*v,0)-b.reduce((s,v)=>s+v*v,0)||a[0]-b[0]||a[1]-b[1]||a[2]-b[2]);
function uniqueColour(rgb,used) {
  for(const delta of offsets) {
    const c=rgb.map((v,i)=>v+delta[i]);
    if(c.some(v=>v<0||v>255))continue;
    const k=pack(c);
    if(!used.has(k)){used.add(k);return c;}
  }
  let k=pack(rgb);
  while(used.has(k))k=(k+1)&0xffffff;
  used.add(k);return [k>>>16,(k>>>8)&255,k&255];
}
const toLinear=v=>v/255<=.04045?v/3294.6:((v/255+.055)/1.055)**2.4;
const toSrgb=v=>255*(v<=.0031308?12.92*v:1.055*v**(1/2.4)-.055);
function rebuildColours() {
  const used=new Set();let collisions=0,maxCorrection=0;
  colourTable=tiles.map(tile=>{
    const raw=rawColour(tile),rgb=uniqueColour(raw,used);
    if(raw.some((v,i)=>v!==rgb[i]))collisions++;
    maxCorrection=Math.max(maxCorrection,...raw.map((v,i)=>Math.abs(v-rgb[i])));
    return {rgb,fill:hex(rgb),core:hex(mix(rgb,[234,245,252],.12))};
  });
  tiles.forEach(tile=>{
    const c=colourTable[tile.id],neighbours=[c.rgb];
    for(const gen of [S,T,Ti]){
      const id=indexByKey.get(key(mul(tile.g,gen)));
      if(id!==undefined)neighbours.push(colourTable[id].rgb);
    }
    const mean=[0,1,2].map(i=>toSrgb(neighbours.reduce((sum,rgb)=>sum+toLinear(rgb[i]),0)/neighbours.length));
    c.edge=hex(mix(mean,[220,239,250],.22));
    c.rim=hex(mix(mix(c.rgb,mean,.32),[7,13,24],.28));
  });
  colourStats={unique:used.size,collisionsResolved:collisions,maxChannelCorrection:maxCorrection};
}
function paintTile(tile,geo,d) {
  if(!appearance.fills)return '<path d="'+d+'" fill="none"/>';
  const c=colourTable[tile.id];
  const size=Math.min((geo.xmax-geo.xmin)*scale,Number.isFinite(geo.ymax)?geo.ymax*scale:ph);
  let fill=c.fill;
  if(size>9) {
    const p=act(tile.g,[.137,1.63]),radius=(geo.cusp?Math.max(geo.xmax-geo.xmin,geo.ymax)*.9:1.9)*scale;
    const id="cell-colour-"+tile.id;
    gradientDefinitions.push('<radialGradient id="'+id+'" gradientUnits="userSpaceOnUse" cx="'+f(X(p[0]))+'" cy="'+f(Y(p[1]))+'" r="'+f(radius)+'"><stop offset="0" stop-color="'+c.core+'"/><stop offset=".48" stop-color="'+c.fill+'"/><stop offset="1" stop-color="'+c.rim+'"/></radialGradient>');
    fill="url(#"+id+")";
  }
  return '<path data-tile="'+tile.id+'" d="'+d+'" fill="'+fill+'" fill-opacity=".72"/>';
}
function rememberSelection() {
  selectionHistory.push({g:selected.slice(),depth,camera:{...camera}});
  if(selectionHistory.length>80)selectionHistory.shift();
}
function setDepth(value) {
  depth=clamp(Math.round(value),0,18);slider.value=depth;
  const tile=lookup.get(key(selected));
  if(tile&&tile.depth>depth)selected=I.slice();
  schedule();
}
function selectIndex(id) {
  const available=tiles.filter(t=>t.depth<=depth).length;
  id=clamp(Math.round(id),0,available-1);
  rememberSelection();selected=tiles[id].g.slice();
  const p=act(selected,[.137,1.63]);
  if(p[0]<xmin+.08*camera.span||p[0]>xmin+.92*camera.span)camera.center=p[0];
  if(p[1]<camera.ymin||p[1]>ymax)camera.ymin=Math.max(0,p[1]-.45*(ymax-camera.ymin));
  schedule();
}
function nextRegion(delta) {
  selectIndex((indexByKey.get(key(selected))||0)+delta);
}
function syncExtraControls() {
  const id=indexByKey.get(key(selected)),count=tiles.filter(t=>t.depth<=depth).length;
  extra("region").max=count-1;
  extra("region").value=id===undefined?0:Math.min(count-1,id);
  extra("region-count").textContent=id===undefined?"独立选区":(id+1).toLocaleString()+" / "+count.toLocaleString();
  extra("previous").disabled=id===0;
  extra("next").disabled=id===count-1;
  extra("less").disabled=depth===0;extra("more").disabled=depth===18;
  extra("undo").disabled=selectionHistory.length===0;
  root.dataset.depth=String(depth);root.dataset.palette=appearance.palette;
  root.dataset.uniqueColours=String(colourStats.unique);
}
function stopPlay() {
  if(playTimer!==null)clearInterval(playTimer);
  playTimer=null;extra("play").textContent="自动展开";extra("play").setAttribute("aria-pressed","false");
}
function play() {
  if(playTimer!==null){stopPlay();return;}
  if(depth===18)setDepth(0);
  extra("play").textContent="暂停展开";extra("play").setAttribute("aria-pressed","true");
  playTimer=setInterval(()=>{setDepth(depth+1);if(depth===18)stopPlay();},900);
}
function resetView() {
  rememberSelection();stopPlay();selected=I.slice();
  camera.center=0;camera.ymin=0;camera.span=host.clientWidth<480?3.1:5.4;
  setDepth(16);
}
function focusRegion() {
  const geo=geometry(selected);
  camera.center=(geo.xmin+geo.xmax)/2;camera.ymin=0;
  camera.span=geo.cusp?clamp(Math.max((geo.xmax-geo.xmin)*2.3,geo.ymax*pw/ph*1.4),.025,15):2.6;
  schedule();
}
function snapshotSVG() {
  const style='<style>text{font-family:system-ui,sans-serif;font-size:12px;fill:#dceaf4}.sl2z-fills{stroke:none}.sl2z-structure{fill:none;stroke-width:.65;stroke-opacity:.38}.sl2z-frame{fill:none;stroke:#3a536b;stroke-width:1}.sl2z-standard{fill:none;stroke:#e8c67b;stroke-width:1.5}.sl2z-selection{fill:#7ec8e5;fill-opacity:.12;stroke:#e5f4ff;stroke-width:2}.sl2z-vertex{fill:#8dc9df;fill-opacity:.65}.sl2z-tick{stroke:#8397ab;stroke-width:.8}.sl2z-point{fill:#e4f3fc;stroke:#0b1525;stroke-width:1.5}</style>';
  const inner=svg.innerHTML.replace(/var\(--background\)/g,"#0b1525").replace(/var\(--viz-series-2\)/g,"#e8c67b");
  return '<svg xmlns="'+NS+'" width="'+width+'" height="'+height+'" viewBox="0 0 '+width+' '+height+'"><rect width="100%" height="100%" fill="#0b1525"/>'+style+inner+"</svg>";
}
function download(blob,name) {
  const url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download=name;document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1200);
}
function exportSVG() {download(new Blob([snapshotSVG()],{type:"image/svg+xml;charset=utf-8"}),"SL2Z_H_N"+depth+"_"+appearance.palette+".svg");}
function exportPNG() {
  const url=URL.createObjectURL(new Blob([snapshotSVG()],{type:"image/svg+xml;charset=utf-8"})),img=new Image();
  img.onload=()=>{
    const canvas=document.createElement("canvas");canvas.width=Math.round(width*3);canvas.height=Math.round(height*3);
    canvas.getContext("2d").drawImage(img,0,0,canvas.width,canvas.height);URL.revokeObjectURL(url);
    canvas.toBlob(blob=>{if(blob)download(blob,"SL2Z_H_N"+depth+"_"+appearance.palette+".png");},"image/png");
  };
  img.onerror=()=>URL.revokeObjectURL(url);img.src=url;
}
extra("previous").addEventListener("click",()=>nextRegion(-1));
extra("next").addEventListener("click",()=>nextRegion(1));
extra("region").addEventListener("input",e=>selectIndex(Number(e.target.value)));
extra("less").addEventListener("click",()=>{stopPlay();setDepth(depth-1);});
extra("more").addEventListener("click",()=>{stopPlay();setDepth(depth+1);});
extra("play").addEventListener("click",play);
extra("reset").addEventListener("click",resetView);
extra("focus").addEventListener("click",focusRegion);
extra("undo").addEventListener("click",()=>{
  const old=selectionHistory.pop();if(!old)return;
  selected=old.g;depth=old.depth;Object.assign(camera,old.camera);slider.value=depth;schedule();
});
extra("export-svg").addEventListener("click",exportSVG);
extra("export-png").addEventListener("click",exportPNG);
extra("palette").addEventListener("change",e=>{appearance.palette=e.target.value;rebuildColours();schedule();});
for(const prop of ["region","depth"])extra(prop+"-mix").addEventListener("input",e=>{
  appearance[prop]=Number(e.target.value)/100;
  extra(prop+"-value").textContent=e.target.value+"%";
  clearTimeout(colourTimer);colourTimer=setTimeout(()=>{rebuildColours();schedule();},60);
});
for(const prop of ["fills","lines","glow"])extra(prop).addEventListener("click",()=>{
  appearance[prop]=!appearance[prop];extra(prop).setAttribute("aria-pressed",String(appearance[prop]));schedule();
});
document.addEventListener("keydown",e=>{
  if(e.target.closest("input,select,textarea,button,summary")||e.altKey||e.ctrlKey||e.metaKey)return;
  const k=e.key.length===1?e.key.toLowerCase():e.key;
  const actions={
    s:()=>root.querySelector('[data-generator="S"]').click(),
    t:()=>root.querySelector('[data-generator="'+(e.shiftKey?"Ti":"T")+'"]').click(),
    ArrowLeft:()=>nextRegion(-1),ArrowRight:()=>nextRegion(1),
    "[":()=>setDepth(depth-1),"]":()=>setDepth(depth+1),
    "+":()=>extra("in").click(),"=":()=>extra("in").click(),"-":()=>extra("out").click(),
    f:focusRegion,"0":resetView," ":play,
    c:()=>extra("fills").click(),l:()=>extra("lines").click(),g:()=>extra("glow").click()
  };
  if(actions[k]){e.preventDefault();actions[k]();}
});
window.addEventListener("pagehide",()=>{stopPlay();clearTimeout(colourTimer);});
window.Sl2zExplorer={
  getState:()=>({selected:selected.slice(),depth,camera:{...camera},appearance:{...appearance},colourStats:{...colourStats},visible:Number(root.dataset.visible)}),
  selectIndex,setDepth,rebuildColours,snapshotSVG,stopPlay,
  colours:()=>colourTable.map(c=>c.fill),
  math:{I,S,T,Ti,mul,inv,act,reduce,geometry},tiles
};
rebuildColours();
