#!/usr/bin/env bash

num_cores=$(sysctl -n hw.ncpu)
load_averages=$(sysctl -n vm.loadavg | awk '{print $2}')
cpu_usage=$(echo "scale=2; $load_averages * 100 / $num_cores" | bc)
cpu_usage=$(printf "%.0f" "$cpu_usage")

sketchybar -m --set cpu label="${cpu_usage}%"
