"""Build the billing dashboard page from the JSON query outputs.

Usage: python3 build_dashboard.py <work_dir> <YYYY-MM>

<work_dir>/out/ must hold the `bq query --format=json` output of each query
for the month, with LIMIT 10 removed, named after the query file:
  gcp_invoice.json  gcp_all_services.json  gcp_uk_platform_cogs.json
  gcp_us_platform_cogs.json  gcp_uk_r&d_platform_cogs.json
  gcp_uk_api_cogs.json  gcp_uk_r&d_api_cogs.json
  aws_services.json  aws_marketplace.json  vonage_services.json
plus four helper queries (see SKILL.md, "Helper queries"):
  aws_split.json  vonage_breakdown.json  vonage_meta.json  coverage.json

Writes <work_dir>/billing-dashboard.html. Every total is cross-checked
(card lists against summary rows, the invoice reconciliation to the cent,
AWS environments against the AWS row, Vonage records against the table);
a failed check stops the build with an AssertionError.
"""
import json,sys,html,os,datetime
S=sys.argv[1]; O=os.path.join(S,'out')+'/'
IM=sys.argv[2]
_start=datetime.date(int(IM[:4]),int(IM[5:7]),1)
_next=datetime.date(_start.year+(_start.month==12),_start.month%12+1,1)
_last=_next-datetime.timedelta(days=1)
MONTH=_start.strftime('%B %Y'); MON=_start.strftime('%B')
HERE=os.path.dirname(os.path.abspath(__file__))
def load(f): return json.load(open(O+f))
def num(v): return float(v or 0)
def money(v,c='$'):
    v=round(num(v),2); return ('&minus;' if v<0 else '')+c+f'{abs(v):,.2f}'
esc=html.escape
def check(a,b,what):
    assert abs(a-b)<0.015, f'{what}: {a} != {b}'

# ---- data
inv=load('gcp_invoice.json')
g=[r for r in inv if r['Invoice']=='Google invoice'][0]; g_total=num(g['Total'])
mk=[r for r in inv if r['Invoice'].startswith('Marketplace')]; mk_total=sum(num(r['Total']) for r in mk)
rnd=sum(num(r['Total']) for r in inv if r['Invoice'].startswith('Unattributed'))
inv_all=sum(num(r['Total']) for r in inv)
ga=load('gcp_all_services.json'); ga_net=sum(num(r['Subtotal']) for r in ga); ga_list=sum(num(r['Cost']) for r in ga)
cogs=[('UK Platform COGS','gcp_uk_platform_cogs.json','gcp_uk_platform_cogs.sql','prj-ufonia-prd-lon-host-01, prj-ufonia-prd-lon-svc-01'),
      ('US Platform COGS','gcp_us_platform_cogs.json','gcp_us_platform_cogs.sql','prj-ufonia-prd-iowa-svc-02'),
      ('UK R&amp;D Platform COGS','gcp_uk_r&d_platform_cogs.json','gcp_uk_r&amp;d_platform_cogs.sql','prj-ufonia-dev-host-01, prj-ufonia-dev-lon-svc-01')]
cogs=[(l,load(f),q,p) for l,f,q,p in cogs]
api=load('gcp_uk_api_cogs.json'); rdapi=load('gcp_uk_r&d_api_cogs.json')
aws=load('aws_services.json'); awsm=load('aws_marketplace.json')
split=load('aws_split.json')
aws_total=[num(r['cost']) for r in split if r['src']=='AWS' and r['env'] is None][0]
awsm_total=[num(r['cost']) for r in split if r['src']=='Marketplace' and r['env'] is None][0]
aws_all=[num(r['cost']) for r in split if r['src'] is None][0]
env={r['env']:num(r['cost']) for r in split if r['src']=='AWS' and r['env']}
check(sum(env.values()),aws_total,'AWS env split')
check(aws_total+awsm_total,aws_all,'AWS + Marketplace')
assert abs(sum(num(r['Cost']) for r in aws)-aws_total)<0.05 and abs(sum(num(r['Cost']) for r in awsm)-awsm_total)<0.05
von={r['Service Description']:num(r['Cost']) for r in load('vonage_services.json')}; von_total=sum(von.values())
vb=load('vonage_breakdown.json'); vm=load('vonage_meta.json')[0]
check(sum(num(r['cost']) for r in vb),von_total,'Vonage breakdown')
assert sum(int(r['n']) for r in vb)==int(vm['n'])
cov={r['scope']:r['missing'] for r in load('coverage.json')}
late=inv_all-ga_net
check(ga_net+late-mk_total-rnd,g_total,'invoice reconciliation')

# ---- building blocks
def bars(items,c='$',top=10):
    items=sorted(items,key=lambda x:-x[1])[:top]; mx=max(v for _,v in items) or 1
    return '<div class="bar-chart">'+''.join(f'<div class="bar-row"><div class="name" title="{esc(n)}">{esc(n)}</div><div class="track"><div class="fill" style="width:{max(v/mx*100,1.5):.1f}%"></div></div><div class="value">{money(v,c)}</div></div>' for n,v in items)+'</div>'
def table(summary,heads,rows,total=None):
    th=''.join(f'<th>{x}</th>' for x in heads)
    tr=''.join('<tr>'+''.join(f'<td>{x}</td>' for x in r)+'</tr>' for r in rows)
    if total: tr+='<tr class="total">'+''.join(f'<td>{x}</td>' for x in total)+'</tr>'
    return f'<details class="table-toggle" open><summary>{summary}</summary><div class="table-wrap"><table class="data-table"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div></details>'
def card(title,note,body,caveat=''):
    return f'''
  <section class="card chart-card">
    <div class="chart-head"><h2>{title}</h2><div class="note">{note}</div></div>
    {body}{f'<div class="caveat">{caveat}</div>' if caveat else ''}
  </section>
'''
def svc_card(title,note,rows,basis,label):
    items=[(r['Service Description'],num(r[basis])) for r in rows]
    items.sort(key=lambda x:-x[1])
    tot=sum(v for _,v in items)
    return card(title,note,f'<div class="sub-head">Top 10 — {label}</div>'+bars(items)+
        table(f'All {len(items)} services — {label}',['Service','Cost'],[(esc(n),money(v)) for n,v in items],(f'Total ({len(items)} services)',money(tot)))), tot

# ---- summary table
rows=[('GCP Invoice (Google)',money(g_total),0),('GCP Marketplace (invoiced separately)',money(mk_total),0),
      ('GCP All services (after credits)',money(ga_net),0)]
cogs_tot={l:sum(num(x['Cost']) for x in r) for l,r,_,_ in cogs}
rows+=[('GCP UK Platform COGS',money(cogs_tot['UK Platform COGS']),1),
       ('GCP UK API COGS',money(sum(num(x['Cost']) for x in api)),1),
       ('GCP UK R&amp;D Platform COGS',money(cogs_tot['UK R&amp;D Platform COGS']),1),
       ('GCP UK R&amp;D API COGS',money(sum(num(x['Cost']) for x in rdapi)),1),
       ('GCP US Platform COGS',money(cogs_tot['US Platform COGS']),1),
       ('AWS Marketplace (third-party, billed via AWS)',money(awsm_total),0),
       ('AWS All services (excluding Marketplace, inc VAT)',money(aws_total),0)]
rows+=[(f'AWS {k} (inc VAT)',money(env[k]),1) for k in sorted(env)]
rows.append(('Vonage All categories',money(von_total,'€'),0))
vorder=['SMS','Inbound Calls','Outbound Calls','WebSocket','Other']
rows+=[(f'Vonage {k}',money(von.get(k,0),'€'),1) for k in vorder+[k for k in von if k not in vorder]]
summary=''.join(f'<tr><td class="sub-row">↳ {l}</td><td>{v}</td></tr>' if s else f'<tr><td>{l}</td><td>{v}</td></tr>' for l,v,s in rows)
envtxt=' + '.join(money(env[k]) for k in sorted(env))
vontxt=' + '.join(money(von.get(k,0),'€') for k in vorder)
def miss(scope,total=24):
    m=cov[scope]; return f'all {total} matched' if not m else f'{total-len(m)} of {total} matched (no usage: '+', '.join(f'<code>{x}</code>' for x in m)+')'
caption=f'''
      <p><strong>GCP Invoice (Google)</strong> reproduces Google's monthly invoice to the cent: invoice month {IM}, seller Google, list cost {money(g['Cost'])} less {money(-num(g['Credits']))} of credits. <strong>GCP Marketplace</strong> is third-party sellers billed through the same account but invoiced separately. The rows below them group by <em>when usage happened</em>, so they don't match the invoice exactly — see the first card for the reconciliation.</p>
      <p><strong>What "Cost" means per row.</strong> GCP All services is <em>after</em> credits (list cost {money(ga_list)} less {money(ga_list-ga_net)} of credits). The five GCP COGS rows are <em>cost before credits</em> — the basis COGS is reported on, and the figure the GCP Billing console shows. AWS is UnblendedCost <em>including VAT</em>, matching the AWS console; AWS Marketplace — third-party products such as the Claude and OpenAI \"Amazon Bedrock Edition\" models — is shown on its own row, the same way as GCP Marketplace. Vonage is the summed price in <strong>EUR</strong>.</p>
      <p><strong>Indented rows mean two different things.</strong> Under AWS excluding Marketplace, inc VAT ({envtxt} = {money(aws_total)}) and Vonage ({vontxt} = {money(von_total,'€')}) they <em>add up exactly</em> to the row above. Under GCP All services they <em>don't</em>: they're slices of GCP spend on different project scopes. The COGS rows are grouped UK first (production, then R&amp;D/dev), then US production, so they never sum to All services or to each other. No grand total is shown, since it would mix currencies and double-count.</p>
      <p><strong>Service-ID coverage this month:</strong> UK Platform COGS {miss('uk')}; US Platform COGS {miss('us')}; UK R&amp;D Platform COGS {miss('rd')}. UK R&amp;D API COGS is small dev usage, not zero.</p>'''

# ---- cards
cards=''
sel_rows=[(esc(r['Invoice']),esc(r['Seller']),money(r['Cost']),money(r['Credits']),money(r['Total'])) for r in inv]
rec=[(f'GCP All services — {MON} usage dates, after credits',money(ga_net)),
     ('+ usage reported late and billed on this invoice (net)',money(late)),
     (f'= everything on invoice month {IM}',money(inv_all))]
rec+=[(f'− {esc(r["Seller"])} (Marketplace)',money(-num(r['Total']))) for r in mk]
if abs(rnd)>=0.005: rec.append(('− unattributed rounding',money(-rnd)))
cards+=card(f'GCP — {MONTH} invoice',f'bigquery-sql/gcp_invoice.sql · invoice month {IM} · USD',
    table('By seller',['Invoice','Seller','Cost','Credits','Total'],sel_rows)+
    table('Reconciliation with GCP All services',['Step','USD'],rec,('= GCP Invoice (Google)',money(g_total))),
    'The invoice groups by invoice month and includes late-reported usage; the usage rows group by usage date. Marketplace sellers bill through the GCP account but issue their own invoices.')
win=f'{MONTH} · US/Pacific month · USD'
c,t=svc_card('GCP — all services',f'gcp_all_services.sql (no LIMIT) · {win}',ga,'Subtotal','cost after credits'); check(t,ga_net,'GCP all'); cards+=c
def cogs_card(l):
    _,r,q,p=[x for x in cogs if x[0]==l][0]
    c,t=svc_card(f'GCP — {l}',f'{q} · {p} · {win}',r,'Cost','cost before credits'); check(t,cogs_tot[l],l); return c
cards+=cogs_card('UK Platform COGS')+cogs_card('UK R&amp;D Platform COGS')
apirows=[('UK API COGS (production)',r) for r in api]+[('UK R&amp;D API COGS (dev)',r) for r in rdapi]
cards+=card('GCP — UK API COGS (Cloud Speech API)',f'gcp_uk_api_cogs.sql · gcp_uk_r&amp;d_api_cogs.sql · {win}',
    table('Cost before credits, by scope',['Scope','Service','Cost'],[(l,esc(r['Service Description']),money(r['Cost'])) for l,r in apirows]),
    'Two different project scopes shown side by side — not a combined total.')
cards+=cogs_card('US Platform COGS')
aws_items=sorted(((r['Service Description'],num(r['Cost'])) for r in aws),key=lambda x:-x[1])
mrows=sorted(awsm,key=lambda r:-num(r['Cost']))
cards+=card('AWS — all services (excluding Marketplace, inc VAT)',f'aws_services.sql (no LIMIT) · aws_services_by_environment.sql · aws_marketplace.sql · {MONTH} · Europe/London dates · USD',
    table('By environment (AWS Cost Category), inc VAT',['Environment','Cost'],[(k,money(env[k])) for k in sorted(env)],('Total',money(aws_total)))+
    '<div class="sub-head">Top 10 services</div>'+bars(aws_items)+
    table(f'All {len(aws_items)} services, inc VAT',['Service','Cost'],[(esc(n),money(v)) for n,v in aws_items],(f'Total ({len(aws_items)} services)',money(aws_total)))+
    table(f'AWS Marketplace — {len(mrows)} products',['Product','Environment','Cost'],[(esc(r['Service Description']),esc(r['Environment']),money(r['Cost'])) for r in mrows],('Total Marketplace','',money(awsm_total))),
    'Marketplace products are identified by their product code (a Marketplace product ID rather than an AWS service code) and excluded from the AWS rows. Line items are rounded individually, so a list can differ from its total by a cent. UnblendedCost including VAT (20% on AWS services; none on Marketplace products), matching the AWS console. No RI/Savings Plan/discount breakdown yet. Production/Development is an AWS Cost Category, not separate AWS accounts.')
vb_sorted=sorted(vb,key=lambda r:(vorder.index(r['category']) if r['category'] in vorder else 99,-num(r['cost'])))
cards+=card('Vonage — by category',f'vonage_services.sql · {MONTH} · Europe/London dates · <strong>EUR</strong>',
    bars([(k,v) for k,v in von.items()],'€')+
    table('Full breakdown — category, product, direction',['Category','Product','Direction','Records','Cost'],
          [(esc(r['category']),esc(r['product']),esc(r['direction']),f"{int(r['n']):,}",money(r['cost'],'€')) for r in vb_sorted],
          ('All categories','','',f"{int(vm['n']):,}",money(von_total,'€'))),
    f"<strong>Currency is EUR, not USD.</strong> Vonage's API leaves the <code>currency</code> field blank on SMS rows ({int(vm['blank']):,} of {int(vm['n']):,} this month); the total assumes EUR like every other category. The five categories cover every record — nothing is unallocated. \"Other\" (VOICE-TTS) near €0 is expected.")

css=open(os.path.join(HERE,'dashboard.css.html')).read()
page=f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Billing Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700;800&family=Public+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
{css}
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="eyebrow">Cost overview — last month</div>
    <h1>Billing dashboard</h1>
    <div class="sub"><strong>{MONTH}</strong> — every GCP, AWS and Vonage cost in one place: the summary table, then a card per source with its full list. GCP uses US/Pacific month boundaries to match the Billing console and invoice; AWS and Vonage use Europe/London dates.</div>
  </header>

  <section class="card summary-wrap">
    <div class="summary-scroll">
    <table class="summary">
      <thead><tr><th>Source</th><th>Cost</th></tr></thead>
      <tbody>{summary}</tbody>
    </table>
    </div>
    <div class="summary-caption">{caption}
    </div>
  </section>
{cards}
  <footer class="card notes">
    Generated by the <code>billing-dashboard</code> skill for {MONTH}, with each query's window pinned to the month (GCP {_start} to {_next} US/Pacific; GCP invoice month {IM}; AWS and Vonage {_start} to {_last}). GCP from <code>bq_dataset_billing_ufonia_invoice</code>; AWS from <code>bg_dataset_aws_cost_and_usage</code> (<code>aws-bigquery-loader</code>); Vonage from <code>bq_dataset_vonage_cost_and_usage</code> (<code>vonage-bigquery-loader</code>). GCP's export can still pick up small late adjustments for a few days after month end.
  </footer>
</div>
</body>
</html>
'''
open(os.path.join(S,'billing-dashboard.html'),'w').write(page)
print('ok', len(page), 'bytes;', page.count('class="card chart-card"'),'cards;', len(rows),'summary rows')
