import os
import sys

# Add the project root to the path
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, path)

# Set the Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "route_manager.settings")

# Import the Django ASGI application
from route_manager.asgi import application


# Handler for Vercel serverless function
def handler(request, response):
    return application(request, response)
