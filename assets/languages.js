/* Inlined by scripts/build_languages.py to keep every experiment usable offline. */
(() => {
  'use strict';
  const entries = __ALGEBRA_LOCALES__;
  const homePath = __ALGEBRA_HOME__;
  const key = 'abstract-algebra-language';
  const valid = value => ['en', 'de', 'zh'].includes(value);
  let stored;
  try { stored = localStorage.getItem(key); } catch (_) { /* Offline storage may be disabled. */ }
  const requested = new URL(location.href).searchParams.get('lang');
  let language = valid(requested) ? requested : valid(stored) ? stored : 'en';
  const normalize = value => value.trim().replace(/\s+/g, ' ');
  const dictionary = new Map(entries.map(row => [normalize(row[0]), row]));
  const originals = new WeakMap();
  const attributeOriginals = new WeakMap();
  const labels = {zh:['语言','作品首页'], en:['Language','Gallery'], de:['Sprache','Galerie']};
  function translate(value) {
    if (language === 'zh') return value;
    const index = language === 'en' ? 1 : 2;
    const term = dictionary.get(normalize(value));
    let output;
    if (term) output = term[index];
    else {
      const de = language === 'de';
      output = value.trim()
        .replace(/([\d,.]+) 圆 · 嵌套 (\d+) · 环 (\d+)/g, (_,n,d,r) => de ? `${n} Kreise · Verschachtelung ${d} · Ring ${r}` : `${n} circles · Nesting ${d} · Ring ${r}`)
        .replace(/([\d,.]+) 个区域 · 可见 ([\d,.]+)/g, (_,n,v) => de ? `${n} Kacheln · ${v} sichtbar` : `${n} tiles · ${v} visible`)
        .replace(/：仅 \{([^}]+)\} 出现 — 其余 (\d+) 类被同余障碍排除（局部-整体猜想）/g, (_,r,n) => de ? `: Nur {${r}} treten auf; die übrigen ${n} Klassen sind durch Kongruenzbedingungen ausgeschlossen (Lokal-global-Vermutung).` : `: Only {${r}} occur; the other ${n} classes are excluded by congruence restrictions (local–global conjecture).`)
        .replace(/ · 尖点 /g, de ? ' · Spitze ' : ' · Cusp ')
        .replace(/ · 字长 /g, de ? ' · Wortlänge ' : ' · Word length ')
        .replace(/([\d,.]+) 圆/g, (_,n) => `${n} ${de ? 'Kreise' : 'circles'}`);
    }
    return (value.match(/^\s*/)?.[0] || '') + output + (value.match(/\s*$/)?.[0] || '');
  }
  const toolbar = document.createElement('div');
  toolbar.id = 'algebra-language-bar';
  toolbar.innerHTML = '<a id="algebra-language-home"></a><label for="algebra-language"><span id="algebra-language-label"></span><select id="algebra-language"><option value="en" lang="en">English</option><option value="de" lang="de">Deutsch</option><option value="zh" lang="zh-Hans">中文</option></select></label>';
  const style = document.createElement('style');
  style.textContent = '#algebra-language-bar{box-sizing:border-box;display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;max-width:1280px;margin:14px auto 6px;padding:0 22px;font:14px/1.5 system-ui,sans-serif;color:inherit}#algebra-language-bar a{color:inherit;text-underline-offset:4px}#algebra-language-bar label{display:flex;gap:10px;align-items:center}#algebra-language-bar select{box-sizing:border-box;width:auto;min-width:116px;min-height:44px;font:16px/1.4 system-ui,sans-serif;padding:8px 12px;border:1px solid #7d869b;border-radius:7px;background:Canvas;color:CanvasText}#algebra-language-bar select:focus-visible{outline:2px solid #789dde;outline-offset:3px}html[lang=de] .row{flex-wrap:wrap}html[lang=de] .row .rng{min-width:110px}html[lang=de] .seg{flex-wrap:wrap}html[lang=de] .seg button{flex-basis:44%;min-height:36px}html[lang=de] nav .name{overflow-wrap:anywhere}';
  document.head.append(style);
  document.body.prepend(toolbar);
  const picker = toolbar.querySelector('select');
  const home = toolbar.querySelector('a');
  const excluded = node => node.parentElement?.closest('script,style,#algebra-language-bar');
  function text(node) {
    if (excluded(node)) return;
    const old = originals.get(node);
    const source = old && node.nodeValue === old.rendered ? old.source : node.nodeValue;
    const rendered = translate(source);
    originals.set(node, {source, rendered});
    if (node.nodeValue !== rendered) node.nodeValue = rendered;
  }
  const attributes = ['title','aria-label','alt','content'];
  function element(node) {
    if (node.closest?.('script,style,#algebra-language-bar')) return;
    if (!node.hasAttribute) return;
    const history = attributeOriginals.get(node) || {};
    for (const attr of attributes) {
      if (!node.hasAttribute(attr) || (attr === 'content' && !node.matches('meta[name="description"]'))) continue;
      const current = node.getAttribute(attr), old = history[attr];
      const source = old && current === old.rendered ? old.source : current;
      const rendered = translate(source);
      history[attr] = {source, rendered};
      if (current !== rendered) node.setAttribute(attr, rendered);
    }
    attributeOriginals.set(node, history);
  }
  function scan(root) {
    if (root.nodeType === Node.TEXT_NODE) { text(root); return; }
    if (root.nodeType !== Node.ELEMENT_NODE || root.closest('script,style,#algebra-language-bar')) return;
    element(root);
    root.querySelectorAll('[title],[aria-label],[alt],meta[name="description"]').forEach(element);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) text(walker.currentNode);
  }
  const observation = {subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:attributes};
  const observer = new MutationObserver(records => {
    observer.disconnect();
    if (!document?.documentElement) return;
    for (const record of records) {
      if (record.type === 'characterData') text(record.target);
      else if (record.type === 'attributes') element(record.target);
      else record.addedNodes.forEach(scan);
    }
    observer.observe(document.documentElement, observation);
  });
  function decorateLinks() {
    for (const link of document.querySelectorAll('a[href]')) {
      const raw = link.getAttribute('href');
      if (!raw || raw.startsWith('#') || /^(mailto:|javascript:|data:)/i.test(raw)) continue;
      const url = new URL(raw, document.baseURI);
      if (url.origin === location.origin && /(?:\.html|\/)$/i.test(url.pathname)) {
        url.searchParams.set('lang', language);
        link.setAttribute('href', url.href);
      }
    }
  }
  function setLanguage(value, updateURL = true) {
    if (!valid(value)) return;
    observer.disconnect();
    language = value;
    document.documentElement.lang = value === 'zh' ? 'zh-Hans' : value;
    picker.value = value;
    toolbar.querySelector('span').textContent = labels[value][0];
    home.textContent = '← ' + labels[value][1];
    home.href = homePath;
    scan(document.documentElement);
    decorateLinks();
    try { localStorage.setItem(key,value); } catch (_) { /* Language still works without storage. */ }
    if (updateURL) {
      const url = new URL(location.href); url.searchParams.set('lang',value);
      try { history.replaceState(null,'',url); } catch (_) { /* Some file:// contexts reject history writes. */ }
    }
    observer.observe(document.documentElement, observation);
  }
  picker.addEventListener('change', () => setLanguage(picker.value));
  // Arrow shortcuts belong to the focused language control, rather than the experiment.
  picker.addEventListener('keydown', event => event.stopPropagation());
  window.addEventListener('storage', event => { if (event.key === key && valid(event.newValue)) setLanguage(event.newValue); });
  window.AlgebraLanguage = Object.freeze({setLanguage,translate,get language(){return language;}});
  setLanguage(language, false);
})();
