#!/bin/sh
# Run validate_hapi.js inside the exp-oie container (HAPI 2.3 + v2.5.1 structures ship with the engine).
#   ./validate_hapi.sh <folder of .hl7 files> > results/hapi.jsonl
set -e
docker exec -u 0 exp-oie rm -rf /tmp/v2in
docker cp "$1" exp-oie:/tmp/v2in
docker cp "$(dirname "$0")/validate_hapi.js" exp-oie:/tmp/validate_hapi.js
docker exec -w /opt/engine exp-oie sh -c 'CP=$(find server-lib client-lib extensions -name "*.jar" | tr "\n" ":"); java -cp "$CP" org.mozilla.javascript.tools.shell.Main /tmp/validate_hapi.js /tmp/v2in 2>/dev/null'
