#!/bin/sh
set -eu
mkdir -p "$(dirname "$CLAIMS_PATH")"
if [ ! -f "$CLAIMS_PATH" ]; then
  cp /app/data/mock_claims.json "$CLAIMS_PATH"
fi
exec "$@"
