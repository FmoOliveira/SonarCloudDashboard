#!/bin/bash
export PYTHONPATH=.:./src:./src/dashboard:./src/dashboard/database
pytest
ruff check src/dashboard/app.py
mypy src/dashboard/app.py --ignore-missing-imports
