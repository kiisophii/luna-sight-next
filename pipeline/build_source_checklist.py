"""Card 15: enumerate source URLs for a HUMAN browser review; no invented PASS.

python pipeline/build_source_checklist.py
This only inventories links. Network errors and HTTP codes are not a human
visual check, and do not establish that a link is permanently broken.
"""
from collections import defaultdict
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    locations = defaultdict(list)
    for line_no, line in enumerate((ROOT / 'data/DATASETS.md').read_text(encoding='utf-8').splitlines(), 1):
        for url in re.findall(r'https?://[^\s<>\[\]()|`;,]+', line):
            ref = f'data/DATASETS.md:L{line_no}'
            url = url.rstrip('.:')
            if ref not in locations[url]:
                locations[url].append(ref)
    sites = json.loads((ROOT / 'web/data/sites.json').read_text(encoding='utf-8'))
    for site in sites:
        locations[site['source_url']].append(f"sites.json:{site['id']}")
    lines = ['# Card 15 source-link checklist', '',
             'Scope: every distinct absolute HTTP(S) URL written in data/DATASETS.md, plus every source_url in sites.json. Shared URLs appear once with all their references. Relative dataset-path fragments are not standalone links.', '',
             f'Total: {len(locations)} distinct URLs, including all {len(sites)} site source_url references.', '',
             '**Human visual review is REQUIRED and still pending for every row.** The AI enumerated the links and read the replacement Shackleton paper; it did not perform or certify a human review. No row is marked PASS.', '',
             'Open each link in your own browser. Confirm the expected paper, table, dataset listing or download opens, not just a login/error page. For large raw DEMs, cancel the download after confirming the expected file response/name; the adjacent product page and label help identify it. For parameterised APIs, an expected API help/parameter response is different from a missing page.', '',
             'Fill Human opened? with your name/date, Content matches? with PASS or the observed problem, and Issue with the issue URL for a confirmed broken/misdirected link. A transient timeout, bot block or network restriction is UNRESOLVED, not proof of a broken link. Keep the original URL and describe any working alternative in the Issue. One Issue per distinct broken source; do not silently alter other owners\' dataset rows.', '',
             '## Issue text for a confirmed problem', '',
             'Title: [Card 15 sources] Broken or misdirected source: <URL>', '',
             'Body: original URL; affected DATASETS lines/site IDs; human review date/browser; observed error or wrong content; expected source; verified replacement if available. No Issue is filed solely because an AI/network request failed.', '',
             '| # | Source URL | Used at | Human opened? | Content matches? | Issue |',
             '|---:|---|---|---|---|---|']
    for i, (url, refs) in enumerate(sorted(locations.items()), 1):
        lines.append(f"| {i} | [open]({url}) | {'; '.join(refs)} | TO CHECK | TO CHECK | TO CHECK |")
    (ROOT / 'docs/source_link_checklist.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Prepared {len(locations)} unique URLs; all {len(sites)} site source URLs covered; human checks pending.')


if __name__ == '__main__':
    main()
