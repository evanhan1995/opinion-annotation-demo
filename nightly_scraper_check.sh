#!/bin/bash
# Nightly XHS scraper validation
# Usage: bash nightly_scraper_check.sh
# Cron example: 0 8 * * * bash /d/Claude\ code/舆情标注Wiki/nightly_scraper_check.sh

PROJECT_DIR="/d/Claude code/舆情标注Wiki"
REPORT_DIR="$PROJECT_DIR/outputs/nightly"
TIMESTAMP=$(date +%Y%m%d_%H%M)
REPORT="$REPORT_DIR/scraper_check_$TIMESTAMP.json"
LOG="$REPORT_DIR/scraper_check_$TIMESTAMP.log"

mkdir -p "$REPORT_DIR"

echo "=== XHS Scraper Nightly Check $(date) ===" | tee "$LOG"

# Step 1: Verify Python and dependencies
echo "[1/4] Checking environment..." | tee -a "$LOG"
cd "$PROJECT_DIR" || exit 1
python -c "import sys; print(sys.executable)" >> "$LOG" 2>&1

# Step 2: Run XHS adapter unit tests
echo "[2/4] Running XHS unit tests..." | tee -a "$LOG"
python -m pytest tests/test_xhs_adapter.py -v --tb=short 2>&1 | tee -a "$LOG"
TEST_EXIT=$?

# Step 3: Dry-run scrape (1 known post)
echo "[3/4] Dry-run XHS scrape..." | tee -a "$LOG"
SCRAPE_RESULT=$(python -c "
from engine.scraper import scrape
import json
result = scrape('https://www.xiaohongshu.com/explore/69ff2eea000000001f005fcc')
print(json.dumps({
    'has_content': bool(result.get('content')),
    'content_len': len(result.get('content', '')),
    'has_comments': bool(result.get('comments')),
    'comment_count': len(result.get('comments', [])),
    'platform': result.get('platform'),
    'title': result.get('title', '')[:80]
}, ensure_ascii=False, indent=2))
" 2>&1)
echo "$SCRAPE_RESULT" | tee -a "$LOG"

# Step 4: Write structured report
echo "[4/4] Writing report..." | tee -a "$LOG"
cat > "$REPORT" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "test_exit_code": $TEST_EXIT,
  "scrape_result": $SCRAPE_RESULT,
  "status": "$([ $TEST_EXIT -eq 0 ] && echo 'pass' || echo 'fail')"
}
EOF

echo "" | tee -a "$LOG"
echo "Report: $REPORT" | tee -a "$LOG"
echo "Done." | tee -a "$LOG"
