# 洛谷 Markdown 编辑器（第三方组件）

论坛的 Markdown 编辑器改造自 **[wudream813/luogu-markdown-editor](https://github.com/wudream813/luogu-markdown-editor)**，
用于支持洛谷扩展语法（`:::info` 折叠框、表格合并、Bilibili 嵌入等）与 KaTeX 公式的实时预览。

- 上游版本：`1.23.1`
- 上游许可证：MIT（见上游仓库 `LICENSE`）
- 本地化时间：见本目录文件的首次提交

---

## 为什么不能直接引用

上游是一份**整页单应用**，直接搬进 Django 模板有两个硬问题：

1. **全局样式会污染整个论坛页面。** 上游 `styles.css` 开头就是

   ```css
   *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
   html, body { width: 100%; height: 100%; overflow: hidden; ... }
   ```

   直接加载会把 Bootstrap 的所有间距清零、把整页滚动吃掉。

2. **脚本不能重复加载。** 上游是 13 个按顺序执行的 `<script>`，且 `editor.js` 顶层用了
   `const LuoguEditor = ...`，同一页面插入两次会抛 `Identifier has already been declared`。

所以做了三层隔离，**上游源码本身一行未改**，全部改造集中在生成器与适配层。

---

## 目录结构

```
md_editor/
├── vendor/                          # 构建工具（不参与运行时）
│   ├── scope_css.py                 # 把上游 styles.css 改写为作用域隔离版
│   ├── build_prism_bundle.py        # 合并需要的 Prism 语言包
│   └── build_widget_template.py     # 从上游 index.html 生成 templates/md_editor.html
├── templates/md_editor.html         # 生成物：编辑器工作区 + 10 个弹窗
└── static/md_editor/
    ├── luogu-loader.js              # 一次性顺序加载上游资源
    ├── luogu-widget.js              # 论坛适配层（内容/主题/图片上传/文件操作）
    ├── luogu-widget.css             # 宿主页面集成样式
    └── luogu/                       # 上游文件（原样）+ 两个生成物
        ├── editor.js                # 上游
        ├── luogu-parser.js          # 上游
        ├── luogu-linter.js          # 上游
        ├── luogu-math-cheatsheet.js # 上游
        ├── luogu-templates.js       # 上游
        ├── luogu-typora.js          # 上游
        ├── styles.css               # 上游（仅作参照，不加载）
        ├── styles.scoped.css        # 生成物（实际加载）
        ├── prism.js                 # 上游
        ├── prism-tomorrow.min.css   # 上游
        ├── prism-bundle.js          # 生成物
        └── katex/                   # 上游（katex.min.css/js + woff2 字体）
```

---

## 改动都放在哪

| 需求 | 改哪里 |
| --- | --- |
| 编辑器行为（图片上传、主题、文件操作） | `static/md_editor/luogu-widget.js` |
| 编辑器在页面里的尺寸/边框 | `static/md_editor/luogu-widget.css` |
| 资源加载顺序 | `static/md_editor/luogu-loader.js` |
| 工作区/弹窗的 HTML | `vendor/build_widget_template.py`，改完重跑生成器 |
| 上游样式 | 不要改 `styles.css`；要覆盖就在 `luogu-widget.css` 里写（用 `.lmd-root.lmd-widget` 提高优先级） |

---

## 重新生成生成物

```bash
# 需要 tinycss2（仅构建期使用，不是运行时依赖）
pip install tinycss2

python md_editor/vendor/scope_css.py \
    md_editor/static/md_editor/luogu/styles.css \
    md_editor/static/md_editor/luogu/styles.scoped.css

python md_editor/vendor/build_prism_bundle.py \
    <上游>/assets/prism \
    md_editor/static/md_editor/luogu/prism-bundle.js

python md_editor/vendor/build_widget_template.py \
    <上游>/index.html \
    md_editor/templates/md_editor.html
```

## 升级上游版本

1. 从上游仓库取新的 `src/*.js`、`src/styles.css`、`assets/katex/`（只要 `katex.min.css`、
   `katex.min.js` 与 `fonts/*.woff2`）、`assets/prism/` 覆盖到 `static/md_editor/luogu/`。
2. 重跑上面三条生成命令。
3. 检查 `build_widget_template.py` 里的替换锚点是否仍然命中（脚本会在锚点失配时报错退出，
   不会静默产出坏模板）。
4. 打开发帖页与评论框，确认双栏预览、公式、图片上传、亮暗主题都正常。

---

## 与论坛的接线

| 事项 | 做法 |
| --- | --- |
| 表单取值 | 编辑器把内容写回 `<textarea name="{{ name }}">`，走原生表单提交；适配层在 submit 时再兜一次底 |
| 图片上传 | `#imageFileInput` → `POST data-image-upload-to`（`md_editor.views.upload_view`），带头 `X-CSRFToken` |
| 主题 | 监听站点 `<html data-bs-theme>`，映射到上游 `setTheme('light'/'dark')`，并镜像到 `.lmd-root[data-theme]` |
| 本地草稿 | 上游的 `localStorage` 草稿键是全局的，会让 A 帖的草稿串进 B 帖，加载前统一清掉；适配层把 `autoSave` 替换为「尚未提交」提示 |
| 文件操作 | 「新建/打开/保存到本地/导出 HTML」在论坛里没有意义，适配层改成 toast 提示 |

---

## 已发布内容的渲染（保证「预览 == 发布后」）

渲染只保留**一个解析器**：上游的 `luogu-parser.js`。服务端那份 markdown-it + bleach 只作为
无脚本时的兜底，脚本就绪后会被覆盖。两份解析器迟早会漂移，一份不会。

链路：

```
Post.content（原始 Markdown）
   ├─ 服务端：markdown-it + bleach ──► content_html ──► 先塞进容器当兜底
   └─ 浏览器：luogu-render.js 用 LuoguParser.render(content) ──► 覆盖掉兜底
```

容器约定（`forum/templates/forum/_markdown.html`）：

```html
<div class="lmd-root lmd-content" data-luogu-markdown="<原始 Markdown>">
  <div class="preview-content"><服务端兜底 HTML></div>
</div>
```

用到的文件：

| 文件 | 作用 |
| --- | --- |
| `static/md_editor/luogu-loader.js` | 两套 profile（`editor` / `content`）共用一份资源与去重表；同时出现在一页时不会重复加载 |
| `static/md_editor/luogu-render.js` | 找到 `[data-luogu-markdown]` 并渲染；补上上游解析器输出需要的三个全局函数 |
| `static/md_editor/luogu-content.css` | 把「整页应用样式」收窄成「一段正文样式」 |

阅读视图与编辑器的两点**有意差异**：

- 任务清单是**只读**的（`disabled`），读者勾选没有意义——勾选不会写回 Markdown。
  除此之外渲染结果与编辑器预览逐字节一致（已用 headless Chrome 实测比对）。
- 编辑器额外提供滚动同步、行号、`data-src-line` 锚点等交互能力，这些不影响 HTML 结构。

前端只保留了这一套渲染栈，因此 `base.html` 里原来的
highlight.js / github-markdown-css / MathJax 都已移除（代码高亮改用 Prism，公式改用 KaTeX）。

## 已知限制

- **每页只能有一个编辑器实例。** 上游脚本按固定 id 取元素，同一页面挂载两个时只有第一个
  能初始化。当前站点每个表单只有一个 Markdown 字段，尚未触发。
- **编辑器的资源由 `base.html` 统一引入。** widget 模板只负责标记，注册发生在
  `DOMContentLoaded`（此时 `defer` 的加载器已就绪）。若把该字段渲染到不经 `base.html` 的页面，
  编辑器不会初始化。
- **`<label for>` 不会聚焦到编辑器内部。** Django 生成的 id 落在容器 div 上，而真正可聚焦的
  textarea 必须保留上游写死的 `id="editorTextarea"`。
- **不向内部 textarea 透传 `required`。** 编辑器切到「纯预览」模式会隐藏它，
  隐藏的必填控件会让浏览器报 `An invalid form control is not focusable`；必填校验交给服务端。
- **正文依赖 JS 才能渲染成洛谷排版。** 关闭脚本时只能看到服务端兜底的 markdown-it 结果，
  洛谷扩展语法（`:::info`、表格合并、Bilibili、KaTeX）不会生效。这是「只有一个解析器」
  这个选择的代价：要同时满足「无 JS 也好看」和「两处排版绝对一致」，就必须写第二份解析器，
  而两份解析器一定会漂移。
- **正文每次打开都要重新解析。** 解析器是 O(n)，官方基准 360KB 文档约 150ms；
  目前没有做服务端缓存或渲染结果回写。
