"""Read-only checks and feature replay; no sample execution or training."""
import collections, csv, hashlib, json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'code'))
import native_release_features as nf
import native_features as native
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 index=read(ROOT/'checksums.json');listed={x['path']for x in index['files']}
 actual={p.relative_to(ROOT).as_posix()for p in ROOT.rglob('*')if p.is_file()}
 assert actual==listed|{'checksums.json'},'Unexpected or missing package files'
 for x in index['files']:
  p=ROOT/x['path'];assert p.is_relative_to(ROOT)and not p.is_symlink()
  assert p.stat().st_size==x['bytes']and sha(p)==x['sha256'],x['path']
 schema=read(ROOT/'feature-schema.json');sets={};groups={};report={}
 for name,expected in nf.DEPENDENCIES.items():assert sha(ROOT/'code'/name)==expected
 assert sha(ROOT/'code/native_release_features.py')==nf.EXTRACTOR_SHA256
 for part,n in [('development',287),('historical-test',96)]:
  manifest=read(ROOT/part/'manifest.json');rows=manifest['records']
  assert len(rows)==manifest['record_count']==n
  bysha={r['sample_sha256']:r for r in rows};assert len(bysha)==n
  sets[part]=set(bysha);groups[part]={r['software_group']for r in rows}
  tables={}
  for view in schema:
   with (ROOT/part/('features-'+view+'.csv')).open(encoding='utf-8',newline='')as f:
    reader=csv.DictReader(f);assert reader.fieldnames==['sample_sha256','run_id']+schema[view]['columns']
    entries=list(reader);assert len(entries)==n;tables[view]={x['sample_sha256']:x for x in entries}
    assert set(tables[view])==set(bysha)
  supported=collections.Counter()
  for row in rows:
   key=row['sample_sha256'];payload=read(ROOT/row['native_input_path'])
   assert payload['sha256']==key and payload['run_id']==row['run_id']
   for k in ['static','dynamic']:
    assert payload[k]['sha256']==key and payload[k]['run_id']==row['run_id']
   raw_static=read(ROOT/row['static_report_path'])
   assert {k:v for k,v in payload['static']['report'].items()if k!='evidence_binding'}=={k:v for k,v in raw_static.items()if k!='evidence_binding'}
   assert payload['static']['report']['evidence_binding']=={'run_id':row['run_id'],'sha256':key}
   assert payload['dynamic']['report']==read(ROOT/row['sandbox_telemetry_path'])
   payload['static']['report']['managed_metadata']=read(ROOT/row['managed_metadata_path'])
   quality=read(ROOT/row['capture_quality_path'])
   assert quality['sha256']==key and quality['run_id']==row['run_id']
   for view in schema:
    expected=row['feature_availability'][view];table=tables[view][key]
    assert table['run_id']==row['run_id']
    try:
     values=native.extract(payload)if view=='native-v2'else nf.extract(payload,view)
     assert expected['supported'];supported[view]+=1
    except nf.InputError as e:
     assert not expected['supported']and expected['reason']==e.code
     values={k:None for k in schema[view]['columns']}
    assert list(values)==schema[view]['columns']
    for k,value in values.items():
     actual=None if table[k]==''else float(table[k])
     assert (actual is None and value is None)or(actual is not None and value is not None and math.isclose(actual,value,rel_tol=1e-12,abs_tol=1e-12)),(key,view,k)
  counts=dict(collections.Counter(str(r['publisher_label'])for r in rows))
  assert counts==manifest['class_counts']
  report[part]={'records':n,'class_counts':counts,'supported':dict(supported)}
 assert not sets['development']&sets['historical-test']
 assert not groups['development']&groups['historical-test']
 folds=read(ROOT/'development/splits/grouped-folds.json')
 assert set(folds['all_retained_sha_order'])==sets['development']
 print(json.dumps({'verified':True,'files':len(listed)+1,'datasets':report,'sha_and_group_intersection':0,'feature_replay_tolerance':1e-12},indent=2))
if __name__=='__main__':main()
