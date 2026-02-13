#!/bin/bash
# Auto-detect hardware acceleration and launch with appropriate profile
# Usage: ./start.sh [up|down|clean] [--build] [cpu|nvidia|intel]

COMMAND="up"
BUILD_FLAG=""
PROFILE="cpu" # Default profile

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

if [ "$COMMAND" = "clean" ]; then
  echo "Cleaning up build caches and temporary files..."
  docker builder prune -f
  # Also clean local temp files if they exist
  rm -rf ./temp_files/*
  exit 0
fi

if [ "$COMMAND" = "down" ] || [ "$COMMAND" = "stop" ]; then
  echo "Stopping services for profile: $PROFILE"
  docker compose --profile "$PROFILE" down
  exit 0
fi

if [ "$MANUAL_PROFILE" != true ]; then
  echo "No profile specified — defaulting to CPU"
fi

echo "Starting services with profile: $PROFILE"
docker compose --profile "$PROFILE" up -d $BUILD_FLAG
