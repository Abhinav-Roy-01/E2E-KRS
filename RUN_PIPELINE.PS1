# RUN_PIPELINE.PS1 — polls and advances the full pipeline every INTERVAL_SECONDS.
# Run this from the E2E-KRS project root: .\RUN_PIPELINE.PS1
#
# This calls each service's OWN .venv python directly (no activation needed —
# .venv\Scripts\python.exe is a real, independent executable), so all four
# separately-installed environments run in sequence without conflicting.
#
# This is a polling-loop automation, not full event-driven (Redis Streams) —
# it's the pragmatic middle step: no manual "run this script now" between
# stages, but not yet the architecture doc's event-driven design either.
# Swap this out for real Redis Streams consumers once there's time to build
# that properly — the per-stage logic doesn't change, only how it's triggered.

$INTERVAL_SECONDS = 15
$ROOT = $PSScriptRoot

Write-Host "Starting E2E-KRS pipeline loop (every $INTERVAL_SECONDS seconds). Ctrl+C to stop." -ForegroundColor Cyan

while ($true) {
    Write-Host "`n--- $(Get-Date -Format 'HH:mm:ss') — running pipeline pass ---" -ForegroundColor Yellow

    Write-Host "[1/4] Ingest (MinIO -> parsed)" -ForegroundColor Green
    & "$ROOT\BACKEND\PARSER_SERVICE\.venv\Scripts\python.exe" "$ROOT\BACKEND\PARSER_SERVICE\APP\INGEST_PENDING.PY"

    Write-Host "[2/4] Classify (parsed -> classified)" -ForegroundColor Green
    & "$ROOT\BACKEND\CLASSIFIER_SERVICE\.venv\Scripts\python.exe" "$ROOT\BACKEND\CLASSIFIER_SERVICE\APP\CLASSIFY_PENDING.PY"

    Write-Host "[3/4] Translate (classified -> translated)" -ForegroundColor Green
    & "$ROOT\BACKEND\LANGUAGE_TRANSLATION_SERVICE\.venv\Scripts\python.exe" "$ROOT\BACKEND\LANGUAGE_TRANSLATION_SERVICE\APP\TRANSLATE_PENDING.PY"

    Write-Host "[4/4] Embed + index (translated -> indexed)" -ForegroundColor Green
    & "$ROOT\BACKEND\EMBEDDER_SERVICE\.venv\Scripts\python.exe" "$ROOT\BACKEND\EMBEDDER_SERVICE\APP\EMBED_PENDING.PY"

    Write-Host "--- pass complete, sleeping $INTERVAL_SECONDS s ---" -ForegroundColor Yellow
    Start-Sleep -Seconds $INTERVAL_SECONDS
}
