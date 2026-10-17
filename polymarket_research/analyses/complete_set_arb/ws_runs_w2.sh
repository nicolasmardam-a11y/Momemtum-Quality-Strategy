#!/bin/bash
# Window 2: three consecutive websocket monitoring segments, each re-selecting near-miss groups from the latest REST scan.
cd /home/user/Momemtum-Quality-Strategy/polymarket_research
for run in 4 5 6; do
  f=$(ls -1 data/derived/complete_set_arb/scan_1*_groups.parquet | tail -1)
  python -m analyses.complete_set_arb.ws_monitor "$f" 20 "run$run"
done
