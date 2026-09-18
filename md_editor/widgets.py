from django.forms.widgets import Textarea
from django.template.loader import render_to_string

from django.forms.utils import flatatt
from django.utils.encoding import force_str
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe


class MDEditorWidget(Textarea):
    """洛谷风格的 Markdown 编辑器控件。

    渲染的编辑器改造自上游 luogu-markdown-editor（MIT），
    适配方式与升级步骤见 md_editor/vendor/README.md。

    几点需要知道：

    * 上游脚本用全局 id 取元素（#editorTextarea / #previewContent / 各弹窗），
      所以**一个页面只能挂载一个**该控件；同页出现两个时只有第一个能初始化。
    * 内容由编辑器写回它自己的 textarea，该 textarea 带 name，
      因此原生表单提交即可，不需要隐藏域同步。
    * 额外属性（含 Django 生成的 id）落在最外层容器上，而不是真正的输入元素；
      label 的 for 不会聚焦到编辑器内部，这是适配的已知取舍。
    * 不把 required 透传到内部 textarea：编辑器切到「纯预览」模式时它会隐藏，
      隐藏的必填控件会让浏览器报 "An invalid form control is not focusable"。
      必填校验交给服务端做。
    """

    def __init__(self, attrs=None, compact=False):
        super().__init__(attrs)
        self.compact = compact

    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            value = ''

        extra_attrs = dict(attrs or {})
        # class 要给容器自己的，避免和 .lmd-root.lmd-widget 冲突
        extra_attrs.pop('class', None)

        return mark_safe(render_to_string('md_editor.html', {
            'final_attrs': flatatt(extra_attrs),
            'value': conditional_escape(force_str(value)),
            'name': name,
            'compact': self.compact,
        }))
