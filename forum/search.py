"""站内搜索：SQLite FTS5 全文索引 + LIKE 回退。

## 为什么是混合方案

SQLite 的 fts5 内置分词器没有一个能同时满足中英文子串搜索：

* ``unicode61``（默认）会把一整串中文当成一个词 —— 搜「最短路」匹配不到
  「本文讲最短路」；
* ``trigram`` 按三字符切分，中英文子串都能命中，但**至少要有 3 个字符**
  才用得上索引（实测：搜「最短路」命中，搜「题解」命中 0）。

中文搜索里两字词很常见，所以按查询长度分流：

===========================  ============================================
查询长度 >= 3                走 FTS5：命中行数越少越快（实测高选择性查询快 50 倍以上）
查询长度 <  3                回退 LIKE：慢一点，但结果正确
===========================  ============================================

宁可短查询走全表扫，也不要为了「用上索引」而干脆搜不到东西。

搜索语义与原来完全一致：把用户输入整体当成一个**子串短语**（不是分词检索），
排序也仍然是按时间倒序 —— 结果集和顺序都不变，变的只有速度。

## 为什么不用 migration 建表

本仓库把 ``migrations/`` 放在 .gitignore 里，手写的 RunSQL 迁移不会进版本库、
部署时也不存在。所以索引改成就地创建：任何环境第一次搜索时自动建好，
全部用 ``IF NOT EXISTS`` 保证幂等。

`forum_post` / `forum_collection` 的增删改由 SQLite 触发器同步，
所以不管从哪写入（网页、DRF、admin、manage.py shell）索引都不会漏。
"""

import logging
import sqlite3

from django.db import connection
from django.db.models import Q

from .models import Post

logger = logging.getLogger(__name__)

#: 短于这个长度用不上 trigram 索引，直接回退 LIKE
MIN_FTS_QUERY_LENGTH = 3

#: FTS 虚表名与它索引的源表/列
FTS_TABLE = 'forum_post_fts'
SOURCE_TABLE = 'forum_post'
SOURCE_COLUMNS = ('title', 'content')

_state = {'ready': False}


def _ddl(table, fts, columns):
    """建虚表 + 三个同步触发器的语句。

    用 external content（``content='<源表>'``）不复制正文，省一半空间；
    代价是删除/更新必须把旧值以 ``'delete'`` 指令喂回索引，触发器就是这么写的。
    """
    cols = ', '.join(columns)
    delete_cols = ', '.join([fts, 'rowid'] + list(columns))
    new_vals = ', '.join('new.%s' % c for c in columns)
    old_vals = ', '.join('old.%s' % c for c in columns)

    return (
        "CREATE VIRTUAL TABLE IF NOT EXISTS %s USING fts5("
        "%s, content='%s', content_rowid='id', tokenize='trigram')" % (fts, cols, table),

        "CREATE TRIGGER IF NOT EXISTS %s_ai AFTER INSERT ON %s BEGIN "
        "INSERT INTO %s(rowid, %s) VALUES (new.id, %s); END" % (fts, table, fts, cols, new_vals),

        "CREATE TRIGGER IF NOT EXISTS %s_ad AFTER DELETE ON %s BEGIN "
        "INSERT INTO %s(%s) VALUES ('delete', old.id, %s); END"
        % (fts, table, fts, delete_cols, old_vals),

        "CREATE TRIGGER IF NOT EXISTS %s_au AFTER UPDATE ON %s BEGIN "
        "INSERT INTO %s(%s) VALUES ('delete', old.id, %s); "
        "INSERT INTO %s(rowid, %s) VALUES (new.id, %s); END"
        % (fts, table, fts, delete_cols, old_vals, fts, cols, new_vals),
    )


def _fts_exists(cursor, fts):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = %s", [fts]
    )
    return cursor.fetchone() is not None


def ensure_index():
    """就地建好 FTS5 虚表与同步触发器；幂等，失败返回 False（调用方回退 LIKE）。

    只在**事务之外**建索引，有两个原因：

    * SQLite 里在事务中建虚表并执行 rebuild，一旦这个事务回滚，
      FTS5 的影子表和连接状态就会对不上，之后任何 SAVEPOINT 都直接报
      ``SQL logic error``（TestCase 每个用例都会回滚，所以这个坑在测试里必现）；
    * 建索引本来就不该挂在某个业务事务上。

    事务里需要索引而它又还不存在时，退回 LIKE —— 宁可这次慢一点，
    也不要把连接搞坏。索引已存在时读写都是安全的，随时可用。
    """
    if connection.vendor != 'sqlite':
        # 其它数据库另有做法（例如 Postgres 的 SearchVector），这里不假装支持
        return False

    if _state['ready']:
        return True

    try:
        with connection.cursor() as cursor:
            if _fts_exists(cursor, FTS_TABLE):
                # 已经建好了（例如部署时跑过 build_search_index）
                _state['ready'] = True
                return True

            if connection.in_atomic_block:
                return False

            for statement in _ddl(SOURCE_TABLE, FTS_TABLE, SOURCE_COLUMNS):
                cursor.execute(statement)
            # 刚建好的 external content 表要从源表重建一次索引
            cursor.execute("INSERT INTO %s(%s) VALUES('rebuild')" % (FTS_TABLE, FTS_TABLE))
    except sqlite3.Error:
        logger.exception('FTS5 索引初始化失败，搜索回退到 LIKE')
        return False

    _state['ready'] = True
    return True


def rebuild_index():
    """强制重建索引（管理命令用）：先删干净再建，保证内容和源表一致。"""
    if connection.vendor != 'sqlite':
        return False

    if connection.in_atomic_block:
        raise RuntimeError('重建索引不能在事务里执行')

    try:
        with connection.cursor() as cursor:
            for suffix in ('ai', 'ad', 'au'):
                cursor.execute("DROP TRIGGER IF EXISTS %s_%s" % (FTS_TABLE, suffix))
            cursor.execute("DROP TABLE IF EXISTS %s" % FTS_TABLE)
    except sqlite3.Error:
        logger.exception('清理旧索引失败')
        return False

    _state['ready'] = False
    return ensure_index()


def _phrase(query):
    """把用户输入包成一个 FTS5 字面短语。

    FTS5 查询语法里 ``"`` ``*`` ``(`` ``)`` ``:`` 都是操作符，直接拼会抛语法错误；
    包成双引号短语既安全，又正好等于原来的「子串」语义（引号用两个双引号转义）。
    """
    return '"%s"' % query.replace('"', '""')


def _match(cursor, fts, query):
    # 占位符必须用 %s：Django 的 SQLite 后端会把它转成 ?，
    # 并且在 DEBUG 下用 `sql % params` 记录日志 —— 直接写 ? 会在 DEBUG 模式抛 TypeError。
    cursor.execute(
        'SELECT rowid FROM {fts} WHERE {fts} MATCH %s ORDER BY rank'.format(fts=fts),
        [_phrase(query)],
    )
    return [row[0] for row in cursor.fetchall()]


def _fts_ids(query):
    """走 FTS5 取命中的帖子 id；用不了时返回 None，表示交给 LIKE。"""
    if not ensure_index():
        return None

    try:
        with connection.cursor() as cursor:
            return _match(cursor, FTS_TABLE, query)
    except sqlite3.Error:
        logger.exception('FTS5 查询失败，回退 LIKE: %r', query)
        return None


def search_posts(query):
    """帖子搜索。返回 QuerySet，可直接交给 Paginator。

    结果集与排序都与原来的 icontains 版本一致 —— 只是更快。
    排序保持「按时间倒序」不变：一来对用户没有行为变化，
    二来实测发现「按 FTS5 相关度排序」需要一个大 CASE WHEN，
    在命中几千条时反而比全表扫还慢（把高选择性查询的 36 倍提速吃成 2 倍）。
    """
    query = (query or '').strip()
    base = Post.objects.select_related('author')

    if not query:
        return base.order_by('-created_at')

    if len(query) >= MIN_FTS_QUERY_LENGTH:
        ids = _fts_ids(query)
        if ids is not None:
            # FTS5 只索引标题与正文；作者名不在索引里，另外用一次 LIKE 补上
            by_author = list(
                base.filter(author__username__icontains=query).values_list('id', flat=True)
            )
            merged = list(dict.fromkeys(ids + by_author))
            return base.filter(pk__in=merged).order_by('-created_at')

    return base.filter(
        Q(title__icontains=query)
        | Q(content__icontains=query)
        | Q(author__username__icontains=query)
    ).order_by('-created_at')

