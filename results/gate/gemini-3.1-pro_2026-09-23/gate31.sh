#!/bin/bash
export CHAMPSIM_ROOT=$HOME/champsim PYTHONPATH=$HOME/champsim A3_VERTEX_REGION=global
cd ~/chia_loop
for i in 1 2 3; do
  echo "=== attempt $i $(date -u +%H:%M:%S)"
  ~/miniconda3/envs/chia_env/bin/python -u translation_check.py --out ~/loop_out/tcheck31_$i --model gemini-3.1-pro-preview > ~/loop_out/tcheck31_$i.log 2>&1
  echo "exit $?"; tail -4 ~/loop_out/tcheck31_$i.log
done
echo "=== done $(date -u +%H:%M:%S)"
