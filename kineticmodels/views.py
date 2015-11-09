from django.shortcuts import render, render_to_response, get_object_or_404
from django.http import HttpResponse
from django.template import RequestContext, loader

from models import Source

def index(request):
#     template=loader.get_template('kineticmodels/index.html')
    return HttpResponse("This is the kinetic models index!")

def bibliography(request):
    """
    The listing of all the sources in the database
    """
    sources = Source.objects.all()
    variables = {'sources': sources}
    return render_to_response('kineticmodels/bibliography.html', variables, context_instance=RequestContext(request))

def source(request, source_id=0):
    """
    The listing of all the sources in the database
    """
    source = get_object_or_404(Source, id=source_id)
    variables = {'source': source}
    return render_to_response('kineticmodels/source.html', variables, context_instance=RequestContext(request))
