"""建立或重建站内搜索的 FTS5 全文索引。

不跑这个命令也能用：第一次搜索时会自动建索引，建不起来就退回 LIKE（慢一些）。
它的价值是**把建索引挪到部署流程里** —— 不用等第一个用户搜索时才建，
也不会在某个业务事务里顺手建表。

用法：
    python manage.py build_search_index            # 没有就建，有就跳过
    python manage.py build_search_index --rebuild  # 先删干净再重建（改过索引列之后用）
"""

from django.core.management.base import BaseCommand

from forum import search


class Command(BaseCommand):
    help = '建立或重建站内搜索的 FTS5 全文索引'

    def add_arguments(self, parser):
        parser.add_argument(
            '--rebuild',
            action='store_true',
            help='先删掉旧索引再重建，保证内容和源表一致',
        )

    def handle(self, *args, **options):
        ok = search.rebuild_index() if options['rebuild'] else search.ensure_index()

        if ok:
            action = '重建完成' if options['rebuild'] else '已就绪'
            self.stdout.write(self.style.SUCCESS('站内搜索索引%s' % action))
            return

        self.stderr.write(self.style.WARNING(
            '未能建立索引（数据库不是 SQLite，或当前在事务中执行）；'
            '搜索会自动回退到 LIKE，结果仍然正确。'
        ))
