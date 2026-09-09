"""Assist manual L2 axis evidence; never writes TF or changes configuration."""
import argparse,csv,json,math,pathlib

def probe(path,limit=200):
    rows=[]
    with pathlib.Path(path).open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                p={k:float(row[k]) for k in ('x','y','z')}
                if all(math.isfinite(v) for v in p.values()):rows.append(p)
            except (KeyError,TypeError,ValueError):continue
    rows=sorted(rows,key=lambda p:p['x']*p['x']+p['y']*p['y']+p['z']*p['z'])[:limit]
    if not rows:return {'status':'NO_FINITE_POINTS','axis':None,'sample_count':0}
    mean={k:sum(p[k] for p in rows)/len(rows) for k in ('x','y','z')}
    axis=max(mean,key=lambda k:abs(mean[k]));sign='+' if mean[axis]>=0 else '-'
    return {'status':'OBSERVATION_ONLY','axis':sign+axis.upper()+'_lidar','centroid_native':mean,'sample_count':len(rows),'tf_written':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--csv',required=True);p.add_argument('--target',choices=('forward','left','ground'),required=True);p.add_argument('--output');a=p.parse_args();r=probe(a.csv);r['target_robot_direction']=a.target;r['verified_mounting_fact']='+Z_lidar -> +X_base';r['requires_human_confirmation']=True;text=json.dumps(r,indent=2)
    if a.output:
        with pathlib.Path(a.output).open('x',encoding='utf-8') as f:f.write(text)
    else:print(text)
