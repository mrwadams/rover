#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python rover_web.py
