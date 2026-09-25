"""防重复提交：一次渲染出来的表单只允许成功提交一次。

浏览器刷新、双击提交按钮、网络重试、代理重放都会把同一个 POST 再发一遍。
创建类视图原来的写法是「表单有效就 insert」，多发一次就多一行完全相同的
记录——帖子列表里就会出现两条一模一样的帖子/评论。

做法是一次性令牌：渲染表单时塞一个随机值，提交成功后记进 session；
再拿同一个令牌来就当作重复提交，直接当成功处理（照常跳转），不再落库。
"""

import secrets

from datetime import timedelta

from django.utils import timezone

#: session 里记录已用过的令牌
SESSION_KEY = 'forum_used_submit_tokens'

#: 只记最近这么多个，避免 session 无限增长
#:
#: 记太多没有意义：令牌只在「页面还开着、用户可能再按一次提交」的时间窗内
#: 有用，记 20 个足够覆盖来回切换几个标签页的情况。
MAX_REMEMBERED_TOKENS = 20

#: 表单里的字段名
FORM_FIELD_NAME = 'submit_token'

#: 重复提交时给用户看的提示
DUPLICATE_MESSAGE = '这次提交已经处理过了，没有重复发布。'

#: 内容去重的时间窗（秒），给没有 session 可用的调用方（DRF API）用
DUPLICATE_WINDOW_SECONDS = 60


def new_submit_token():
    """给一份刚渲染出来的表单发一个新令牌。"""
    return secrets.token_urlsafe(16)


def claim_submit_token(session, token):
    """认领令牌。第一次见到返回 True，重复的返回 False。

    没有令牌（老页面、第三方客户端、测试里的直连 POST）一律放行：
    这层防护是为了挡住浏览器的重复提交，不该把没有令牌的调用方挡在外面。
    """
    if not token:
        return True

    used = list(session.get(SESSION_KEY, []))
    if token in used:
        return False

    used.append(token)
    session[SESSION_KEY] = used[-MAX_REMEMBERED_TOKENS:]
    return True


def recent_duplicate(model, author, **lookup):
    """同一作者在 DUPLICATE_WINDOW_SECONDS 内提交过的完全相同的内容。

    API 走不了 session 令牌，用这个兜底；返回已有的那一条，没有则返回 None。
    """
    if author is None or not getattr(author, 'is_authenticated', False):
        return None

    criteria = {}
    for key, value in lookup.items():
        criteria[key] = value.strip() if isinstance(value, str) else value

    # 文本条件全为空时不认为「内容相同」——否则空内容会把所有请求都算成重复
    if not any(
        value for value in criteria.values() if isinstance(value, str)
    ):
        return None

    since = timezone.now() - timedelta(seconds=DUPLICATE_WINDOW_SECONDS)
    return (
        model.objects.filter(author=author, created_at__gte=since, **criteria)
        .order_by('-created_at')
        .first()
    )
