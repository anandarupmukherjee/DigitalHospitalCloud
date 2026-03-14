#!/bin/bash

# Stop all Django applications

if [ -f pids.txt ]; then
    while read pid; do
        kill $pid 2>/dev/null && echo "Stopped process $pid"
    done < pids.txt
    rm pids.txt
    echo "All applications stopped"
else
    echo "No pids.txt file found. Processes may already be stopped."
fi
