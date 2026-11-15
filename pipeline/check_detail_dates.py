"""Contract Z3. Standard-library structure, boundary, exact-count and provenance checks."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
SCHEMA='detail-dates-z3-v1'
STAYS=[168,336,708]
SHIFTS=[-7,-3,-1,1,3,7]
ROWS=['status','sun_h','earth_h','both_h','sun_frac','earth_frac','both_frac','longest_dark_h','dark_left_censored','dark_right_censored']
DELTAS=['status','target_day_index','delta_sun_h','delta_earth_h','delta_both_h','delta_longest_dark_h']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def integer(v):return isinstance(v,int) and not isinstance(v,bool)
def check_detail_dates(data,sites,err):
    data=Path(data);directory=data/'detail/dates'
    if not directory.exists():return
    root=data.resolve().parents[1]
    def require(c,m):
        if not c:raise ValueError(m)
    try:
        index=json.loads((directory/'index.json').read_text(encoding='utf8'))
        require(index['schema']==SCHEMA and index['mock'] is False,'schema/mock')
        require(index['first_landing']=='2026-01-01' and index['last_landing']=='2030-12-31' and index['n_landings']==1826,'landing domain')
        require(index['stay_h']==STAYS and index['slip_days']==SHIFTS,'stays/slips')
        entries=index['sites'];require(len(entries)==len(sites)==33,'33 catalogue entries required')
        require({e['id'] for e in entries}==set(sites),'index IDs')
        require({p.stem for p in directory.glob('*.json')}==set(sites)|{'index'},'file inventory')
    except (OSError,KeyError,ValueError,TypeError) as e:err('detail/dates/index.json',str(e));return
    for entry in entries:
        sid=entry['id'];where='detail/dates/'+sid+'.json'
        try:
            require(entry['file']==sid+'.json','unsafe/mismatched path')
            p=directory/entry['file'];require(sha(p)==entry['sha256'],'index file hash')
            o=json.loads(p.read_text(encoding='utf8'))
            require(o['id']==sid and o['lat']==sites[sid]['lat'] and o['lon']==sites[sid]['lon'],'coordinate identity')
            require(o['schema']==SCHEMA and o['mock'] is False,'schema/mock')
            require(o['content_sha256']==entry['content_sha256'],'index content hash')
            require(o['first_landing']=='2026-01-01' and o['last_landing']=='2030-12-31' and o['n_landings']==1826 and o['step_days']==1 and o['landing_time_utc']=='00:00:00','daily landing grid')
            require(o['hourly_cells']==dict(start_utc='2026-01-01T00:00:00Z',last_cell_start_utc='2030-12-31T23:00:00Z',end_exclusive_utc='2031-01-01T00:00:00Z',n=43824,rule='[i,i+1)'),'hourly cell coverage')
            require(o['row_columns']==ROWS and o['delta_columns']==DELTAS,'column definitions')
            require([s['stay_h'] for s in o['stays']]==STAYS,'stay inventory')
            for stay in o['stays']:
                h=stay['stay_h'];r=stay['rows']
                require(stay['stay_days']==h/24 and stay['delta_fraction_denominator_h']==h,'exact stay denominator')
                require(len(r)==1826,'all daily starts required')
                for d,row in enumerate(r):
                    require(isinstance(row,list) and len(row)==10,'base row shape')
                    valid=d*24+h<=43824
                    if not valid:require(row==['out_of_range']+[None]*9,'out-of-range row must be explicit nulls');continue
                    require(row[0]=='ok','valid stay marked invalid')
                    s,e,b=row[1:4];dark=row[7]
                    require(all(integer(v) and 0<=v<=h for v in (s,e,b,dark)),'integer hourly counts')
                    require(b<=min(s,e) and dark<=h-s,'subset/dark count')
                    require(row[4:7]==[s/h,e/h,b/h],'fractions must use exact counts, not rounded arrays')
                    require(type(row[8]) is bool and type(row[9]) is bool,'dark censor flags')
                require([x['shift_days'] for x in stay['slips']]==SHIFTS,'signed shift inventory')
                for slip in stay['slips']:
                    shift=slip['shift_days'];require(len(slip['rows'])==1826,'shift rows')
                    for d,delta in enumerate(slip['rows']):
                        j=d+shift;base=r[d];target=r[j] if 0<=j<1826 else None
                        bv=base[0]=='ok';tv=target is not None and target[0]=='ok'
                        status='ok' if bv and tv else 'both_out_of_range' if not bv and not tv else 'base_out_of_range' if not bv else 'target_out_of_range'
                        expected=[status,j,target[1]-base[1],target[2]-base[2],target[3]-base[3],target[7]-base[7]] if status=='ok' else [status,j,None,None,None,None]
                        require(delta==expected,'signed shift/count delta or range flag mismatch')
            inputs=o['inputs']
            paths={'ephem_sha256':data/'ephem.bin','ephem_metadata_sha256':data/'ephem.json','sites_sha256':data/'sites.json','horizon_sha256':data/'horizon'/(sid+'.json'),'core_sha256':root/'web/js/core.js','producer_sha256':root/'pipeline/build_detail_dates.mjs','cache_helper_sha256':root/'pipeline/cache_metrics.mjs'}
            for key,path in paths.items():require(inputs[key]==sha(path),'stale input '+key)
        except (OSError,KeyError,ValueError,TypeError,IndexError) as e:err(where,str(e))
    # Hash the complete canonical object and JSON.stringify(site) in JS to avoid
    # Python/JS shortest-double or exponent serialization differences.
    node=os.environ.get('LLSN_NODE') or shutil.which('node')
    if not node:err('detail/dates','Node is required for exact JS provenance');return
    js="""
    const fs=require('fs'),path=require('path'),crypto=require('crypto');
    const dir=process.argv[1],data=process.argv[2];
    const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
    const sort=v=>Array.isArray(v)?v.map(sort):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sort(v[k])])):v;
    const stable=v=>JSON.stringify(sort(v));
    const sites=JSON.parse(fs.readFileSync(path.join(data,'sites.json')));
    for(const site of sites){
      const obj=JSON.parse(fs.readFileSync(path.join(dir,site.id+'.json')));
      const {content_sha256,...content}=obj;
      if(sha(stable(content))!==content_sha256)throw Error(site.id+' content hash');
      const {signature,...inputs}=obj.inputs;
      if(sha(stable(inputs))!==signature)throw Error(site.id+' input signature');
      if(sha(JSON.stringify(site))!==inputs.site_sha256)throw Error(site.id+' exact site hash');
    }
    """
    result=subprocess.run([node,'-e',js,str(directory),str(data)],capture_output=True,text=True)
    if result.returncode:err('detail/dates',result.stderr.strip())
    print('detail/dates: 33 sites, full daily/stay/slip arrays checked')
