"""
Generate an HTML thumbnail gallery from a social media quarterly report Excel file.
Shows each slide's post via Instagram iframe embed, with placeholders for TikTok/YouTube.

Usage:
    python generate_thumbnails.py --excel <path.xlsx> [--output <path.html>] [--sheet <name>]
"""
import argparse, re, os
import pandas as pd

STOP_WORDS = {'Campaign name', 'Campaign', 'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL',
              'MAY', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER',
              'DECEMBER', 'BY MONTHLY', 'TOTAL', 'META', 'TIKTOK', 'YOUTUBE',
              'OVERALL CAMPAIGN'}

PLATFORM_LABEL = {
    'instagram': ('ig',  'Instagram'),
    'tiktok':    ('tt',  'TikTok'),
    'youtube':   ('yt',  'YouTube'),
}

PLATFORM_ICON = {
    'tiktok':  ('&#127925;', 'TikTok post'),
    'youtube': ('&#9654;&#65039;', 'YouTube video'),
}


def detect_sheet(path):
    return pd.ExcelFile(path).sheet_names[0]


def short_desc(name):
    parts = name.split('|')
    if len(parts) >= 7:
        desc = parts[6].strip()
        dates = ''
        if len(parts) >= 9:
            dates = f'{parts[-2].strip()} to {parts[-1].strip()}'
        return desc, dates
    return name[:60], ''


def parse_excel(excel_path, sheet_name):
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
    blocks, month, i, n = [], None, 0, len(df)

    while i < n:
        row = df.iloc[i]
        v0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
        v1 = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''

        if v0.upper() in {'JANUARY','FEBRUARY','MARCH','APRIL','MAY','JUNE',
                          'JULY','AUGUST','SEPTEMBER','OCTOBER','NOVEMBER','DECEMBER'}:
            month = v0.strip(); i += 1; continue

        if v0 in ('Campaign name', 'Campaign') and \
                v1 in ('Placement', 'Advertising objective', 'Campaign type'):
            platform = ('instagram' if v1 == 'Placement'
                        else 'tiktok' if v1 == 'Advertising objective'
                        else 'youtube')
            j = i + 1
            if platform == 'instagram':
                data_rows, cname = [], None
                while j < n:
                    dr = df.iloc[j]
                    dv0 = str(dr.iloc[0]).strip() if pd.notna(dr.iloc[0]) else ''
                    dv1 = str(dr.iloc[1]).strip() if pd.notna(dr.iloc[1]) else ''
                    if not dv0 and not dv1: break
                    if dv0 in STOP_WORDS or dv0.startswith('Link:') or dv0.startswith('*'): break
                    if dv0: cname = dv0
                    data_rows.append(dr); j += 1
                if data_rows and cname:
                    blocks.append({'month': month, 'platform': platform, 'campaign_name': cname})
            else:
                while j < n:
                    dr = df.iloc[j]
                    dv0 = str(dr.iloc[0]).strip() if pd.notna(dr.iloc[0]) else ''
                    dv1 = str(dr.iloc[1]).strip() if pd.notna(dr.iloc[1]) else ''
                    if not dv0 and not dv1: break
                    if dv0 in STOP_WORDS or dv0.startswith('Link:') or dv0.startswith('*'): break
                    if dv0:
                        blocks.append({'month': month, 'platform': platform, 'campaign_name': dv0})
                    j += 1
            i = j
        else:
            i += 1

    return blocks


def parse_links(excel_path, sheet_name):
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
    links_by_month = {}
    month = None
    for i in range(len(df)):
        v0 = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ''
        if v0.upper() in {'JANUARY','FEBRUARY','MARCH','APRIL','MAY','JUNE',
                          'JULY','AUGUST','SEPTEMBER','OCTOBER','NOVEMBER','DECEMBER'}:
            month = v0.strip()
        if v0.startswith('Link:') and month:
            url = v0.replace('Link:', '').strip()
            links_by_month.setdefault(month, []).append(url)
    return links_by_month


def match_links(blocks, links_by_month):
    """
    Match links to Instagram blocks by month order.
    /p/ links → static/carousel posts (DS Article type)
    /reel/ links → video posts (Social Boosting / KITA SERUMPUN type)
    """
    month_ig_blocks = {}
    for b in blocks:
        if b['platform'] == 'instagram':
            month_ig_blocks.setdefault(b['month'], []).append(b)

    result = {}
    for month, ig_blocks in month_ig_blocks.items():
        raw_links = links_by_month.get(month, [])
        p_links    = [l for l in raw_links if '/p/' in l]
        reel_links = [l for l in raw_links if '/reel/' in l]

        p_idx, reel_idx = 0, 0
        for b in ig_blocks:
            cname = b['campaign_name'].lower()
            is_reel = any(k in cname for k in ['social boosting', 'kita serumpun', 'videovie'])
            if is_reel:
                if reel_idx < len(reel_links):
                    result[id(b)] = reel_links[reel_idx]
                    reel_idx += 1
                else:
                    result[id(b)] = None  # missing
            else:
                if p_idx < len(p_links):
                    result[id(b)] = p_links[p_idx]
                    p_idx += 1
                else:
                    result[id(b)] = None

    return result


def ig_embed_url(url):
    url = url.strip()
    if '/reel/' in url:
        code = re.search(r'/reel/([^/?]+)', url)
        if code:
            return f'https://www.instagram.com/reel/{code.group(1)}/embed/'
    elif '/p/' in url:
        code = re.search(r'/p/([^/?]+)', url)
        if code:
            return f'https://www.instagram.com/p/{code.group(1)}/embed/'
    return None


def ig_display_url(url):
    url = url.strip()
    if '/reel/' in url:
        code = re.search(r'/reel/([^/?]+)', url)
        if code:
            return f'instagram.com/reel/{code.group(1)}/'
    elif '/p/' in url:
        code = re.search(r'/p/([^/?]+)', url)
        if code:
            return f'instagram.com/p/{code.group(1)}/'
    return url


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Arial, sans-serif; background: #f0f0f0; padding: 24px; }
h1 { font-size: 20px; font-weight: 700; margin-bottom: 6px; color: #111; }
.subtitle { font-size: 13px; color: #666; margin-bottom: 28px; }
.month-section { margin-bottom: 40px; }
.month-label {
  font-size: 13px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 1px; color: #fff; background: #111;
  display: inline-block; padding: 4px 12px; border-radius: 3px; margin-bottom: 16px;
}
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.card { background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.12); }
.card-header { padding: 10px 12px; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 8px; }
.slide-num { background: #BB1111; color: #fff; font-size: 11px; font-weight: 700; border-radius: 3px; padding: 2px 6px; flex-shrink: 0; }
.badge { font-size: 10px; font-weight: 700; border-radius: 3px; padding: 2px 6px; flex-shrink: 0; }
.ig { background: #E1306C; color: #fff; }
.tt { background: #000; color: #fff; }
.yt { background: #FF0000; color: #fff; }
.card-title { font-size: 11px; color: #333; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-date { font-size: 10px; color: #999; padding: 4px 12px 8px; }
.embed-wrap { padding: 0 8px 0; }
.embed-wrap iframe { width: 100%; height: 400px; border: none; border-radius: 4px; display: block; }
.no-link { height: 160px; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #f7f7f7; gap: 8px; margin: 0 8px 8px; border-radius: 4px; border: 1px dashed #ccc; }
.no-link .icon { font-size: 28px; }
.no-link .msg { font-size: 11px; color: #999; text-align: center; line-height: 1.4; }
.link-row { padding: 6px 12px 10px; font-size: 10px; }
.link-row a { color: #BB1111; text-decoration: none; word-break: break-all; }
.link-row a:hover { text-decoration: underline; }
"""


def build_html(blocks, link_map, report_title):
    cards_by_month = {}
    slide_num = 0
    for b in blocks:
        slide_num += 1
        m = b['month'] or 'Unknown'
        cards_by_month.setdefault(m, []).append((slide_num, b))

    months_order = list(dict.fromkeys(b['month'] or 'Unknown' for b in blocks))

    parts = [f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n',
             f'<title>{report_title} — Thumbnails</title>\n<style>{CSS}</style>\n</head>\n<body>\n',
             f'<h1>{report_title} — Post Thumbnails by Slide</h1>\n',
             f'<p class="subtitle">{slide_num} slides total &nbsp;·&nbsp; '
             f'Instagram iframes load from instagram.com &nbsp;·&nbsp; '
             f'TikTok &amp; YouTube links not in source data</p>\n']

    for month in months_order:
        parts.append(f'<div class="month-section">\n<div class="month-label">{month}</div>\n<div class="grid">\n')

        for sn, b in cards_by_month.get(month, []):
            platform = b['platform']
            cls, label = PLATFORM_LABEL[platform]
            desc, dates = short_desc(b['campaign_name'])
            url = link_map.get(id(b))

            parts.append(f'<div class="card">\n')
            parts.append(f'  <div class="card-header">\n')
            parts.append(f'    <span class="slide-num">Slide {sn}</span>\n')
            parts.append(f'    <span class="badge {cls}">{label}</span>\n')
            parts.append(f'    <span class="card-title">{desc}</span>\n')
            parts.append(f'  </div>\n')
            if dates:
                parts.append(f'  <div class="card-date">{dates}</div>\n')

            if platform == 'instagram' and url:
                embed = ig_embed_url(url)
                disp  = ig_display_url(url)
                if embed:
                    parts.append(f'  <div class="embed-wrap">\n')
                    parts.append(f'    <iframe src="{embed}" scrolling="no" allowtransparency="true"></iframe>\n')
                    parts.append(f'  </div>\n')
                    parts.append(f'  <div class="link-row"><a href="{url}" target="_blank">{disp}</a></div>\n')
                else:
                    parts.append(f'  <div class="no-link"><div class="icon">&#128247;</div>'
                                 f'<div class="msg">Could not parse link</div></div>\n')
            elif platform == 'instagram' and url is None:
                parts.append(f'  <div class="no-link"><div class="icon">&#9888;&#65039;</div>'
                             f'<div class="msg">Link unavailable<br>(90-day retention policy)</div></div>\n')
            else:
                icon, msg = PLATFORM_ICON.get(platform, ('&#10067;', 'No link'))
                parts.append(f'  <div class="no-link"><div class="icon">{icon}</div>'
                             f'<div class="msg">{label} post &middot; No link in source data</div></div>\n')

            parts.append('</div>\n')

        parts.append('</div>\n</div>\n')

    parts.append('</body>\n</html>\n')
    return ''.join(parts)


def main():
    ap = argparse.ArgumentParser(description='Generate HTML thumbnail gallery from social report Excel')
    ap.add_argument('--excel',  required=True, help='Path to the .xlsx report file')
    ap.add_argument('--output', default=None,  help='Output .html path (default: alongside Excel)')
    ap.add_argument('--sheet',  default=None,  help='Sheet name (default: auto-detect first sheet)')
    args = ap.parse_args()

    excel_path  = args.excel
    sheet_name  = args.sheet or detect_sheet(excel_path)
    report_title = os.path.splitext(os.path.basename(excel_path))[0]

    if args.output:
        output_path = args.output
    else:
        base = os.path.splitext(excel_path)[0]
        output_path = base + '_thumbnails.html'

    print(f'Sheet  : {sheet_name}')
    print(f'Output : {output_path}')

    blocks     = parse_excel(excel_path, sheet_name)
    links      = parse_links(excel_path, sheet_name)
    link_map   = match_links(blocks, links)
    html       = build_html(blocks, link_map, report_title)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'Done. {len(blocks)} slides written to {output_path}')


if __name__ == '__main__':
    main()
