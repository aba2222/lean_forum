from django import forms
from django.forms.widgets import Textarea
from django.template.loader import render_to_string

from django.forms.utils import flatatt
from django.utils.encoding import force_str
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe


class MDEditorWidget(Textarea):
    def render(self, name, value, attrs = None, renderer = None):
        final_attrs = self.build_attrs(self.attrs, {**attrs, "name" : name})
        return mark_safe(render_to_string('md_editor.html', {
            'final_attrs': flatatt(final_attrs),
            'value': conditional_escape(force_str(value)),
            'id': final_attrs['id'],
        }))
