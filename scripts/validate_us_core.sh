#!/usr/bin/env bash
# Validate a few patient bundles against US Core 6.1.0 with the official HL7 validator (in Docker).
# Usage: scripts/validate_us_core.sh <bundle-folder> <out-folder> [count]
# Terminology checks are off (-tx n/a): codes are NOT checked against terminology servers.
set -euo pipefail
src=$1; dst=$2; n=${3:-3}
[ -f tools/validator_cli.jar ] || curl -sL -o tools/validator_cli.jar https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar
mkdir -p "$dst" .fhircache
ls "$src" | grep -v -E '^(hospital|practitioner)' | grep '\.json$' | head -"$n" > "$dst/sample.txt"
docker run --rm -m 6g -v "$PWD":/w -v "$PWD/.fhircache":/root/.fhir -w /w eclipse-temurin:17-jre sh -c \
  "for f in \$(cat $dst/sample.txt); do java -Xmx5g -jar tools/validator_cli.jar $src/\$f -version 4.0.1 -ig hl7.fhir.us.core#6.1.0 -tx n/a -output $dst/\$f.outcome.json > $dst/\$f.log 2>&1 || true; done"
python3 scripts/summarize_validation.py "$dst"
