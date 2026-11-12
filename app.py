"""Opportunity Ledger: localhost-only opportunity economics and experiment tracking."""
import argparse, csv, io, json, os, secrets, sqlite3, threading, webbrowser
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATUSES = {'idea', 'testing', 'won', 'delivered', 'lost'}

def amount(value, name, maximum='1000000000'):
    if isinstance(value, bool): raise ValueError(f'{name} must be a number')
    try: n = Decimal(str(value))
    except InvalidOperation: raise ValueError(f'{name} must be a number')
    if not n.is_finite() or n < 0 or n > Decimal(maximum):
        raise ValueError(f'{name} must be between 0 and {maximum}')
    return n

def cents(value, name):
    return int((amount(value, name) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def metrics(row):
    r = dict(row)
    fee = int((Decimal(r['price_cents']) * Decimal(str(r['fee_percent'])) / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    costs = r['direct_cents'] + r['acquisition_cents'] + fee
    contribution = r['price_cents'] - costs
    hours = Decimal(str(r['hours']))
    labor = int((hours * r['target_hourly_cents']).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    numerator = r['direct_cents'] + r['acquisition_cents'] + labor
    break_even = int((Decimal(numerator) / (1 - Decimal(str(r['fee_percent'])) / 100)).quantize(Decimal('1'), rounding='ROUND_CEILING'))
    r.update(fee_cents=fee, contribution_cents=contribution, target_labor_cents=labor,
             surplus_cents=contribution-labor, break_even_cents=break_even,
             hourly_cents=int((Decimal(contribution)/hours).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if hours else None,
             margin_percent=round(contribution/r['price_cents']*100,1) if r['price_cents'] else None,
             expected_contribution_cents=int((Decimal(contribution)*Decimal(str(r['probability']))/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP)))
    return r

def validate(data):
    def short(key, default='', limit=500):
        value=data.get(key,default)
        if not isinstance(value,str): raise ValueError(f'{key} must be text')
        value=value.strip()
        if len(value)>limit: raise ValueError(f'{key} is too long')
        return value
    title=short('title',limit=120)
    if not title: raise ValueError('Give the opportunity a title')
    status=short('status','idea')
    if status not in STATUSES: raise ValueError('Invalid status')
    fee=amount(data.get('fee_percent',0),'fee percent','99')
    return dict(title=title,category=short('category','Service',60),status=status,
        price_cents=cents(data.get('price',0),'price'),direct_cents=cents(data.get('direct_cost',0),'direct cost'),
        acquisition_cents=cents(data.get('acquisition_cost',0),'acquisition cost'),
        hours=float(amount(data.get('hours',0),'hours','100000')),
        target_hourly_cents=cents(data.get('target_hourly',0),'target hourly pay'),
        fee_percent=float(fee),probability=float(amount(data.get('probability',50),'probability','100')),
        next_action=short('next_action'),notes=short('notes',limit=4000))

class Store:
    def __init__(self,path):
        self.path=str(path)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,status TEXT NOT NULL,
            price_cents INTEGER NOT NULL,direct_cents INTEGER NOT NULL,acquisition_cents INTEGER NOT NULL,
            hours REAL NOT NULL,target_hourly_cents INTEGER NOT NULL,fee_percent REAL NOT NULL,
            probability REAL NOT NULL,next_action TEXT NOT NULL,notes TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY,opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
            channel TEXT NOT NULL,contacts INTEGER NOT NULL,replies INTEGER NOT NULL,wins INTEGER NOT NULL,
            spend_cents INTEGER NOT NULL,revenue_cents INTEGER NOT NULL,notes TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY,message TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            INSERT OR IGNORE INTO settings VALUES('currency','USD');
            ''')
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db: yield db
        finally: db.close()
    def log(self,db,message):
        db.execute('INSERT INTO activity(message,created_at) VALUES (?,?)',(message,datetime.now(timezone.utc).isoformat()))
    def snapshot(self):
        with self.db() as db:
            return dict(opportunities=[metrics(r) for r in db.execute('SELECT * FROM opportunities ORDER BY updated_at DESC,id DESC')],
                        experiments=[dict(r) for r in db.execute('SELECT * FROM experiments ORDER BY id DESC')],
                        activity=[dict(r) for r in db.execute('SELECT * FROM activity ORDER BY id DESC LIMIT 50')],
                        currency=db.execute("SELECT value FROM settings WHERE key='currency'").fetchone()[0])
    def save(self,data):
        fields=validate(data);stamp=datetime.now(timezone.utc).isoformat()
        with self.db() as db:
            if data.get('id') is not None:
                oid=int(data['id']);version=int(data.get('version',0))
                assignments=','.join(k+'=?' for k in fields)
                cur=db.execute(f'UPDATE opportunities SET {assignments},version=version+1,updated_at=? WHERE id=? AND version=?',[*fields.values(),stamp,oid,version])
                if cur.rowcount!=1: raise Conflict('This record changed or was removed. Refresh before saving.')
            else:
                columns=','.join(fields)+',updated_at';marks=','.join('?' for _ in range(len(fields)+1))
                oid=db.execute(f'INSERT INTO opportunities({columns}) VALUES ({marks})',[*fields.values(),stamp]).lastrowid
            self.log(db,f"Saved opportunity: {fields['title']}")
        return oid
    def experiment(self,data):
        def count(key):
            n=data.get(key,0)
            if isinstance(n,bool) or not isinstance(n,int) or n<0 or n>1000000: raise ValueError(f'{key} must be a whole number from 0 to 1000000')
            return n
        contacts,replies,wins=(count(k) for k in ('contacts','replies','wins'))
        if wins>replies or replies>contacts: raise ValueError('Use wins <= replies <= contacts')
        channel=str(data.get('channel','')).strip();notes=str(data.get('notes','')).strip()
        if not channel or len(channel)>100 or len(notes)>2000: raise ValueError('Provide a short channel and notes under 2000 characters')
        with self.db() as db:
            oid=int(data['opportunity_id'])
            if not db.execute('SELECT 1 FROM opportunities WHERE id=?',(oid,)).fetchone(): raise ValueError('Opportunity not found')
            db.execute('INSERT INTO experiments(opportunity_id,channel,contacts,replies,wins,spend_cents,revenue_cents,notes,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                (oid,channel,contacts,replies,wins,cents(data.get('spend',0),'spend'),cents(data.get('revenue',0),'revenue'),notes,datetime.now(timezone.utc).isoformat()))
            self.log(db,f'Recorded experiment: {channel}')
    def delete(self,data):
        with self.db() as db:
            oid=int(data['id']);version=int(data['version'])
            row=db.execute('SELECT title FROM opportunities WHERE id=? AND version=?',(oid,version)).fetchone()
            if not row: raise Conflict('Record changed. Refresh first.')
            db.execute('DELETE FROM experiments WHERE opportunity_id=?',(oid,))
            db.execute('DELETE FROM opportunities WHERE id=?',(oid,))
            self.log(db,'Deleted opportunity: '+row['title'])
    def demo(self):
        with self.db() as db:
            if db.execute('SELECT count(*) FROM opportunities').fetchone()[0]: raise ValueError('Demo data can only be loaded into an empty workspace')
        for title,price,cost,hours,category in [('Garden cleanup package',240,35,5,'Local service'),('Website accessibility review',450,20,7,'Digital service'),('Handmade gift box',65,32,2,'Product')]:
            self.save(dict(title=title,price=price,direct_cost=cost,hours=hours,target_hourly=30,acquisition_cost=15,fee_percent=3,probability=50,category=category,next_action='Interview one potential buyer; record what they need.',notes='Fictional example. Prices are illustrations, not recommended market rates.'))

class Conflict(Exception): pass

def handler_for(store,token):
    class Handler(BaseHTTPRequestHandler):
        def send(self,status,payload,kind='application/json'):
            raw=payload if isinstance(payload,bytes) else json.dumps(payload).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers();self.wfile.write(raw)
        def valid_host(self): return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
        def do_GET(self):
            if not self.valid_host(): return self.send(403,{'error':'Use the printed localhost address'})
            path=urlparse(self.path).path
            if path=='/api/state': return self.send(200,store.snapshot())
            if path=='/api/session': return self.send(200,{'token':token})
            if path=='/api/export':
                snap=store.snapshot();snap.pop('activity');snap['format_version']=1
                return self.send(200,snap)
            if path=='/api/csv':
                output=io.StringIO();rows=store.snapshot()['opportunities']
                keys=['title','category','status','price_cents','contribution_cents','hours','hourly_cents','surplus_cents','next_action']
                writer=csv.DictWriter(output,fieldnames=keys);writer.writeheader()
                for r in rows:
                    # Neutralize spreadsheet formula injection in user-entered text.
                    writer.writerow({k:("'"+r[k] if isinstance(r[k],str) and r[k].lstrip().startswith(('=','+','-','@')) else r[k]) for k in keys})
                return self.send(200,output.getvalue().encode(),'text/csv; charset=utf-8')
            files={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
            if path in files:
                mime={'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[path]
                return self.send(200,(ROOT/'static'/files[path]).read_bytes(),mime)
            self.send(404,{'error':'Not found'})
        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-Local-Token')!=token:
                return self.send(403,{'error':'Invalid local session'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length<1 or length>100000: return self.send(413,{'error':'Request too large or empty'})
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict): raise ValueError('Expected an object')
                if self.path=='/api/opportunities': store.save(data)
                elif self.path=='/api/experiments': store.experiment(data)
                elif self.path=='/api/delete': store.delete(data)
                elif self.path=='/api/demo': store.demo()
                elif self.path=='/api/settings':
                    currency=data.get('currency')
                    if currency not in {'USD','EUR','GBP','BRL','CAD','AUD'}: raise ValueError('Unsupported currency')
                    with store.db() as db:
                        db.execute("UPDATE settings SET value=? WHERE key='currency'",(currency,))
                else: return self.send(404,{'error':'Not found'})
                self.send(200,store.snapshot())
            except Conflict as exc: self.send(409,{'error':str(exc)})
            except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as exc: self.send(400,{'error':str(exc)})
            except Exception:
                self.log_error('Unexpected server error');self.send(500,{'error':'Unexpected server error'})
    return Handler

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--db',default=str(ROOT/'ledger.db'));parser.add_argument('--open',action='store_true')
    args=parser.parse_args();store=Store(args.db)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(store,secrets.token_urlsafe(32)))
    url=f'http://127.0.0.1:{server.server_port}'
    print(f'Opportunity Ledger: {url}\nData stays on this computer. Press Ctrl+C to stop.',flush=True)
    if args.open: threading.Timer(.5,lambda:webbrowser.open(url)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
