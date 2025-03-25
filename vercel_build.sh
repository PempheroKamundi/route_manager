#!/bin/bash

# Print environment information
echo "Node version: $(node -v)"
echo "Python version: $(python --version)"

# Install only production dependencies
pip install -r requirements-prod.txt

# Make sure the application directory is in the Python path
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Set up Django settings
export DJANGO_SETTINGS_MODULE=route_manager.settings

# Collect static files - but skip this if not needed for API-only deployment
# python manage.py collectstatic --noinput

# Create output directories for Vercel
mkdir -p .vercel/output/functions/api
mkdir -p .vercel/output/static

# Create a simple config.json for the Vercel build output
echo '{
  "version": 3,
  "routes": [
    {
      "src": "/(.*)",
      "dest": "/api/index.py"
    }
  ]
}' > .vercel/output/config.json

# Copy all necessary files to the function directory
# Only copy what's necessary for your API to run
cp -r api .vercel/output/functions/
cp -r repository .vercel/output/functions/api/
cp -r routing .vercel/output/functions/api/
cp -r trip_planner .vercel/output/functions/api/
cp -r hos_rules .vercel/output/functions/api/
cp -r route_manager .vercel/output/functions/api/
cp manage.py .vercel/output/functions/api/
cp requirements-prod.txt .vercel/output/functions/api/

# Clean up any unnecessary files that might bloat your deployment
find .vercel/output/functions/api -name "*.pyc" -delete
find .vercel/output/functions/api -name "__pycache__" -type d -exec rm -rf {} +
find .vercel/output/functions/api -name "*.log" -delete
find .vercel/output/functions/api -name "*.egg-info" -type d -exec rm -rf {} +
find .vercel/output/functions/api -name ".pytest_cache" -type d -exec rm -rf {} +

echo "Build completed"
