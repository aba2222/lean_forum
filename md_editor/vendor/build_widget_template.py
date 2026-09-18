#!/usr/bin/env python3
"""从上游 index.html 生成 Django 用的编辑器 widget 模板。

上游 index.html 是「整页单应用」：一个 #app 工作区 + 10 个模态框。
论坛里它要变成一个表单字段，所以做三件机械改动，其余原样搬运：

1. 去掉顶栏 .app-header（新建/打开/保存/导出/打印/一键复制发布/主题切换），
   这些是本地文件应用才需要的东西；论坛的保存动作由表单的提交按钮完成。
2. 把 #editorTextarea 换成真正参与表单提交的 textarea（带 name 与初值），
   编辑器自己就会把内容写回这个 textarea，不需要隐藏域同步。
3. 图片弹窗从「只能填 URL」改成「可上传到论坛 + 也可填外链」。

用法：
    python md_editor/vendor/build_widget_template.py <上游 index.html> <输出模板>
"""

import re
import sys
from pathlib import Path

TEMPLATE_HEAD = """{% load static %}
{% comment %}
  由 md_editor/vendor/build_widget_template.py 从上游 index.html 生成，请勿手改。
  行为改动请写在 luogu-widget.js / luogu-widget.css，或改生成器后重跑。

  注意：上游编辑器用全局 id 取元素（#editorTextarea / #previewContent / 各弹窗），
  所以每页只能挂载一个实例。同一页面要放第二个编辑器时需要先改造上游脚本。
{% endcomment %}
<link rel="stylesheet" href="{% static 'md_editor/luogu-widget.css' %}" />
<div
  class="lmd-root lmd-widget"
  data-lmd-editor
  data-lmd-static-base="{% static 'md_editor/luogu/' %}"
  data-image-upload-to="{% url 'upload_view' %}"
  {% if compact %}data-lmd-compact{% endif %}
  {{ final_attrs }}
>
"""

TEMPLATE_MID = """
"""

TEMPLATE_TAIL = """
<script src="{% static 'md_editor/luogu-widget.js' %}"></script>
<script>
  // 资源加载器由 base.html 以 defer 引入（与「已发布内容」的渲染器共用一份，内部按 profile 去重）。
  // defer 脚本先于 DOMContentLoaded 执行，所以这里登记时 LMDLoader 一定已就绪；
  // 而此刻 textarea 里仍是服务端渲染的初值 —— 上游 init() 会优先读 localStorage 草稿、
  // 读不到就塞一份演示模板，所以必须在这个时点把初值交给适配层。
  document.addEventListener('DOMContentLoaded', function () {
    var root = document.querySelector('[data-lmd-editor]');
    if (!root) return;
    if (window.LMDLoader) {
      window.LMDLoader.register(root);
    } else {
      console.error('[lmd] 找不到 LMDLoader：base.html 是否引入了 md_editor/luogu-loader.js？');
    }
  });
</script>
"""

# 图片弹窗整体替换：允许上传文件到论坛，也保留填外链的能力
IMAGE_MODAL = """<!-- 8. Image Modal（改造：可直接上传到论坛，也可填外链） -->
<div id="imageModal" class="modal-overlay">
  <div class="modal-dialog">
    <div class="modal-header">
      <h3 class="modal-title">🖼️ 插入图片</h3>
      <button class="modal-close-btn" onclick="LuoguEditor.closeModal('imageModal')">&times;</button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label class="form-label">图片描述 (Alt)</label>
        <input type="text" id="imageAltInput" class="form-input" placeholder="例如：算法示意图" />
      </div>
      <div class="form-group">
        <label class="form-label">从本地上传</label>
        <input type="file" id="imageFileInput" class="form-input" accept="image/png,image/jpeg,image/webp" />
        <div class="lmd-upload-hint" id="imageUploadHint">
          支持 JPG / PNG / WebP，单张不超过 10 MB；上传完成后会自动插入到光标处。
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">或填写图片 URL / 洛谷图床地址</label>
        <input type="text" id="imageUrlInput" class="form-input" placeholder="https://cdn.luogu.com.cn/upload/image_hosting/..." />
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn" onclick="LuoguEditor.closeModal('imageModal')">取消</button>
      <button class="btn btn-primary" onclick="LMDWidget.insertImageUrl()">插入图片</button>
    </div>
  </div>
</div>

"""


def slice_between(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    source = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    html = source.read_text(encoding='utf-8')

    # 1) 工作区：<div id="app"> 直到模态框注释之前
    app_block = slice_between(
        html,
        '<div id="app">',
        '<!-- ==========================================================================\n     Modals & Dialogs',
    )

    # 2) 模态框：从第一个模态框注释到 toastContainer 为止
    #    （不能切到 </body>，那里还有上游自己的 <script src="assets/...">，
    #      路径在论坛里不存在，而且我们用自己的加载器统一注入）
    toast_marker = (
        '<div id="toastContainer" class="toast-container" '
        'role="status" aria-live="polite" aria-atomic="true"></div>'
    )
    modals_start = html.index('<!-- 1. KaTeX Math Cheatsheet Modal -->')
    modals_end = html.index(toast_marker, modals_start) + len(toast_marker)
    modals_block = html[modals_start:modals_end]

    # 3) 顶栏整体移除（本地文件应用的操作区）
    header_start = app_block.index('<header class="app-header">')
    header_end = app_block.index('</header>', header_start) + len('</header>')
    app_block = app_block[:header_start] + app_block[header_end:]

    # 4) textarea 变成真正参与提交的表单控件
    old_textarea = (
        '<textarea id="editorTextarea" class="editor-textarea" '
        'placeholder="在此输入 Markdown 内容，右侧将实时渲染……" spellcheck="false"></textarea>'
    )
    new_textarea = (
        '<textarea id="editorTextarea" name="{{ name }}" class="editor-textarea" '
        'placeholder="在此输入 Markdown 内容，右侧将实时渲染……" '
        'spellcheck="false">{{ value }}</textarea>'
    )
    if old_textarea not in app_block:
        raise SystemExit('textarea 替换失败：上游 index.html 的结构变了，请检查')
    app_block = app_block.replace(old_textarea, new_textarea)

    # 5) 图片弹窗替换
    image_block = slice_between(
        modals_block,
        '<!-- 8. Image Modal -->',
        '<!-- 9. Luogu Formatting Diagnostic Modal -->',
    )
    modals_block = modals_block.replace(image_block, IMAGE_MODAL)

    # 6) 状态栏文案：论坛场景不落本地草稿
    app_block = app_block.replace(
        '<span id="saveStatusIndicator" role="status" aria-live="polite">已自动保存</span>',
        '<span id="saveStatusIndicator" role="status" aria-live="polite">尚未保存</span>',
    )

    # 7) 收敛空行
    app_block = re.sub(r'\n{3,}', '\n\n', app_block.strip())
    modals_block = re.sub(r'\n{3,}', '\n\n', modals_block.strip())

    template = TEMPLATE_HEAD + app_block + TEMPLATE_MID + modals_block + TEMPLATE_TAIL
    out_path.write_text(template, encoding='utf-8', newline='\n')

    print('written: %s (%d KB)' % (out_path, out_path.stat().st_size // 1024))
    print('app block: %d lines, modals: %d lines' % (
        app_block.count('\n') + 1, modals_block.count('\n') + 1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
