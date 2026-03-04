#!/bin/bash
# Podman-optimized launch script for Voxtral-Subtitles
# Usage: ./start.sh [up|down|clean] [--build] [cpu|nvidia|intel]

COMMAND="up"
BUILD_FLAG=""
PROFILE="cpu" # Default profile

# Detect if podman-compose or docker-compose is used
if command -v podman-compose &> /dev/null; then
  COMPOSE_CMD="podman-compose"
else
  COMPOSE_CMD="docker compose"
fi

# Parse arguments
for arg in "$@"; do
  case $arg in
    up|down|stop)
      COMMAND="$arg"
      ;;
    clean)
      COMMAND="clean"
      ;;
    --build)
      BUILD_FLAG="--build"
      ;;
    cpu|nvidia|intel)
      PROFILE="$arg"
      MANUAL_PROFILE=true
      ;;
  esac
done

# Ensure temp directory exists with correct permissions
mkdir -p ./temp_files
chmod 777 ./temp_files

if [ "$COMMAND" = "clean" ]; then
  echo "Cleaning up build caches and temporary files..."
  if [ "$COMPOSE_CMD" = "podman-compose" ]; then
    podman builder prune -f
  else
    docker builder prune -f
  fi
  rm -rf ./temp_files/*
  exit 0
fi

if [ "$COMMAND" = "down" ] || [ "$COMMAND" = "stop" ]; then
  echo "Stopping services for profile: $PROFILE"
  $COMPOSE_CMD --profile "$PROFILE" down --volumes --remove-orphans
  exit 0
fi

if [ "$MANUAL_PROFILE" != true ]; then
  echo "No profile specified — defaulting to CPU"
fi

echo "Starting services with profile: $PROFILE using $COMPOSE_CMD"
$COMPOSE_CMD --profile "$PROFILE" up -d $BUILD_FLAG
