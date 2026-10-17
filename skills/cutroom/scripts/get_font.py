#!/usr/bin/env python3
"""Fetch a font for the film: a Google Fonts family name, or a local file (.ttf/.otf/.woff2).

  python get_font.py "Space Grotesk" assets/fonts/display      → assets/fonts/display.woff2 (variable weight when available)
  python get_font.py ~/Library/Fonts/MyFont.otf assets/fonts/ui → assets/fonts/ui.otf
Prints the written path. Brand fonts that aren't on Google Fonts: ask the user for the file.
"""
import os, re, shutil, ssl, sys, urllib.request
try:                                     # python.org builds ship without CA certs; certifi comes with faster-whisper
    import certifi; CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl.create_default_context()

src, dest = sys.argv[1], sys.argv[2]
os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
if os.path.exists(os.path.expanduser(src)):
    p = os.path.expanduser(src); out = dest + os.path.splitext(p)[1].lower(); shutil.copy(p, out); print(out); sys.exit()
fam = src.strip().replace(' ', '+')
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30, context=CTX).read()
css = None
# variable fonts: the widest weight range the family supports; then a bold static weight; then the default
for q in [f'family={fam}:wght@{r}' for r in ('100..900', '200..900', '100..800', '200..800', '300..900', '300..800', '300..700', '400..900', '400..800', '400..700')] + [f'family={fam}:wght@700', f'family={fam}']:
    try:
        css = get(f'https://fonts.googleapis.com/css2?{q}&display=swap').decode(); break
    except Exception as e:
        if 'CERTIFICATE' in str(e): sys.exit('SSL certificates missing for Python: run "Install Certificates.command" or pip install certifi')
        continue
if not css: sys.exit(f'"{src}" is not on Google Fonts: ask the user for the font file')
# prefer the latin subset block
blocks = re.findall(r'/\* ([\w-]+) \*/\s*@font-face \{(.*?)\}', css, re.S) or [('latin', css)]
body = next((b for s, b in blocks if s == 'latin'), blocks[-1][1])
url = re.search(r'url\((https://[^)]+)\)', body)[1]
out = dest + '.woff2'
open(out, 'wb').write(get(url))
print(out)
