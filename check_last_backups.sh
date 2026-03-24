#!/bin/bash
source venv/bin/activate
uv pip install -r requirements.txt
python daily_report.py
