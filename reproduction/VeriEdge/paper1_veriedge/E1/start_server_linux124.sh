#!/usr/bin/env bash
set -euo pipefail
LOCAL_NODE=linux124 exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/real_e1.sh" server
