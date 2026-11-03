import os

from django.conf import settings
from django.http import Http404
from django.views.static import serve


def docs(request, path=""):
    """The MkDocs guide at /docs/, from the build in settings.DOCS_ROOT.

    nginx serves /docs/ itself in the Docker deploy; this view serves it everywhere else.
    """
    root = settings.DOCS_ROOT
    if not os.path.isfile(os.path.join(root, "index.html")):
        raise Http404("The documentation is not built. Run bin/build-docs.sh.")
    if not path or path.endswith("/"):
        path += "index.html"
    # serve() keeps the path inside root
    return serve(request, path, document_root=root)
