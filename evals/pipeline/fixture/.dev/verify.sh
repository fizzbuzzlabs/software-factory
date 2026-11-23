#!/bin/sh
exec python3 "$(cat "$(dirname "$0")/harness-path")/verify.py" "$@"
