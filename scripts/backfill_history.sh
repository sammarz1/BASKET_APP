#!/usr/bin/env bash
set -euo pipefail

# Ensure we run from the project root
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Locate CLI binary
if [ -f ".venv/bin/basket-app" ]; then
    CLI=".venv/bin/basket-app"
elif command -v basket-app &> /dev/null; then
    CLI="basket-app"
else
    echo "Error: basket-app CLI not found. Please activate your virtualenv or run 'pip install -e .'"
    exit 1
fi

echo "================================================================="
echo "   STARTING FULL HISTORICAL BACKFILL (BRONZE MEDALLION LAYER)   "
echo "================================================================="
echo "Project Root : $ROOT_DIR"
echo "CLI Executable: $CLI"
echo "EuroLeague   : E2000 -> E2024 (all 8 endpoints)"
echo "NBA          : 2000-01 -> 2024-25 (all 7 endpoints)"
echo "Started at   : $(date)"
echo "================================================================="
echo ""

# Ensure MinIO is running
echo "Checking MinIO object storage..."
docker compose up -d minio createbuckets

# 1. Backfill EuroLeague History (from founding season E2000 to E2024)
echo ""
echo ">>> [1/2] Backfilling EuroLeague full history (E2000 to E2024)..."
$CLI backfill euroleague --start-season E2000 --end-season E2024

# 2. Backfill NBA History (from 2000-01 to 2024-25)
echo ""
echo ">>> [2/2] Backfilling NBA full history (2000-01 to 2024-25)..."
$CLI backfill nba --start-season 2000-01 --end-season 2024-25

echo ""
echo "================================================================="
echo "   FULL HISTORICAL BACKFILL COMPLETED SUCCESSFULLY              "
echo "   Finished at: $(date)"
echo "================================================================="

# Run an audit report upon completion
echo ""
$CLI audit
