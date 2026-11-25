#!/usr/bin/env bash
# Render every 3D shot of a plan (resumable). render_all.sh <plan> <outdir> [samples]
cd "$(dirname "$0")/.."
PLAN=$1; OUT=$2; SMP=${3:-24}; BL=${BLENDER:-blender}
ids=$(python3 -c "import json;p=json.load(open('$PLAN'));print(' '.join(s['id'] for s in p['shots'] if 'set' in s))")
mkdir -p $OUT; echo "start $(date +%s)" > $OUT/progress.txt
for id in $ids; do
  $BL -b --python scripts/shot.py -- --plan $PLAN --shot $id --out $OUT/$id --samples $SMP > $OUT/$id.log 2>&1
  echo "$id $(grep -E '^\[S|^\[END' $OUT/$id.log | tail -1) $(grep -c Traceback $OUT/$id.log)" >> $OUT/progress.txt
done
echo "done $(date +%s)" >> $OUT/progress.txt
