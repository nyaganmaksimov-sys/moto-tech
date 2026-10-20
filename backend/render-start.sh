#!/bin/sh
set -eu
exec uvicorn backend.api.main:app --host 0.0.0.0 --port "${PORT:-10000}"
