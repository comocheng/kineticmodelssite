from django.shortcuts import render
from django.http import HttpResponse
from django.template import RequestContext, loader

def index(request):
    return HttpResponse("This is the kinetic models index!")
