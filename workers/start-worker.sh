#!/usr/bin/env bash
set -euo pipefail

WORKER_DIR="${WORKER_DIR:?WORKER_DIR is required}"
WORKER_REPLICAS="${WORKER_REPLICAS:-1}"
WORKER_ENTRYPOINT="${WORKER_ENTRYPOINT:-agent.py}"

if ! [[ "$WORKER_REPLICAS" =~ ^[0-9]+$ ]] || [ "$WORKER_REPLICAS" -lt 1 ]; then
  echo "WORKER_REPLICAS must be a positive integer"
  exit 1
fi

WORKER_PATH="/app/workers/${WORKER_DIR}"
VENV_PYTHON="${WORKER_PATH}/.venv/bin/python"

if [ ! -f "${WORKER_PATH}/${WORKER_ENTRYPOINT}" ]; then
  echo "Worker entrypoint not found: ${WORKER_PATH}/${WORKER_ENTRYPOINT}"
  exit 1
fi

if [ ! -x "${VENV_PYTHON}" ]; then
  echo "Worker virtualenv python not found: ${VENV_PYTHON}"
  exit 1
fi

cd "${WORKER_PATH}"

echo "Starting worker group: dir=${WORKER_DIR}, entrypoint=${WORKER_ENTRYPOINT}, replicas=${WORKER_REPLICAS}"

pids=()

cleanup() {
  for pid in "${pids[@]:-}"; do
    kill "${pid}" 2>/dev/null || true
  done
  wait || true
}

trap cleanup INT TERM

for i in $(seq 1 "${WORKER_REPLICAS}"); do
  echo "Starting replica ${i}/${WORKER_REPLICAS} for ${WORKER_DIR}"
  "${VENV_PYTHON}" "${WORKER_ENTRYPOINT}" &
  pids+=("$!")
done

set +e
wait -n "${pids[@]}"
status=$?
set -e

echo "A worker replica exited with status ${status}, stopping remaining replicas"
cleanup
exit "${status}"
