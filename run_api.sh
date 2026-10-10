#!/bin/bash
# Use the correct python interpreter to run the server
python3 -m uvicorn app.api:app --reload --port 8000
