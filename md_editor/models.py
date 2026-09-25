from django import forms
from django.db import models

from .widgets import MDEditorWidget


class MDTextFormField(forms.CharField):
    """带洛谷编辑器的表单字段。

    坑在这里：`models.TextField.formfield()` 会**无条件**注入
    `widget=forms.Textarea`（见 Django 源码的 TextField.formfield）。
    所以不能简单地 `kwargs.setdefault('widget', MDEditorWidget())` ——
    键总是存在，编辑器永远套不上，输入框会静默退化成普通 Textarea。

    这里把 Django 注入的默认 Textarea 当作「没指定控件」处理，
    只保留调用方显式传入的自定义控件（例如 MDEditorWidget(compact=True)）。
    """

    def __init__(self, **kwargs):
        widget = kwargs.get('widget')
        if widget is None or widget is forms.Textarea:
            kwargs['widget'] = MDEditorWidget()
        super().__init__(**kwargs)


class MDTextField(models.TextField):
    def formfield(self, **kwargs):
        defaults = {
            'form_class': MDTextFormField,
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)
