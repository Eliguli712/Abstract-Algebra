#!/usr/bin/env python3
"""Build a self-contained offline explorer from the maintained source files."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"sl2z"

def build():
    original=(APP/"base-fragment.html").read_text(encoding="utf-8")
    extra=(APP/"enhancements.js").read_text(encoding="utf-8")
    controls=(APP/"controls.html").read_text(encoding="utf-8")
    css=(APP/"standalone.css").read_text(encoding="utf-8")
    # Keep the original depth counter ID distinct from the colour-control counter.
    controls=controls.replace('id="sl2z-depth-value"','id="sl2z-depth-mix-value"')
    extra=extra.replace('extra(prop+"-value")','extra(prop==="depth"?"depth-mix-value":prop+"-value")')
    original=original.replace('<div class="sl2z-plot"></div>','<div class="sl2z-plot"></div>\n'+controls)
    original=original.replace('展开深度 <span','展开深度（字长） <span')
    original=original.replace('shapes+=\'<path d="\'+d+\'"/>\';','shapes+=paintTile(tile,geo,d);')
    original=original.replace('lines+=\'<path d="\'+d+\'"/>\';','lines+=\'<path d="\'+d+\'" stroke="\'+colourTable[tile.id].edge+\'"/>\';')
    original=original.replace('const seenVertices=new Set();','gradientDefinitions=[];\n    const seenVertices=new Set();')
    original=original.replace('height="\'+ph+\'"/></clipPath></defs>\'+','height="\'+ph+\'"/></clipPath>\'+gradientDefinitions.join("")+\'</defs>\'+')
    original=original.replace("shapes+'</g><g class=\"sl2z-structure\">'+lines+'</g>'+",
        "shapes+'</g>'+(appearance.glow&&appearance.lines?'<g fill=\"none\" stroke-width=\"3\" stroke-opacity=\".065\">'+lines+'</g>':'')+'<g class=\"sl2z-structure\">'+(appearance.lines?lines:'')+'</g>'+")
    original=original.replace('root.querySelector(".sl2z-swatch.selected").parentElement.hidden=!moved;',
        'root.querySelector(".sl2z-swatch.selected").parentElement.hidden=!moved;\n    syncExtraControls();')
    original=original.replace('if (g[1]===-1) return "T⁻¹ℱ";','if (g[1]===-1) return "T⁻¹ℱ";')
    original=original.replace('selected=mul(gen,selected);','rememberSelection();selected=mul(gen,selected);const known=lookup.get(key(selected));if(known&&known.depth>depth){depth=known.depth;slider.value=depth;}')
    original=original.replace('if(z[1]>1e-8){selected=reduce(z);schedule();}','if(z[1]>1e-8){rememberSelection();selected=reduce(z);const hit=lookup.get(key(selected));if(hit&&hit.depth>depth){depth=hit.depth;slider.value=depth;}schedule();}')
    original=original.replace('slider.addEventListener("input",()=>{depth=Number(slider.value);schedule();});',
        'slider.addEventListener("input",()=>{stopPlay();setDepth(Number(slider.value));});')
    original=original.replace('new ResizeObserver(schedule).observe(host);',
        extra+'\n  new ResizeObserver(()=>{if(host.clientWidth!==width)schedule();}).observe(host);')
    assert 'paintTile(tile,geo,d)' in original
    assert 'gradientDefinitions.join("")' in original
    assert 'appearance.glow&&appearance.lines' in original
    # Move scripts to the end of body so the offline document is parsed first.
    scripts=re.findall(r"<script>(.*?)</script>",original,flags=re.S)
    fragment=re.sub(r"<script>.*?</script>","",original,flags=re.S)
    document='''<!doctype html>
<html lang="zh-Hans"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>SL₂(ℤ) · 模群的上半平面</title>
<style>'''+css+'''</style></head><body><main>
<header><div><h1>模群的上半平面</h1><p>从标准基本域展开，追踪每一块区域的色彩与整数矩阵。</p></div><p>SL₂(ℤ) / ℍ</p></header>
'''+fragment+'''
<p class="math-note">ℱ={z∈ℍ : |Re z|≤½，|z|≥1}；S(z)=−1/z，T(z)=z+1。金色轮廓标出 ℱ。展开深度采用最短生成元字长。</p>
<details class="help"><summary>键盘与数学</summary>
<p>S / T / Shift+T：施加 S / T / T⁻¹；← / →：逐块选择；[ / ]：调整深度；＋ / −：缩放；F：聚焦；0：复位；空格：自动展开；C / L / G：填充／描线／柔光。</p>
<p>每块区域是 gℱ，g=[a b;c d] 满足 ad−bc=1。g 与 −g 的作用相同，因此区域按 PSL₂(ℤ) 去重。画面展示有限展开，靠近实轴的结构继续无限细分。</p>
</details><footer>Abstract Algebra · Möbius 变换与双曲几何</footer>
<noscript>启用 JavaScript 即可互动探索。</noscript></main><script>
'''+scripts[0]+'''</script></body></html>'''
    output=APP/"index.html"
    output.write_text(document,encoding="utf-8")
    print(f"Built {output.relative_to(ROOT)}: {output.stat().st_size} bytes")
    return output

if __name__=="__main__":build()
