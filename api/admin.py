from django.contrib import admin
from rest_framework.authtoken.admin import TokenAdmin

from api.models import Revision

TokenAdmin.raw_id_fields = ["user"]

admin.site.register(Revision)
