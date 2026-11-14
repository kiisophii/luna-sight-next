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


def render_ai_report(file):
    """Import supplied AI evidence without promoting it to human sign-off."""
    audit = json.loads(file.read_text(encoding='utf-8'))
    destination = ROOT / 'docs/source_link_checklist.md'
    old = destination.read_text(encoding='utf-8') if destination.exists() else ''
    marker = '\n## Human checks\n'
    human = old.split(marker, 1)[1] if marker in old else '''
Only these two targeted human checks remain requested. An AI PASS above does not mean a human opened it. Enter date/result only after viewing the actual table.

| Check | Open and inspect | Human opened? | Human result |
|---|---|---|---|
| H1 | [Wiley original](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434), Appendix Table A1: compare PCB01, HW01, MMA01, MMP01, MMO01, NR101, NR201, dGR201 and SP01 with sites.json. AI access was blocked; no human result is assumed. | TO CHECK | TO CHECK |
| H2 | [Gläser 2017 PDF](https://ntrs.nasa.gov/api/citations/20170007365/downloads/20170007365.pdf), printed p.12 Table 2: visually confirm the FIRST Shackleton S row is -89.6866 / 197.19 E (= -162.81 signed E). Text extraction can misalign row labels. | TO CHECK | TO CHECK |
'''
    lines = ['# Card 15 source-link checklist — imported AI results', '',
             '**AI-checked 2026-11-14. This is the user-supplied Claude automated report, not human review and not a new independent run by the implementation assistant.**', '',
             'Original 65-URL audit: PASS 62 / BROKEN 2 / UNRESOLVED 1 / MISMATCH 0. Full supplied method/evidence: docs/source_link_ai_report_2026-11-14.md; structured import: docs/source_link_ai_results.json.', '',
             'The numbered rows preserve the original audit snapshot and old URLs for traceability. They are not a newly deduplicated inventory after repairs. DATASETS.md now uses products/90 and products/69 for the two broken folder listings; direct TIF URLs remain unchanged. The stale ACD-50044 current-site association was removed for Shackleton; its active source is Gläser et al. 2017, NTRS 20170007365. Historical R04 validation references remain historical.', '',
             'Wiley remains UNRESOLVED due to bot blocking, not BROKEN. The Gläser result includes an explicit human table-layout check below. The ShadowCam redirect is recorded as working by the supplied AI report.', '',
             '| # | Checked URL (original snapshot) | Used at (snapshot) | AI result | Evidence / remediation |',
             '|---:|---|---|---|---|']
    for row in audit['rows']:
        evidence = row['evidence'].replace('|', '\\|').replace('\n', ' ')
        if row.get('replacement_url'):
            evidence += f"; REPAIRED in DATASETS.md -> {row['replacement_url']} (individual files unchanged)"
        if row.get('issue_url'):
            evidence += f"; tracking Issue: {row['issue_url']}"
        lines.append(f"| {row['id']} | [open]({row['url']}) | {row['used_at']} | {row['checked']}: {row['verdict']} | {evidence} |")
    destination.write_text('\n'.join(lines) + '\n' + marker + human, encoding='utf-8')
    print('Imported AI-checked 2026-11-14: 62 PASS, 2 BROKEN (repaired links), 1 UNRESOLVED; two human checks retained.')


def main():
    audit_file = ROOT / 'docs/source_link_ai_results.json'
    if audit_file.exists():
        render_ai_report(audit_file)
        return
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
