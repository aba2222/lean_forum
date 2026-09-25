"""站内通知与 @提及。

把「提及怎么解析」「谁能被通知」集中在这里一份定义，
表单、视图、API 都调这里的函数，避免三处各写一个正则。
"""

import re

from django.contrib.auth.models import User

from .models import Notification

# @提及：用户名规则与注册时一致（字母/数字/下划线/中文，2~20 个字符）。
# 前面不能紧跟单词字符，否则邮箱 a@b.com 里的 @b 会被当成提及。
MENTION_RE = re.compile(r'(?<![\w\u4e00-\u9fff])@([\w\u4e00-\u9fff]{2,20})')


def extract_mentions(text):
    """从 Markdown 原文里取出被提及的用户名，去重且保持出现顺序。"""
    found = []
    for name in MENTION_RE.findall(text or ''):
        if name not in found:
            found.append(name)
    return found


def existing_usernames(names):
    """过滤出真实存在的用户名。

    渲染时只给这些名字加个人主页链接 —— 否则 @ 一个不存在的名字会链到 404。
    """
    if not names:
        return []
    rows = User.objects.filter(username__in=names).values_list('username', flat=True)
    return list(rows)


def notify(recipient, actor, kind, post=None, comment=None):
    """建一条通知。

    - 自己触发自己的不通知（自己评论自己的帖子、自己 @ 自己）
    - 重复触发不会产生第二条（靠唯一约束兜住）
    """
    if recipient is None or actor is None or recipient.pk == actor.pk:
        return None
    notification, _created = Notification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        kind=kind,
        post=post,
        comment=comment,
    )
    return notification


def notify_new_comment(comment):
    """有人评论了帖子 → 通知楼主。"""
    return notify(
        recipient=comment.post.author,
        actor=comment.author,
        kind=Notification.KIND_COMMENT,
        post=comment.post,
        comment=comment,
    )


def notify_mentions(content, actor, post=None, comment=None):
    """内容里 @ 到的人各通知一条；只通知真实存在的用户。"""
    names = extract_mentions(content)
    if not names:
        return []

    created = []
    for user in User.objects.filter(username__in=names):
        notification = notify(
            recipient=user,
            actor=actor,
            kind=Notification.KIND_MENTION,
            post=post,
            comment=comment,
        )
        if notification is not None:
            created.append(notification)
    return created
