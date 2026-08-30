#!/bin/sh
set -e
# Expand ** recursively regardless of args passed ($@ ignored on purpose)
exec java -DPLANTUML_LIMIT_SIZE=${PLANTUML_LIMIT_SIZE:-4096} \
  -jar /opt/plantuml.jar -tpng -r "."