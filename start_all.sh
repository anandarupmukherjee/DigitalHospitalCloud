#!/bin/bash

# Start all Django applications

cd "$(dirname "$0")"

# Start Histopath on port 8001
cd histopath_local/stock_control
source venv/bin/activate
python manage.py runserver 8001 &
HIST_PID=$!
cd ../..

# Start Genomics on port 8002
cd genomics_local/stock_control
source venv/bin/activate
python manage.py runserver 8002 &
GEN_PID=$!
cd ../..

# Start Tracker on port 8003
cd tracker_local
source venv/bin/activate
python manage.py runserver 8003 &
TRACK_PID=$!
cd ..

echo "Started Django applications:"
echo "  - Histopath on port 8001 (PID: $HIST_PID)"
echo "  - Genomics on port 8002 (PID: $GEN_PID)"
echo ""
echo "To stop all applications, run: ./stop_all.sh"
echo "Processes saved to pids.txt"

echo "$HIST_PID" > pids.txt
echo "$GEN_PID" >> pids.txt
