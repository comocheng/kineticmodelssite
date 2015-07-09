from django.contrib import admin

from .models import Kinetics, Reaction, Species, Stoichiometry, Author, Source, KineticModel

# class ReactionInline(admin.TabularInline):
#     model=Reaction
#     extra=3
# 
# class QuestionAdmin(admin.ModelAdmin):
#     fieldsets=[
#         (None, {'fields':['question_text']}),
#         ('Date information', {'fields':['pub_date'],'classes': ['collapse']}),
#     ]
#     inlines=[ChoiceInline]
#     list_display = ('question_text', 'pub_date','was_published_recently')
#     list_filter=['pub_date']
#     search_fields = ['question_text']
# 
admin.site.register(Reaction)
admin.site.register(Species)
admin.site.register(Stoichiometry)
admin.site.register(Kinetics)
admin.site.register(Source)
admin.site.register(Author)
admin.site.register(KineticModel)
# 
# # Register your models here.

