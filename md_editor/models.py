from django.db import models
from django.forms.fields import CharField

from .widgets import MDEditorWidget


class MDTextFormField(CharField):
    def __init__(self, **kwargs):
        kwargs.update({'widget': MDEditorWidget()})
        super().__init__(**kwargs)

class MDTextField(models.TextField):
    def formfield(self, **kwargs):
        defaults = {
            'form_class': MDTextFormField,
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)
