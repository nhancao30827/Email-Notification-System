#!/bin/sh
set -e

if [ "$#" -gt 0 ]; then
	echo "Starting custom command..."
	exec "$@"
fi

echo "Running database migrations..."
uv run alembic upgrade head

echo "Starting API server..."
exec uv run uvicorn main:app --host 0.0.0.0 --port 8000
