# 第三方组件声明

本目录下的 Markdown 编辑器及其运行依赖来自以下第三方项目。
它们的许可证全文随附于本目录，**再分发时请一并保留**。

本目录内容的使用方式与升级步骤见 [`../../vendor/README.md`](../../vendor/README.md)。

---

## 洛谷 Markdown & KaTeX 实时预览编辑器

- 来源：https://github.com/wudream813/luogu-markdown-editor
- 版本：1.23.1
- 许可：MIT License
- 全文：[`LICENSE`](LICENSE)

Copyright (c) 2026 wudream813

本目录下除 `katex/`、`prism/` 子目录外的文件均来自该项目：
`editor.js`、`luogu-parser.js`、`luogu-linter.js`、`luogu-math-cheatsheet.js`、
`luogu-templates.js`、`luogu-typora.js`、`styles.css`。

其中 `styles.scoped.css`、`prism-bundle.js` 与本仓库的 `templates/md_editor.html`
是**派生文件**（由 `md_editor/vendor/` 下的脚本从上述源码生成，见该目录的说明），
同样按 MIT 许可分发。

---

## KaTeX

- 用途：数学公式渲染（`$...$` / `$$...$$`）
- 主页：https://katex.org/
- 许可：MIT License
- 全文：[`katex/LICENSE`](katex/LICENSE)

Copyright (c) 2013-2020 Khan Academy and other contributors

本仓库收录了 KaTeX 的 `katex.min.js`、`katex.min.css` 与 `fonts/` 下的 woff2 字体。

---

## Prism

- 用途：代码块语法高亮
- 主页：https://prismjs.com/
- 许可：MIT License
- 全文：[`prism/LICENSE`](prism/LICENSE)

Copyright (c) 2012 Lea Verou

本仓库收录了 Prism 核心（`prism.js`）、`prism-tomorrow.min.css` 主题，
以及 `prism-bundle.js` —— 后者由 `md_editor/vendor/build_prism_bundle.py`
从上游 290+ 个语言定义里挑出本项目用得到的 18 种合并而成。

---

## 与 Lean Forum 的关系

Lean Forum 本身以 AGPL-3.0 发布（见仓库根目录 `LICENSE`），
与本目录这些 MIT 组件相互独立：MIT 允许被 AGPL 项目使用与再分发，
条件是保留上述版权与许可声明。
