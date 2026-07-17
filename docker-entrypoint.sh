#!/bin/sh
set -eu

alembic upgrade head
exec werewolf-server --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
