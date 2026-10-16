#!/usr/bin/env bash
# Fetch pages the way a crawler gets them and print only the SEO fields, one line per page, so the HTML itself never
# enters the session's context. Read-only: it writes nothing but its own temp files, which it removes.
#
# Usage: probe.sh [-u googlebot|browser] [-j] BASE_URL PATH...
#   -u  user agent: googlebot (default; Googlebot Smartphone plus an "seo-audit" marker, so log queries can drop
#       audit traffic) or browser (a desktop Chrome string, to spot user-agent-dependent responses)
#   -j  also print each JSON-LD block (first 1,500 characters)
# Redirects are not followed: a 3xx line shows its Location.
set -euo pipefail

ua_name=googlebot
jsonld=0
while getopts 'u:j' opt; do
  case $opt in
    u) ua_name=$OPTARG ;;
    j) jsonld=1 ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))
[ $# -ge 2 ] || { echo 'usage: probe.sh [-u googlebot|browser] [-j] BASE_URL PATH...' >&2; exit 2; }

case $ua_name in
  googlebot) ua='Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html) seo-audit' ;;
  browser) ua='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 seo-audit' ;;
  *) echo "unknown -u $ua_name" >&2; exit 2 ;;
esac

base=${1%/}
shift
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

for path in "$@"; do
  meta=$(curl -s -A "$ua" --compressed --max-time 60 -D "$tmp/headers" -o "$tmp/body" \
    -w '%{http_code} %{time_total} %{redirect_url}' "$base$path") || meta="000 0 curl-exit-$?"
  python3 -I - "$path" "$meta" "$tmp/headers" "$tmp/body" "$jsonld" <<'PY'
import json, os, re, sys
from html.parser import HTMLParser

path, meta, headers_file, body_file, show_jsonld = sys.argv[1:6]
code, secs, location = (meta.split(' ', 2) + [''] * 3)[:3]
if code == '000':
    print(f'000 {path} | fetch failed ({location})')
    sys.exit()
headers = open(headers_file, errors='replace').read()
size = os.path.getsize(body_file)
ctype = (re.findall(r'(?im)^content-type:\s*([^;\r\n]*)', headers) or [''])[-1].strip()
x_robots = ', '.join(m.strip() for m in re.findall(r'(?im)^x-robots-tag:(.*)$', headers))

class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = None; self.in_title = False
        self.desc = []; self.canon = []; self.robots = []
        self.og = 0; self.tw = 0; self.h1 = []; self.in_h1 = False
        self.ld = []; self.in_ld = False; self.skip = 0
        self.words = 0; self.links = 0
    def handle_starttag(self, tag, attrs):
        a = {k: (v or '') for k, v in attrs}
        if tag == 'title' and self.title is None: self.title = ''; self.in_title = True
        elif tag == 'meta':
            name = a.get('name', '').lower(); prop = a.get('property', '').lower()
            if name == 'description': self.desc.append(a.get('content', ''))
            elif name in ('robots', 'googlebot'): self.robots.append(f"{name}={a.get('content', '')}")
            if prop.startswith('og:'): self.og += 1
            if name.startswith('twitter:') or prop.startswith('twitter:'): self.tw += 1
        elif tag == 'link' and 'canonical' in a.get('rel', '').lower().split(): self.canon.append(a.get('href', ''))
        elif tag == 'h1': self.h1.append(''); self.in_h1 = True
        elif tag == 'a' and a.get('href'): self.links += 1
        elif tag == 'script':
            self.skip += 1
            if a.get('type', '').lower() == 'application/ld+json': self.ld.append(''); self.in_ld = True
        elif tag in ('style', 'template', 'noscript', 'svg'): self.skip += 1
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        elif tag == 'h1': self.in_h1 = False
        elif tag in ('script', 'style', 'template', 'noscript', 'svg') and self.skip:
            self.skip -= 1
            if tag == 'script': self.in_ld = False
    def handle_data(self, data):
        if self.in_ld: self.ld[-1] += data
        if self.skip: return
        if self.in_title: self.title += data
        if self.in_h1: self.h1[-1] += data
        if not self.in_title: self.words += len(data.split())

p = Head()
html = 'html' in ctype
if html:
    p.feed(open(body_file, errors='replace').read())

def short(s, n=90):
    s = ' '.join((s or '').split())
    return s if len(s) <= n else s[:n - 1] + '…'

def ld_types(block):
    try:
        data = json.loads(block)
    except ValueError:
        return ['invalid-json']
    found = []
    def walk(node):
        if isinstance(node, dict):
            t = node.get('@type')
            if t: found.extend(t if isinstance(t, list) else [t])
            for v in node.values(): walk(v)
        elif isinstance(node, list):
            for v in node: walk(v)
    walk(data)
    return found

fields = [f'{code} {float(secs):.2f}s {size}B {path}']
if location: fields.append(f'location={location}')
if not html:
    fields.append(f'content-type={ctype or "none"}')
    if x_robots: fields.append(f'x-robots-tag={x_robots}')
else:
    fields += [
        f'title={short(p.title) if p.title is not None else "none"}',
        f'desc={short(p.desc[0], 70) if p.desc else "none"}' + (f' (x{len(p.desc)})' if len(p.desc) > 1 else ''),
        f'canonical={",".join(p.canon) or "none"}',
        f'robots={";".join(p.robots) or "none"}',
        f'x-robots-tag={x_robots or "none"}',
        f'h1x{len(p.h1)}={short(p.h1[0], 50) if p.h1 else ""}',
        f'og={p.og} twitter={p.tw}',
        f'jsonld={len(p.ld)}:{"+".join(sorted({t for b in p.ld for t in ld_types(b)}))}',
        f'words={p.words} links={p.links}',
    ]
print(' | '.join(fields))
if show_jsonld == '1':
    for i, block in enumerate(p.ld, 1):
        print(f'  jsonld[{i}]: {short(block, 1500)}')
PY
done
