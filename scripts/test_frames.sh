#!/usr/bin/env bash
# one test frame per shot at low res: test_frames.sh <plan> <outdir> [res] [samples] [shot ids...]
PLAN=$1; OUT=$2; RES=${3:-270x480}; SMP=${4:-8}; shift 4
PY=${PY:-/home/claude/fv2/venv311/bin/python}
ids=${@:-$(python3 -c "import json;p=json.load(open('$PLAN'));print(' '.join(s['id'] for s in p['shots'] if 'set' in s))")}
for id in $ids; do
  f=$(python3 -c "import json;p=json.load(open('$PLAN'));s=[x for x in p['shots'] if x['id']=='$id'][0];print(int(((s['t0']+s['t1'])/2+s.get('test_dt',0))*p['fps']))")
  timeout 600 $PY -I scripts/shot.py --plan $PLAN --shot $id --out $OUT/$id --res $RES --samples $SMP --frames $f-$f > $OUT/$id.log 2>&1
  echo "$id f$f $(grep -E '^\[' $OUT/$id.log | tail -1) $(grep -E 'Error|Traceback' -A3 $OUT/$id.log | tail -3 | tr '\n' ' ')"
done
