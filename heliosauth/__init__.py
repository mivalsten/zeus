

from django.conf import settings
from . import auth_systems

TEMPLATE_BASE = settings.AUTH_TEMPLATE_BASE or "auth/templates/base.html"

# enabled auth systems
ENABLED_AUTH_SYSTEMS = settings.AUTH_ENABLED_AUTH_SYSTEMS or list(auth_systems.AUTH_SYSTEMS.keys())
DEFAULT_AUTH_SYSTEM = settings.AUTH_DEFAULT_AUTH_SYSTEM or None
