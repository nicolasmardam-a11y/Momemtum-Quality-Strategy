#!/bin/bash
# Three consecutive websocket monitoring segments, each re-selecting near-miss groups from the latest REST scan.
cd /home/user/Momemtum-Quality-Strategy/polymarket_research
for run in 1 2 3; do
  f=$(ls -1 data/derived/complete_set_arb/scan_*_groups.parquet | tail -1)
  python -m analyses.complete_set_arb.ws_monitor "$f" 18 "run$run"
done
