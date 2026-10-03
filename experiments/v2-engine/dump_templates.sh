#!/bin/sh
# Serialize default engine objects using the jars inside the exp-oie container.
set -e
docker exec -u 0 exp-oie rm -rf /tmp/templates; docker cp "$(dirname "$0")/dump_templates.js" exp-oie:/tmp/dump_templates.js
docker exec -w /opt/engine exp-oie sh -c 'CP=$(find server-lib extensions -name "*.jar" | tr "\n" ":"); java -cp "$CP" org.mozilla.javascript.tools.shell.Main /tmp/dump_templates.js'
rm -rf "$(dirname "$0")/templates"
docker cp exp-oie:/tmp/templates "$(dirname "$0")/templates"
