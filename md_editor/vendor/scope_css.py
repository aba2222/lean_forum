#!/usr/bin/env python3
"""把上游 Luogu 编辑器的 styles.css 改写成作用域隔离版。

上游 styles.css 是给「整页单应用」写的，开头就是全局重置：

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { width: 100%; height: 100%; overflow: hidden; ... }

直接塞进 Django 模板会把整个论坛页面的排版冲垮（所有元素 margin/padding 归零、
页面滚动被 overflow:hidden 吃掉）。所以这里做一次机械改写：

    :root                      -> .lmd-root            （变量要落在包裹元素上）
    html / body                -> .lmd-root            （原样收进包裹元素）
    [data-theme="dark"]        -> .lmd-root[data-theme="dark"]
    [data-theme="dark"] .foo   -> .lmd-root[data-theme="dark"] .foo
    其余选择器 X                -> .lmd-root X

@keyframes / @font-face / @import / @page 的内容不做改写。

用法：
    python md_editor/vendor/scope_css.py <输入.css> <输出.css> [作用域选择器]
"""

import sys

import tinycss2

SCOPE = '.lmd-root'

# 这些 at-rule 的内容不是选择器，原样保留
KEEP_AS_IS = {'keyframes', 'font-face', 'font-feature-values', 'counter-style', 'page'}
# 这些 at-rule 的内容是选择器，需要递归改写
RECURSE = {'media', 'supports', 'layer', 'container', 'document'}


def scope_one(selector):
    """给单个选择器加上作用域前缀。"""
    sel = ' '.join(selector.split())
    if not sel:
        return sel

    if sel.startswith(':root'):
        return SCOPE + sel[len(':root'):]
    if sel.startswith('[data-theme'):
        return SCOPE + sel
    if sel in ('html', 'body'):
        return SCOPE
    if sel.startswith('html ') or sel.startswith('body '):
        return SCOPE + sel[len('html'):]
    if sel.startswith('.lmd-root'):
        return sel
    return SCOPE + ' ' + sel


def scope_prelude(prelude):
    """按顶层逗号切分选择器组，逐个加前缀。"""
    groups, current = [], []
    for token in prelude:
        if token.type == 'literal' and token.value == ',':
            groups.append(current)
            current = []
        else:
            current.append(token)
    groups.append(current)

    out = []
    for group in groups:
        raw = tinycss2.serialize(group).strip()
        if raw:
            out.append(scope_one(raw))
    return ',\n'.join(out)


def transform(rules, depth=0, stats=None):
    chunks = []
    for rule in rules:
        if rule.type == 'qualified-rule':
            chunks.append(scope_prelude(rule.prelude) + '{' + tinycss2.serialize(rule.content) + '}')
            if stats is not None:
                stats['scoped'] += 1

        elif rule.type == 'at-rule':
            keyword = rule.lower_at_keyword
            prelude = tinycss2.serialize(rule.prelude or [])

            if rule.content is None:
                chunks.append('@%s %s;' % (rule.at_keyword, prelude))
                continue

            if keyword in KEEP_AS_IS:
                chunks.append('@%s %s{%s}' % (rule.at_keyword, prelude, tinycss2.serialize(rule.content)))
                if stats is not None:
                    stats['kept'] += 1
                continue

            inner_rules = tinycss2.parse_rule_list(rule.content, skip_whitespace=True, skip_comments=True)
            inner = transform(inner_rules, depth + 1, stats)
            chunks.append('@%s %s{\n%s\n}' % (rule.at_keyword, prelude, inner))

        elif rule.type in ('comment', 'whitespace'):
            if depth == 0:
                chunks.append(rule.serialize())
        elif rule.type == 'error':
            chunks.append(rule.serialize())

    return '\n'.join(chunks)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding='utf-8') as fh:
        css = fh.read()

    rules = tinycss2.parse_stylesheet(css, skip_whitespace=True, skip_comments=False)
    stats = {'scoped': 0, 'kept': 0}
    body = transform(rules, 0, stats)

    header = (
        '/* 由 vendor/scope_css.py 从上游 styles.css 生成，请勿手改。\n'
        '   作用域：%s —— 所有选择器都被限制在该容器内，\n'
        '   避免上游的全局重置（* { margin:0 } / html,body { overflow:hidden }）污染论坛页面。 */\n\n'
        % SCOPE
    )

    with open(dst, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(header + body + '\n')

    print('scoped rules: %d, kept as-is blocks: %d' % (stats['scoped'], stats['kept']))
    print('written:', dst)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
