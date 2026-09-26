"""开发脚本自身的约束。

这些脚本很容易在后续编辑里悄悄坏掉，而且坏法都很隐蔽：
Windows PowerShell 5.1 读没有 BOM 的 .ps1 会按系统 ANSI 代码页（简体中文下
是 GBK）解码，中文注释直接变乱码，运气不好整个脚本解析不过去 ——
这类问题只有真的双击运行才会发现，所以这里用测试钉住。
"""

import io
import os
import re

from django.test import SimpleTestCase

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UTF8_BOM = b'\xef\xbb\xbf'


class DevScriptTests(SimpleTestCase):
    def read_bytes(self, name):
        path = os.path.join(REPO_ROOT, name)
        self.assertTrue(os.path.exists(path), f'{name} 不存在')
        with open(path, 'rb') as handle:
            return handle.read()

    def test_dev_ps1_starts_with_a_utf8_bom(self):
        """dev.ps1 必须带 UTF-8 BOM。

        没有 BOM 时 PowerShell 5.1 会按 GBK 解码，脚本里的中文会变成乱码，
        甚至直接抛 ParserError —— 而这个脚本的主要入口 dev.bat 调用的正是
        Windows PowerShell 5.1。
        """
        payload = self.read_bytes('dev.ps1')

        self.assertTrue(
            payload.startswith(UTF8_BOM),
            'dev.ps1 丢了 UTF-8 BOM：PowerShell 5.1 会按 GBK 读，中文会乱码。'
            '补回来的办法见文件头部的 .NOTES。',
        )

    def test_dev_ps1_decodes_as_utf8(self):
        payload = self.read_bytes('dev.ps1')
        self.assertIsInstance(payload.decode('utf-8'), str)

    def test_dev_ps1_declares_a_help_block(self):
        """有注释式帮助才能在 Get-Help .\\dev.ps1 里看到用法。"""
        text = self.read_bytes('dev.ps1').decode('utf-8')

        self.assertIn('.SYNOPSIS', text)
        self.assertIn('.EXAMPLE', text)
        self.assertIn('param(', text)

    def test_dev_ps1_does_not_use_powershell7_only_syntax(self):
        """只能写 PS 5.1 也认的语法。

        三元运算符 `? :`、`??`、`?.` 都是 PowerShell 7 才有的，
        在 5.1 里是硬解析错误。
        """
        text = self.read_bytes('dev.ps1').decode('utf-8')
        # 去掉注释和字符串，避免被中文说明里的符号误伤
        without_block_comments = re.sub(r'<#.*?#>', '', text, flags=re.S)
        code = '\n'.join(
            line for line in without_block_comments.split('\n')
            if not line.strip().startswith('#')
        )

        self.assertNotIn('??', code)
        self.assertNotIn('?.', code)
        self.assertNotRegex(code, r'\?\s+\S+\s+:\s+\S+')

    def test_dev_ps1_uses_the_venv_interpreter_not_path_python(self):
        """必须用 venv 里的解释器：PATH 上的 python 很可能是另一个版本。"""
        text = self.read_bytes('dev.ps1').decode('utf-8')

        self.assertIn('Scripts\\python.exe', text)
        self.assertNotIn('& python manage.py', text)

    def test_dev_ps1_makemigrations_names_the_apps_explicitly(self):
        """makemigrations 必须带 app 名。

        这个仓库把 migrations/ 放进了 .gitignore，刚 clone 下来连 migrations
        目录都没有；不带 app 名的 makemigrations 会跳过这类 app，
        结果 forum 一张表都不建，起来一访问就是 no such table。
        """
        text = self.read_bytes('dev.ps1').decode('utf-8')

        self.assertIn('makemigrations forum md_editor', text)

    def test_dev_ps1_sets_debug(self):
        """不设 DEBUG=1，/static/ 下的编辑器资源会整片 404。"""
        text = self.read_bytes('dev.ps1').decode('utf-8')

        self.assertIn("$env:DEBUG = '1'", text)

    def test_dev_bat_hands_over_to_dev_ps1(self):
        text = self.read_bytes('dev.bat').decode('utf-8')

        self.assertIn('dev.ps1', text)
        # 双击运行时命令行参数要能透传
        self.assertIn('%*', text)
        # 用 Bypass，否则默认执行策略会直接拦下脚本
        self.assertIn('-ExecutionPolicy Bypass', text)
