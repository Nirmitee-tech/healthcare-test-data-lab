#!/usr/bin/env bash
# Size and time of Synthea output under different settings. Usage: experiments/scale/run_scale.sh <patients>
# Each variant is measured, then its output deleted (disk is tight). Results appended to results.tsv.
set -euo pipefail
n=${1:-200}; cd "$(dirname "$0")/../.."
out=experiments/scale/tmp; res=experiments/scale/results.tsv
[ -f $res ] || echo -e "variant\tpatients_requested\trecords\tseconds\tfhir_bytes\tfiles" > $res
run() {
  name=$1; shift; rm -rf $out; mkdir -p $out
  start=$(date +%s)
  docker run --rm -m 4g -v "$PWD":/w -w /w eclipse-temurin:17-jre java -Xmx3g -jar tools/synthea-with-dependencies.jar \
    -s 42 -cs 42 -r 20261003 -p $n --exporter.baseDirectory=/w/$out --exporter.hospital.fhir.export=false \
    --exporter.practitioner.fhir.export=false "$@" Massachusetts > $out.log 2>&1
  secs=$(( $(date +%s) - start ))
  recs=$(grep -o "total=[0-9]*" $out.log | cut -d= -f2)
  bytes=$(cat $out/fhir/* | wc -c | tr -d " "); files=$(ls $out/fhir | wc -l | tr -d ' ')
  echo -e "$name\t$n\t$recs\t$secs\t$bytes\t$files" >> $res
  rm -rf $out
}
run default_10y_history
run no_pretty --exporter.pretty_print=false
run full_history --exporter.years_of_history=0
run history_2y --exporter.years_of_history=2
run bulk_ndjson --exporter.fhir.bulk_data=true
