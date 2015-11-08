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
    return render_to_response('bibliography.html', variables, context_instance=RequestContext(request))
