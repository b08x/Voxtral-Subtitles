#!/bin/bash
# Emergency stop script for Voxtral-Subtitles
# Forcibly removes all containers, pods and networks associated with the project

PROJECT_NAME=$(grep PROJECT_NAME .env | cut -d '=' -f2 | tr -d '"' | tr -d '\r')
PROJECT_NAME=${PROJECT_NAME:-voxtral-subtitles}

echo "🛑 Forcibly stopping and removing all project resources for: $PROJECT_NAME"

if command -v podman &> /dev/null; then
  echo "Using podman for cleanup..."
  # Stop and remove containers by name pattern
  podman ps -a --format "{{.Names}}" | grep "$PROJECT_NAME" | xargs -r podman stop -t 2
  podman ps -a --format "{{.Names}}" | grep "$PROJECT_NAME" | xargs -r podman rm -f
  
  # Remove pods if any
  podman pod ps --format "{{.Name}}" | grep "$PROJECT_NAME" | xargs -r podman pod rm -f
  
  # Cleanup unused networks
  podman network prune -f
else
  echo "Using docker for cleanup..."
  docker compose down --volumes --remove-orphans
fi

echo "✅ Cleanup complete."
