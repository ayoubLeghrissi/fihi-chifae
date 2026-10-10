#!/usr/bin/env bash
# Load test the production Docker image at several crowd sizes and record
# resource usage, then build the report (perf/report.py).
#
#   PERF_USERS="5 100 1000" PERF_DURATION=60 PERF_CPUS=1 PERF_MEMORY=512m bash perf/run.sh
#
# Each stage starts a FRESH container + volume with the same CPU/RAM limits
# (default: 1 vCPU / 512 MB, close to a small Railway instance) and the demo
# catalog, so stages are comparable. Nothing touches real data.
set -uo pipefail

IMAGE="${PERF_IMAGE:-fihi-chifae:perf}"
USERS="${PERF_USERS:-5 100 1000}"
DURATION="${PERF_DURATION:-60}"
CPUS="${PERF_CPUS:-1}"
MEMORY="${PERF_MEMORY:-512m}"
OUT="${PERF_OUT:-perf-results}"
PORT="${PERF_PORT:-18000}"
NAME=fihi-perf-app
VOL=fihi-perf-data
ADMIN_PASSWORD=perf-admin-pass
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

USERS="${USERS//,/ }"
mkdir -p "$OUT"
echo "{\"image\": \"$IMAGE\", \"users\": \"$USERS\", \"duration_s\": $DURATION, \"cpus\": \"$CPUS\", \"memory\": \"$MEMORY\", \"git_sha\": \"${GITHUB_SHA:-local}\", \"started\": \"$(date -u +%FT%TZ)\"}" > "$OUT/run.json"

stop_all() {
  [ -n "${SAMPLER:-}" ] && kill "$SAMPLER" 2>/dev/null
  docker rm -f "$NAME" >/dev/null 2>&1
  docker volume rm "$VOL" >/dev/null 2>&1
}
trap stop_all EXIT

for N in $USERS; do
  echo "================ stage: $N concurrent users (${DURATION}s, ${CPUS} vCPU, ${MEMORY}) ================"
  stop_all
  docker run -d --name "$NAME" -p "$PORT:8000" -v "$VOL:/data" \
    --cpus "$CPUS" --memory "$MEMORY" \
    -e FIHI_ADMIN_PASSWORD="$ADMIN_PASSWORD" -e FIHI_SEED_DEMO=1 -e FIHI_TRUST_PROXY=0 \
    -e FIHI_ORDER_RATE_LIMIT=100000000 -e FIHI_NEWSLETTER_RATE_LIMIT=100000000 \
    "$IMAGE" >/dev/null
  for _ in $(seq 1 60); do curl -fs "http://127.0.0.1:$PORT/api/v1/ping" >/dev/null && break; sleep 0.5; done

  # resource sampler: one JSON line per second, prefixed with a timestamp
  docker stats --format '{{json .}}' "$NAME" 2>/dev/null \
    | while IFS= read -r line; do
        line="${line//$'\e'\[2J/}"; line="${line//$'\e'\[H/}"; line="${line//$'\e'\[J/}"
        [ -n "$line" ] && printf '%s|%s\n' "$(date +%s.%N)" "$line"
      done > "$OUT/u${N}_docker_stats.txt" &
  SAMPLER=$!

  RATE=$(( N / 10 )); [ "$RATE" -lt 1 ] && RATE=1   # ramp up over ~10 s
  PERF_ADMIN_PASSWORD="$ADMIN_PASSWORD" locust -f "$HERE/locustfile.py" --headless \
    -u "$N" -r "$RATE" -t "${DURATION}s" --host "http://127.0.0.1:$PORT" \
    --csv "$OUT/u${N}" --csv-full-history --html "$OUT/u${N}_locust.html" \
    --only-summary --stop-timeout 5 --loglevel WARNING || true

  kill "$SAMPLER" 2>/dev/null; SAMPLER=
  docker inspect -f '{"oom_killed": {{.State.OOMKilled}}, "restarts": {{.RestartCount}}, "running": {{.State.Running}}}' "$NAME" \
    > "$OUT/u${N}_container.json" 2>/dev/null || echo '{"running": false}' > "$OUT/u${N}_container.json"
  docker logs --tail 300 "$NAME" > "$OUT/u${N}_server.log" 2>&1
done

python "$HERE/report.py" "$OUT"
