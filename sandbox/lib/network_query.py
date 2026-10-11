#!/usr/bin/env python3
"""Shared network allocation CLI for Bash host adapters."""
import json
import sys
from sandbox_core.network import NetworkAllocation, proxy_config

if sys.argv[1] == "proxy":
    print(json.dumps(proxy_config(json.load(sys.stdin), sys.argv[2])))
else:
    allocation = NetworkAllocation.at(sys.argv[2], int(sys.argv[3]))
    print(getattr(allocation, sys.argv[1]))
