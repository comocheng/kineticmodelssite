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


def sign_in_redirect(request, message, next_url=None):
    """Send an anonymous visitor to the login page, then back to `next_url` or the last page."""
    from urllib.parse import urlencode, urlparse

    from django.contrib import messages
    from django.shortcuts import redirect
    from django.utils.http import url_has_allowed_host_and_scheme

    if next_url is None:
        referer = request.META.get('HTTP_REFERER', '')
        if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
            next_url = urlparse(referer).path
        else:
            next_url = '/'
    messages.info(request, message)
    return redirect(f"{settings.LOGIN_URL}?{urlencode({'next': next_url})}")


def write_login_required(message='Sign in to do this.'):
    """
    Require a signed-in user for requests that change something (any method but GET and HEAD),
    also while SITE_REQUIRE_LOGIN is off. Starting and stopping import jobs, pulling RMG-models
    and opening pull requests act on the server and on GitHub, so they must have a name on them.
    """
    from functools import wraps

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in ('GET', 'HEAD') and not request.user.is_authenticated:
                return sign_in_redirect(request, message)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
