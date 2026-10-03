#!/bin/sh
# Full Experiment A run: fresh engine container, deploy both channels, send all messages + controls,
# then collect engine output, statistics and log counts into results/.
set -e
cd "$(dirname "$0")"
SRC=../../out/run/hl7v2
docker rm -f exp-oie >/dev/null 2>&1 || true
docker run -d --name exp-oie -m 2g -p 127.0.0.1:8443:8443 -p 127.0.0.1:6661:6661 -p 127.0.0.1:6662:6662 \
  openintegrationengine/engine:latest >/dev/null
until docker logs exp-oie 2>&1 | grep -q 'successfully started'; do sleep 3; done
docker exec exp-oie mkdir -p /opt/engine/appdata/in
python3 build_channel.py
rm -rf results && mkdir -p results
python3 send_mllp.py --port 6661 --src "$SRC" --out results/strict-acks.jsonl --controls > results/strict-ack-summary.json
python3 send_mllp.py --port 6662 --src "$SRC" --out results/lenient-acks.jsonl --controls > results/lenient-ack-summary.json
# File Reader test: drop the .hl7 files in, wait until the engine has written a line per message
docker cp "$SRC/." exp-oie:/opt/engine/appdata/in/
docker exec -u 0 exp-oie chown -R engine:engine /opt/engine/appdata/in
for i in $(seq 1 60); do
  n=$(docker exec exp-oie sh -c 'cat /opt/engine/appdata/out/exp-v2-file.jsonl 2>/dev/null | wc -l')
  left=$(docker exec exp-oie sh -c 'ls /opt/engine/appdata/in | wc -l')
  [ "$left" -eq 0 ] && [ "$n" -gt 0 ] && break
  sleep 5
done
sleep 5
docker cp exp-oie:/opt/engine/appdata/out/exp-v2-file.jsonl results/engine-file.jsonl || true
docker cp exp-oie:/opt/engine/appdata/out/exp-v2-strict.jsonl results/engine-strict.jsonl
docker cp exp-oie:/opt/engine/appdata/out/exp-v2-lenient.jsonl results/engine-lenient.jsonl
docker logs exp-oie > results/engine.log 2>&1
python3 channel_stats.py > results/engine-stats.json
python3 analyze_engine.py --src "$SRC" --manifest ../../out/run/fhir-messy/defects.manifest.jsonl > results/engine-analysis.json
cat results/engine-analysis.json

# Validators (HAPI 2.3 runs inside the engine container, hl7apy in a local venv) and checks
./validate_hapi.sh "$SRC" > results/hapi.jsonl
./validate_hapi.sh controls > results/hapi-controls.jsonl
python3 summarize_hapi.py results/hapi.jsonl > results/hapi-summary.json
${HL7APY_PY:-python3} validate_hl7apy.py "$SRC" > results/hl7apy.json
python3 coverage_check.py ../../out/run/fhir-messy > results/coverage.txt
python3 obr3_length_check.py "$SRC" > results/obr3.txt
