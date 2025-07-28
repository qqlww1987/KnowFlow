#!/usr/bin/env bash

set -e

# Default settings
ENABLE_WEBSERVER=1
ENABLE_TASKEXECUTOR=1
CONSUMER_NO_BEG=0
CONSUMER_NO_END=0
WORKERS=1
HOST_ID=$(hostname)

# Parse arguments
for arg in "$@"; do
  case $arg in
    --disable-webserver)
      ENABLE_WEBSERVER=0
      shift
      ;;
    --disable-taskexecutor)
      ENABLE_TASKEXECUTOR=0
      shift
      ;;
    --consumer-no-beg=*)
      CONSUMER_NO_BEG="${arg#*=}"
      shift
      ;;
    --consumer-no-end=*)
      CONSUMER_NO_END="${arg#*=}"
      shift
      ;;
    --workers=*)
      WORKERS="${arg#*=}"
      shift
      ;;
    --host-id=*)
      HOST_ID="${arg#*=}"
      shift
      ;;
    *)
      echo "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

# Function to run task executor
function task_exe() {
    local consumer_id="$1"
    local host_id="$2"

    if command -v pkg-config &> /dev/null && pkg-config --exists jemalloc; then
        JEMALLOC_PATH="$(pkg-config --variable=libdir jemalloc)/libjemalloc.so"
        echo "Starting task executor ${host_id}_${consumer_id} with jemalloc..."
        while true; do
            LD_PRELOAD="$JEMALLOC_PATH" python rag/svr/task_executor.py "${consumer_id}"
        done
    else
        echo "Starting task executor ${consumer_id} without jemalloc..."
        while true; do
            python rag/svr/task_executor.py "${consumer_id}"
        done
    fi
}

# Start components
if [[ "${ENABLE_WEBSERVER}" -eq 1 ]]; then
    echo "Starting ragflow_server..."
    python api/ragflow_server.py &
fi

if [[ "${ENABLE_TASKEXECUTOR}" -eq 1 ]]; then
    if [[ "${CONSUMER_NO_END}" -gt "${CONSUMER_NO_BEG}" ]]; then
        echo "Starting task executors on host '${HOST_ID}' for IDs in [${CONSUMER_NO_BEG}, ${CONSUMER_NO_END})..."
        for (( i=CONSUMER_NO_BEG; i<CONSUMER_NO_END; i++ ))
        do
          task_exe "${i}" "${HOST_ID}" &
        done
    else
        echo "Starting ${WORKERS} task executor(s) on host '${HOST_ID}'..."
        for (( i=0; i<WORKERS; i++ ))
        do
          task_exe "${i}" "${HOST_ID}" &
        done
    fi
fi

wait 