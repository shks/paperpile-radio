#!/usr/bin/env python3
"""Paperpile Radio sync script.
Scans paper folders and regenerates feed.xml + index.html.
Run after adding or updating episodes.
"""
import os, re, json, hashlib
from datetime import datetime
from urllib.parse import quote
import xml.etree.ElementTree as ET
from xml.dom import minidom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ep_dir = os.path.join(ROOT, "episodes")
BASE_URL = os.environ.get("PAPERPILE_RADIO_URL", "https://shks.github.io/paperpile-radio")

episodes = []

for folder in sorted(os.listdir(ep_dir)):
    fp = os.path.join(ep_dir, folder)
    
    files = os.listdir(fp)
    mp3s = [f for f in files if f.endswith('_radio.mp3')]
    if not mp3s: continue
    
    pngs = [f for f in files if f.endswith('_infographic.png') and 'square' not in f]
    sq_pngs = [f for f in files if f.endswith('_infographic_square.png')]
    mds = [f for f in files if f.endswith('_report.md')]
    
    match = re.match(r'(.+?) \((\d{4})\) (?:—|-) (.+)', folder)
    if not match: continue
    
    authors = match.group(1)
    year = match.group(2)
    title = match.group(3)
    
    mp3_file = mp3s[0]
    png_file = pngs[0] if pngs else (sq_pngs[0] if sq_pngs else None)
    sq_png_file = sq_pngs[0] if sq_pngs else (pngs[0] if pngs else None)
    md_file = mds[0] if mds else None
    
    desc = ""
    if md_file:
        with open(os.path.join(fp, md_file)) as f:
            lines = f.readlines()
            content, started = [], False
            for line in lines:
                s = line.strip()
                if started and s and not s.startswith('#'):
                    content.append(s)
                    if len(content) >= 2: break
                if s.startswith('# ') or s.startswith('## '): started = True
            desc = ' '.join(content)[:200]
    
    paper = None
    for lf in ('paper_url.txt', 'link.txt'):
        lp = os.path.join(fp, lf)
        if os.path.exists(lp):
            with open(lp) as f:
                paper = f.read().strip() or None
            if paper: break
    if md_file and not paper:
        with open(os.path.join(fp, md_file)) as f:
            text = f.read()
        mdoi = re.search(r'\b10\.\d{4,9}/[^\s"<>)\]]+', text)
        murl = re.search(r'https?://[^\s"<>)\]]+', text)
        if mdoi: paper = 'https://doi.org/' + mdoi.group(0)
        elif murl: paper = murl.group(0)

    mp3_size = os.path.getsize(os.path.join(fp, mp3_file))
    guid = hashlib.md5(folder.encode()).hexdigest()
    pubDate = datetime.fromtimestamp(
        os.path.getmtime(os.path.join(fp, mp3_file))
    ).strftime('%a, %d %b %Y %H:%M:%S +0900')
    
    episodes.append({
        'title': f"{authors} ({year}) — {title}",
        'desc': desc, 'year': year,
        'folder_enc': quote(folder),
        'mp3_enc': quote(mp3_file),
        'mp3_size': mp3_size,
        'png_enc': quote(png_file) if png_file else None,
        'sq_png_enc': quote(sq_png_file) if sq_png_file else None,
        'report_enc': quote(md_file) if md_file else None,
        'paper': paper,
        'guid': guid, 'pubDate': pubDate,
    })

episodes.sort(key=lambda x: x['pubDate'], reverse=True)

# feed.xml
rss = ET.Element('rss', {
    'xmlns:itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
    'xmlns:content': 'http://purl.org/rss/1.0/modules/content/',
    'version': '2.0'
})
ch = ET.SubElement(rss, 'channel')
ET.SubElement(ch, 'title').text = 'Paperpile Radio 🎧'
ET.SubElement(ch, 'link').text = BASE_URL
ET.SubElement(ch, 'description').text = '論文のNotebookLM音声概要。認知科学・HCI・ロボティクス論文を日本語で。'
ET.SubElement(ch, 'language').text = 'ja'
ET.SubElement(ch, 'itunes:author').text = 'Shun Kasahara'
ET.SubElement(ch, 'itunes:category', {'text': 'Science'})
ET.SubElement(ch, 'itunes:explicit').text = 'no'
ET.SubElement(ch, 'itunes:type').text = 'episodic'
ET.SubElement(ch, 'generator').text = 'Paperpile Radio Generator'
ET.SubElement(ch, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0900')

for ep in episodes:
    item = ET.SubElement(ch, 'item')
    ET.SubElement(item, 'title').text = ep['title']
    ET.SubElement(item, 'description').text = ep['desc']
    ET.SubElement(item, 'itunes:summary').text = ep['desc']
    ET.SubElement(item, 'guid', {'isPermaLink': 'false'}).text = ep['guid']
    ET.SubElement(item, 'pubDate').text = ep['pubDate']
    ET.SubElement(item, 'enclosure', {
        'url': f"{BASE_URL}/episodes/{ep['folder_enc']}/{ep['mp3_enc']}",
        'length': str(ep['mp3_size']), 'type': 'audio/mpeg'
    })
    if ep['sq_png_enc']:
        ET.SubElement(item, 'itunes:image', {
            'href': f"{BASE_URL}/episodes/{ep['folder_enc']}/{ep['sq_png_enc']}"
        })

raw = ET.tostring(rss, encoding='unicode')
with open(os.path.join(ROOT, "feed.xml"), 'w') as f:
    f.write(minidom.parseString(raw).toprettyxml(indent='  '))

# index.html
idx_data = []
for ep in episodes:
    idx_data.append({
        'title': ep['title'], 'year': ep['year'], 'desc': ep['desc'],
        'audio': f"episodes/{ep['folder_enc']}/{ep['mp3_enc']}",
        'img': f"episodes/{ep['folder_enc']}/{ep['png_enc']}" if ep['png_enc'] else "",
        'report': f"episodes/{ep['folder_enc']}/{ep['report_enc']}" if ep['report_enc'] else "",
        'paper': ep['paper'] or "",
    })

with open(os.path.join(ROOT, "index.html")) as f:
    html = f.read()
html = re.sub(r'var EPISODES = \[.*?\];',
              f'var EPISODES = {json.dumps(idx_data, ensure_ascii=False)};',
              html, flags=re.DOTALL)
with open(os.path.join(ROOT, "index.html"), 'w') as f:
    f.write(html)

print(f"✅ Synced {len(episodes)} episodes → feed.xml + index.html + README.md")
print(f"   {BASE_URL}")

# README.md
with open(os.path.join(ROOT, "README.md"), 'w') as f:
    f.write(f"""# 🎧 Paperpile Radio

論文のNotebookLM音声概要を自動配信する個人ポッドキャスト。
認知科学・HCI・ロボティクス論文を日本語で。

**🎵 聴く**: [{BASE_URL}]({BASE_URL})  
**📡 RSS**: [{BASE_URL}/feed.xml]({BASE_URL}/feed.xml)

## 使い方

### ポッドキャストアプリに登録
Overcast / Apple Podcasts / Pocket Casts で「URLで追加」し、
`{BASE_URL}/feed.xml` を登録してください。

### Webで聴く
[{BASE_URL}]({BASE_URL}) を開くだけ。

## 統計

- **エピソード数**: {len(episodes)}
- **最終更新**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- **収録年**: {min(ep['year'] for ep in episodes) if episodes else '—'} 〜 {max(ep['year'] for ep in episodes) if episodes else '—'}

## 仕組み

Paperpile → Google Drive → NotebookLM → 日本語レポート/音声/インフォグラフィック → GitHub Pages

自動生成のため、週に数本ずつ追加されます。
""")