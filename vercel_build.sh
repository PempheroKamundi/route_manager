#!/bin/bash

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Create output directory for Vercel
mkdir -p public

# Copy static files to public directory
cp -r staticfiles/* public/
