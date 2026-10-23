"""Temporary public access for the site's web tools."""

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import AccessMixin


def site_access_allowed(user):
    return not getattr(settings, 'SITE_REQUIRE_LOGIN', False) or user.is_authenticated


site_login_required = user_passes_test(site_access_allowed)


class SiteLoginRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not site_access_allowed(request.user):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


def site_access(request):
    """Keep navigation and editing controls consistent with view access."""
    return {'site_access_allowed': site_access_allowed(request.user)}


def actor_name(request):
    return request.user.username if request.user.is_authenticated else 'anonymous'
