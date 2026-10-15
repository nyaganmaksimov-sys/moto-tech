#!/bin/sh
set -eu
mkdir -p /backup
while :; do
  target="/backup/mototech-$(date -u +%Y%m%d-%H%M%S).dump"
  pg_dump -Fc -f "$target"
  find /backup -type f -name 'mototech-*.dump' -mtime +13 -delete
  sleep 86400
done
