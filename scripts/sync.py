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
    mds = [f for f in files if f.endswith('_report.md')]
    
    match = re.match(r'(.+?) \((\d{4})\) (?:—|-) (.+)', folder)
    if not match: continue
    
    authors = match.group(1)
    year = match.group(2)
    title = match.group(3)
    
    mp3_file = mp3s[0]
    png_file = pngs[0] if pngs else None
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
ET.SubElement(ch, 'itunes:image', {'href': f'{BASE_URL}/artwork.png'})
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
        'url': f"{BASE_URL}/{ep['folder_enc']}/{ep['mp3_enc']}",
        'length': str(ep['mp3_size']), 'type': 'audio/mpeg'
    })
    if ep['png_enc']:
        ET.SubElement(item, 'itunes:image', {
            'href': f"{BASE_URL}/{ep['folder_enc']}/{ep['png_enc']}"
        })

raw = ET.tostring(rss, encoding='unicode')
with open(os.path.join(ROOT, "feed.xml"), 'w') as f:
    f.write(minidom.parseString(raw).toprettyxml(indent='  '))

# index.html
idx_data = []
for ep in episodes:
    idx_data.append({
        'title': ep['title'], 'year': ep['year'], 'desc': ep['desc'],
        'audio': f"{ep['folder_enc']}/{ep['mp3_enc']}",
        'img': f"{ep['folder_enc']}/{ep['png_enc']}" if ep['png_enc'] else "",
    })

with open(os.path.join(ROOT, "index.html")) as f:
    html = f.read()
html = re.sub(r'var EPISODES = \[.*?\];',
              f'var EPISODES = {json.dumps(idx_data, ensure_ascii=False)};',
              html, flags=re.DOTALL)
with open(os.path.join(ROOT, "index.html"), 'w') as f:
    f.write(html)

print(f"✅ Synced {len(episodes)} episodes → feed.xml + index.html")
print(f"   {BASE_URL}")