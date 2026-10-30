#!/usr/bin/env bash
set -euo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_root="${SUBBOOST_BUILD_ROOT:-$PWD/work}"
mkdir -p -- "$build_root"
build_dir=$(mktemp -d "$build_root/subboost-phone-build.XXXXXXXX")
trap 'rm -rf -- "$build_dir"' EXIT
python3 "$source_dir/prepare.py" "$build_dir"
docker build --network host --progress plain \
  -t local/subboost:2.8.1-phone-stash-v1 "$build_dir"
