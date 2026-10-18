#!/bin/sh
set -eu
mkdir -p /data
chown -R app:app /data
exec su-exec app "$@"