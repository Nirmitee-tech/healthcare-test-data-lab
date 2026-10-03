#!/bin/sh
# Rerun Synthea exactly like lab/pipeline.py generate() (same jar, seed, reference date, state),
# with 10 patients and the CSV, CPCDS and BFD (Blue Button RIF) exporters switched on, to see
# whether any exporter emits ICD-10-CM diagnoses or CPT/HCPCS procedure codes.
#   experiments/x12-837/run_synthea.sh [require_code_maps=false|true]
set -e
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT="$ROOT/experiments/x12-837/synthea-out"
REQ=${1:-false}
rm -rf "$OUT/synthea-$REQ"; mkdir -p "$OUT"
docker run --rm --name exp-synthea -m 2g -v "$ROOT:/w" -v "$OUT:/o" -w /w eclipse-temurin:17-jre \
  java -Xmx1536m -jar tools/synthea-with-dependencies.jar -s 42 -cs 42 -r 20261003 -p 10 \
  --exporter.baseDirectory=/o/synthea-$REQ --exporter.fhir.export=true \
  --exporter.csv.export=true --exporter.cpcds.export=true \
  --exporter.bfd.export=true --exporter.bfd.require_code_maps=$REQ \
  Massachusetts > "$OUT/synthea-$REQ.log" 2>&1 || echo "synthea exited non-zero, see synthea-$REQ.log"
