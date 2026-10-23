const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {JSDOM}=require("jsdom");
const html=fs.readFileSync(path.join(__dirname,"../sl2z/index.html"),"utf8");
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
function setup(width=900){
 const dom=new JSDOM(html,{runScripts:"outside-only",pretendToBeVisual:true});
 const w=dom.window;
 Object.defineProperty(w.HTMLElement.prototype,"clientWidth",{get(){return width;}});
 w.ResizeObserver=class{observe(){}};
 w.SVGElement.prototype.setPointerCapture=function(){};
 w.SVGElement.prototype.getBoundingClientRect=function(){return{left:0,top:0,width:Number(this.getAttribute("width")),height:Number(this.getAttribute("height"))};};
 w.eval(code);
 return{w,dom,app:w.Sl2zExplorer,el:id=>w.document.getElementById("sl2z-"+id)};
}
const settle=()=>new Promise(r=>setTimeout(r,90));
test("all matrices, domain reduction, group relations and unique colours",()=>{
 const{w,dom,app}=setup();
 try{
  assert.equal(app.tiles.length,35416);
  assert.equal(new Set(app.colours()).size,35416);
  const{I,S,T,mul,inv,act,reduce}=app.math;
  assert.deepEqual(Array.from(mul(S,S)),Array.from(I));
  const st=mul(S,T);assert.deepEqual(Array.from(mul(st,mul(st,st))),Array.from(I));
  for(const tile of app.tiles){
   const[a,b,c,d]=tile.g.map(BigInt);
   assert.equal(a*d-b*c,1n);
   assert.deepEqual(Array.from(mul(tile.g,inv(tile.g))),Array.from(I));
   assert.deepEqual(Array.from(reduce(act(tile.g,[.137,1.63]))),Array.from(tile.g));
  }
 }finally{app.stopPlay();w.close();}
});
test("controls, colour presets, stable depth colours and vector export",async()=>{
 const{w,dom,app,el}=setup(900);
 try{
  const initial=app.colours().slice(0,100);
  el("next").click();await settle();
  assert.deepEqual(Array.from(app.getState().selected),[0,-1,1,0]);
  w.document.querySelector('[data-generator="T"]').click();await settle();
  assert.deepEqual(Array.from(app.getState().selected),[1,-1,1,0]);
  el("undo").click();await settle();
  assert.deepEqual(Array.from(app.getState().selected),[0,-1,1,0]);
  app.setDepth(4);await settle();app.selectIndex(35);await settle();
  assert.deepEqual(Array.from(app.colours().slice(0,100)),Array.from(initial));
  assert.equal(app.getState().depth,4);
  el("reset").click();await settle();
  w.document.body.dispatchEvent(new w.KeyboardEvent("keydown",{key:"t",shiftKey:true,bubbles:true,cancelable:true}));
  await settle();assert.deepEqual(Array.from(app.getState().selected),[1,-1,0,1]);
  const span=app.getState().camera.span;el("in").click();await settle();
  assert(app.getState().camera.span<span);
  el("fills").click();await settle();assert.equal(app.getState().appearance.fills,false);
  el("fills").click();await settle();
  for(const preset of["cyan","orchid","rainbow"]){
   el("palette").value=preset;el("palette").dispatchEvent(new w.Event("change",{bubbles:true}));await settle();
   assert.equal(new Set(app.colours()).size,35416);
   assert.equal(app.getState().appearance.palette,preset);
  }
  el("region-mix").value=80;el("region-mix").dispatchEvent(new w.Event("input",{bubbles:true}));await settle();
  assert.equal(app.getState().appearance.region,.8);
  el("depth-mix").value=90;el("depth-mix").dispatchEvent(new w.Event("input",{bubbles:true}));await settle();
  assert.equal(app.getState().appearance.depth,.9);
  const exported=app.snapshotSVG();
  assert(!/NaN|Infinity|var\(--/.test(exported));
  assert(exported.includes("<radialGradient"));
  const xml=new JSDOM(exported,{contentType:"image/svg+xml"});xml.window.close();
  app.setDepth(17);await settle();el("play").click();
  await new Promise(r=>setTimeout(r,1030));assert.equal(app.getState().depth,18);
  assert.equal(el("play").getAttribute("aria-pressed"),"false");
 }finally{app.stopPlay();w.close();}
});
test("phone-width coordinate layouts and control identifiers",()=>{
 for(const width of[320,390]){
  const{w,app,el}=setup(width);
  try{
   const svg=w.document.querySelector(".sl2z-diagram");
   assert.equal(Number(svg.getAttribute("width")),width);
   assert(Number(w.document.getElementById("sl2z-upper-half-plane").dataset.visible)>100);
   const ids=Array.from(w.document.querySelectorAll("[id]"),n=>n.id);
   assert.equal(ids.length,new Set(ids).size);
  }finally{app.stopPlay();w.close();}
 }
});
