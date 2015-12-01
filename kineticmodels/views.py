from django.shortcuts import render, render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from django.core.urlresolvers import reverse

from forms import EditSourceForm
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

def source_editor(request, source_id=0):
    """
    Edit the details of a source
    """
    source = get_object_or_404(Source, id=source_id)
    if request.method == 'POST':
        form = EditSourceForm(request.POST, instance=source)
        if form.is_valid():
            # Save the form
            form.save()
            # Go back to the network's main page
            return HttpResponseRedirect(reverse(source, args=(source.id,)))
    else:
        # Create the form
        form = EditSourceForm(instance=source)
    variables = {'source': source,
                 'form': form, }
    return render_to_response('kineticmodels/source_editor.html', variables, context_instance=RequestContext(request))

def species(request):
    """
    The listing of all species currently in the database
    """

    sources = Source.objects.all()
    variables = {'sources',sources}

    return render_to_response('kineticmodels/species.html', variables, context_instance=RequestContext(request))

def species_editor(request):
    """
    The listing of all species currently in the database
    """

    source = get_object_or_404(Source, id=source_id)
    variables = {'source',source}

    return render_to_response('kineticmodels/species_editor.html', variables, context_instance=RequestContext(request))
