#!/usr/bin/env bash
# Prepare airflow/work/: a clone of the public `data` branch that the DAGs work on.
# Pushing is disabled in the clone: GitHub Actions is the only writer of `data`.
# Run it again to start from scratch (the clone is deleted and cloned again).
#
#   ./bin/init-work.sh               # the data branch
#   ./bin/init-work.sh data-fase-3   # another data branch (e.g. the one of a phase in progress)
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
work="$here/work"
repo="https://github.com/AdayCuestaCorrea/paleo-atlas.git"
branch="${1:-data}"

mkdir -p "$work" "$here/logs"
rm -rf "$work/data"
git clone --quiet --branch "$branch" --single-branch "$repo" "$work/data"
git -C "$work/data" remote set-url --push origin "DISABLED: Airflow never pushes"
echo "Cloned the $branch branch into $work/data ($(git -C "$work/data" log -1 --format='%h %s'))"
