"""Render the billing dashboard as a timestamped PDF report.

Usage: python3 build_pdf.py <work_dir> <YYYY-MM> <reports_dir>

Run after build_dashboard.py. Reads <work_dir>/billing-dashboard.html, plus
<work_dir>/out/freshness.json (see SKILL.md, "Helper queries") and
vonage_meta.json for the data timestamp. Writes a print copy of the page to
<work_dir>/billing-report-print.html (light theme, A4, a data-timestamp box
under the title) and prints it with headless Chrome to
<reports_dir>/billing-report-<YYYY-MM>_data-<YYYY-MM-DDTHHMM>.pdf, where the
second stamp is when the queries ran (the mtime of out/gcp_invoice.json, local
time). Set CHROME to override the browser path.
"""
import datetime, json, os, subprocess, sys

S, IM, REPORTS = sys.argv[1], sys.argv[2], sys.argv[3]
O = os.path.join(S, 'out')
start = datetime.date(int(IM[:4]), int(IM[5:7]), 1)
last = (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
MONTH = start.strftime('%B %Y')

ran = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(O, 'gcp_invoice.json'))).astimezone()
fresh = {r['s']: r['t'] for r in json.load(open(os.path.join(O, 'freshness.json')))}
vm = json.load(open(os.path.join(O, 'vonage_meta.json')))[0]

stamp = (f'<div class="stamp"><strong>Data timestamp:</strong> queries run {ran:%Y-%m-%d %H:%M %Z}. '
         f'Latest data in each source — GCP billing export: {fresh.get("gcp") or "none"} '
         f'(invoice month {start:%Y-%m}); AWS CUR: usage to {fresh.get("aws") or "none"}; '
         f'Vonage: usage to {vm.get("mx") or "none"}. '
         f'Report period: {start.day}–{last.day} {MONTH}.</div>')

css = '''
  .stamp { margin-top: 12px; font-size: 12.5px; color: var(--ink-2); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; background: var(--surface-2); line-height: 1.6; }
  @page { size: A4; margin: 12mm; }
  @media print {
    body { background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .wrap { max-width: none; padding: 0; gap: 14px; }
    .card { box-shadow: none; }
    table.summary, .summary-caption, .chart-head, .bar-chart, tr, .caveat { break-inside: avoid; }
    .chart-card { break-inside: auto; }
    details > summary::before { content: none !important; }
  }
</style>'''

s = open(os.path.join(S, 'billing-dashboard.html')).read()
for old, new in [('<html lang="en">', '<html lang="en" data-theme="light">'),
                 ('</style>', css),
                 ('</header>', stamp + '\n  </header>')]:
    assert old in s, f'marker not found: {old}'
    s = s.replace(old, new, 1)
s = s.replace('Cost overview — last month', f'Billing report — {MONTH}', 1)
html_path = os.path.join(S, 'billing-report-print.html')
open(html_path, 'w').write(s)

os.makedirs(REPORTS, exist_ok=True)
pdf = os.path.abspath(os.path.join(REPORTS, f'billing-report-{IM}_data-{ran:%Y-%m-%dT%H%M}.pdf'))
chrome = os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                '--virtual-time-budget=5000', f'--print-to-pdf={pdf}', 'file://' + os.path.abspath(html_path)],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
assert os.path.getsize(pdf) > 10000, f'PDF looks empty: {pdf}'
print(pdf)
