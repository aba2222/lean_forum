#!/usr/bin/env python3
"""把需要的 Prism 语言包合并成一个文件。

上游 assets/prism/ 里有 290+ 个语言文件，整页应用只按需引用了 5 个。
这里按「代码块弹窗里可选的语言 + 论坛常见的几种」挑一组合并，
把请求数从十几次降到一次。

Prism 的语言文件都是 `(function(Prism){ ... })(Prism);` 形式，
直接拼接即可，执行顺序按下面的 LANGUAGES 列表（有依赖的要排在前面）。

用法：
    python md_editor/vendor/build_prism_bundle.py <上游 assets/prism 目录> <输出文件>
"""

import sys
from pathlib import Path

# 顺序有意义：clike 由核心提供，cpp 依赖 c，typescript 依赖 javascript
LANGUAGES = [
    'c', 'cpp', 'python', 'java', 'pascal', 'rust', 'go',
    'javascript', 'typescript', 'json', 'bash', 'sql',
    'markup', 'css', 'markdown', 'yaml', 'ini', 'diff',
]


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    prism_dir = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    chunks = [
        '/* 由 vendor/build_prism_bundle.py 从上游 assets/prism 合并生成，请勿手改。',
        '   语言：%s */' % ', '.join(LANGUAGES),
        '',
    ]

    missing = []
    for lang in LANGUAGES:
        path = prism_dir / ('prism-%s.min.js' % lang)
        if not path.exists():
            missing.append(lang)
            continue
        chunks.append('/* --- %s --- */' % lang)
        chunks.append(path.read_text(encoding='utf-8').strip())
        chunks.append('')

    out_path.write_text('\n'.join(chunks), encoding='utf-8', newline='\n')

    print('bundled %d languages -> %s (%d KB)' % (
        len(LANGUAGES) - len(missing), out_path, out_path.stat().st_size // 1024))
    if missing:
        print('missing upstream files:', ', '.join(missing))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
