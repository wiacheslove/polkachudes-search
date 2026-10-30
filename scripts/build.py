"""Сборка поискового индекса «Полки Чудес» из публичного API Tilda.
Только чтение публичных данных; ключей и персональных данных нет.
Если выгрузка подозрительная — выходит с ошибкой и прежние файлы остаются."""
import json, re, sys, time, os, urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else 'docs'
ROOT, REC = '848566607491', '5076893701'
API = 'https://store.tildaapi.com/api/getproductslist/?storepartuid=%s&recid=%s&c=%d&size=500&filters%%5Bquantity%%5D=y' % (ROOT, REC, int(time.time()))
HDR = {'Referer': 'https://polkachudes.ru/catalog', 'User-Agent': 'polkachudes-search-index/1.0'}
MIN_TOTAL, MIN_RATIO = 1000, 0.8

def get(url, tries=3):
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=60).read())
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(10 * (i + 1))

meta = get(API + '&getparts=true&slice=1&size=1')
products, sl = [], 1
while True:
    d = get(API + '&slice=%d' % sl)
    products += d.get('products') or []
    if not d.get('nextslice'): break
    sl = d['nextslice']
    if sl > 40: sys.exit('слишком много страниц — остановка')

total = int(meta.get('total') or 0)
prev = 0
try: prev = json.load(open(os.path.join(OUT, 'status.json')))['count']
except Exception: pass
n = len(products)
print('товаров:', n, 'API total:', total, 'предыдущая сборка:', prev)
if n < MIN_TOTAL: sys.exit('мало товаров (%d) — файлы не обновлены' % n)
if total and n < total * 0.98: sys.exit('выгрузка неполная (%d из %d)' % (n, total))
if prev and n < prev * MIN_RATIO: sys.exit('товаров меньше %d%% от прошлой сборки — файлы не обновлены' % (MIN_RATIO * 100))

parts = {}
def walk(ps):
    for p in ps or []:
        parts[str(p['uid'])] = p['title']; walk(p.get('subparts'))
walk(meta.get('parts'))
clean = lambda h: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', (h or '').replace('&nbsp;', ' '))).strip()
def js(v, d):
    if isinstance(v, str):
        try: return json.loads(v)
        except Exception: return d
    return v or d
dic, D = {}, []
def ix(vals):
    out = []
    for v in vals:
        if not v: continue
        if v not in dic: dic[v] = len(D); D.append(v)
        out.append(dic[v])
    return out
core, thumbs = [], []
for p in products:
    ch = js(p.get('characteristics'), [])
    g = js(p.get('gallery'), [])
    img = (g[0].get('img', '') if g else '').replace('https://static.tildacdn.com/', '')
    pu = js(p.get('partuids'), [])
    try: price = round(float(p.get('price') or 0))
    except ValueError: price = 0
    core.append([p['uid'], p.get('title', ''),
                 ix(c['value'] for c in ch if c.get('title') == 'Фандом'),
                 ix(c['value'] for c in ch if c.get('title') == 'Тематика'),
                 ix([p.get('brand', '')]), clean(p.get('text')), price, '', '',
                 ix(parts.get(str(u), '') for u in pu)])
    thumbs.append([p['uid'], img, (p.get('url') or '').split('/tproduct/')[-1]])
built = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
os.makedirs(OUT, exist_ok=True)
def write(name, obj):
    tmp = os.path.join(OUT, name + '.tmp')
    json.dump(obj, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, os.path.join(OUT, name))
write('core.json', {'v': 1, 'built': built, 'd': D, 'r': core})
write('thumbs.json', thumbs)
write('status.json', {'built': built, 'count': n})
print('готово:', built)
