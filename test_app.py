import json, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from app import Store, Conflict, handler_for, metrics, validate

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'ledger.db')
    def tearDown(self): self.tmp.cleanup()
    def offer(self,**extra):
        return dict(title='Fictional offer',price=100,direct_cost=10,acquisition_cost=5,hours=2,target_hourly=20,fee_percent=3,probability=50,**extra)
    def test_exact_economics(self):
        self.store.save(self.offer());r=self.store.snapshot()['opportunities'][0]
        self.assertEqual((r['contribution_cents'],r['hourly_cents'],r['surplus_cents'],r['break_even_cents'],r['expected_contribution_cents']),(8200,4100,4200,5671,4100))
    def test_zero_hours_price_and_high_fees(self):
        d=self.offer();d.update(hours=0,price=0,fee_percent=99);self.store.save(d)
        r=self.store.snapshot()['opportunities'][0];self.assertIsNone(r['hourly_cents']);self.assertIsNone(r['margin_percent']);self.assertEqual(r['contribution_cents'],-1500)
    def test_invalid_inputs(self):
        for field,value in [('price',-1),('price','NaN'),('hours','Infinity'),('fee_percent',100),('probability',101),('title',' '),('status','invalid')]:
            d=self.offer();d[field]=value
            with self.subTest(field=field,value=value):
                with self.assertRaises(ValueError): self.store.save(d)
        self.assertEqual(self.store.snapshot()['opportunities'],[])
    def test_stale_edit_rejected(self):
        oid=self.store.save(self.offer());d=self.offer();d.update(id=oid,version=1,title='Changed');self.store.save(d)
        with self.assertRaises(Conflict):self.store.save(d)
        self.assertEqual(self.store.snapshot()['opportunities'][0]['title'],'Changed')
    def test_experiment_and_delete(self):
        oid=self.store.save(self.offer());self.store.experiment(dict(opportunity_id=oid,channel='Referrals',contacts=10,replies=4,wins=1,spend=5,revenue=100))
        snap=self.store.snapshot();self.assertEqual(snap['experiments'][0]['revenue_cents'],10000)
        self.store.delete({'id':oid,'version':1});self.assertEqual(self.store.snapshot()['experiments'],[])
    def test_bad_funnel_rejected(self):
        oid=self.store.save(self.offer())
        with self.assertRaises(ValueError): self.store.experiment(dict(opportunity_id=oid,channel='Test',contacts=1,replies=2,wins=0))
        self.assertFalse(self.store.snapshot()['experiments'])
    def test_persistence(self):
        self.store.save(self.offer());again=Store(self.store.path);self.assertEqual(len(again.snapshot()['opportunities']),1)
    def test_demo_no_accidental_double_seed(self):
        self.store.demo()
        with self.assertRaises(ValueError):self.store.demo()
        self.assertEqual(len(self.store.snapshot()['opportunities']),3)
    def test_http_token_and_exports(self):
        srv=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.store,'test-token'));thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{srv.server_port}'
        try:
            with urllib.request.urlopen(url+'/') as r:self.assertIn(b'Opportunity Ledger',r.read())
            req=urllib.request.Request(url+'/api/opportunities',json.dumps(self.offer()).encode(),{'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
            self.assertEqual(e.exception.code,403)
            req.add_header('X-Local-Token','test-token')
            with urllib.request.urlopen(req) as r:self.assertEqual(len(json.load(r)['opportunities']),1)
            with urllib.request.urlopen(url+'/api/export') as r:self.assertEqual(json.load(r)['format_version'],1)
            with urllib.request.urlopen(url+'/api/csv') as r:self.assertIn(b'Fictional offer',r.read())
        finally:srv.shutdown();srv.server_close();thread.join()

if __name__=='__main__':unittest.main()
