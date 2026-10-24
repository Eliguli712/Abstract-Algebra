#!/usr/bin/env python3
"""Embed the shared language runtime and dictionary in each standalone page."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['index.html', 'circle-chains/steiner-pappus-v5.html',
         'circle-chains/nested-apollonian-v2.html', 'sl2z/index.html']

def localize_file(path):
    path = Path(path)
    source = path.read_text(encoding='utf-8')
    source = re.sub(r'\n?<!-- algebra-language:start -->.*?<!-- algebra-language:end -->\n?', '', source, flags=re.S)
    runtime = (ROOT / 'assets/languages.js').read_text(encoding='utf-8')
    locales = json.loads((ROOT / 'assets/locales.json').read_text(encoding='utf-8'))
    home = 'index.html' if path.parent == ROOT else '../index.html'
    runtime = runtime.replace('__ALGEBRA_LOCALES__', json.dumps(locales,ensure_ascii=False))
    runtime = runtime.replace('__ALGEBRA_HOME__',json.dumps(home))
    block = '\n<!-- algebra-language:start -->\n<script id="algebra-language-runtime">\n' + runtime + '\n</script>\n<!-- algebra-language:end -->\n'
    assert source.count('</body>') == 1, path
    source = source.replace('</body>',block + '</body>')
    path.write_text(source,encoding='utf-8')
    return path

if __name__ == '__main__':
    for page in PAGES:
        print(localize_file(ROOT / page).relative_to(ROOT))
