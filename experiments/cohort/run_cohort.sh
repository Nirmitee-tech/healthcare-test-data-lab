#!/usr/bin/env bash
# Generate only patients matching a keep module and measure the cost. Usage: experiments/cohort/run_cohort.sh <patients> <keep.json>
set -euo pipefail
n=$1; keep=$2; cd "$(dirname "$0")/../.."
out=experiments/cohort/tmp; rm -rf $out
start=$(date +%s)
docker run --rm -m 4g -v "$PWD":/w -w /w eclipse-temurin:17-jre java -Xmx3g -jar tools/synthea-with-dependencies.jar \
  -s 42 -cs 42 -r 20261003 -p $n -k $keep --exporter.baseDirectory=/w/$out --exporter.years_of_history=2 \
  --exporter.hospital.fhir.export=false --exporter.practitioner.fhir.export=false Massachusetts > $out.log 2>&1
echo "seconds=$(( $(date +%s) - start ))"; tail -4 $out.log | head -2
python3 - "$out/fhir" <<'P'
import json,glob,sys,collections
c=collections.Counter(); n=0
for f in glob.glob(sys.argv[1]+"/*.json"):
    b=json.load(open(f)); n+=1
    codes={cc.get("code") for e in b["entry"] if e["resource"]["resourceType"]=="Condition" for cc in e["resource"]["code"]["coding"]}
    c["has_diabetes_44054006"]+= "44054006" in codes
    c["has_prediabetes_714628002"]+= "714628002" in codes
print("patients",n,dict(c))
P
rm -rf $out
