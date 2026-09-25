"""论坛通用模板标签：头像渲染、@提及解析等。"""

from django import template

from forum.avatars import avatar_url, fallback_color, fallback_initial
from forum.notifications import existing_usernames, extract_mentions

register = template.Library()


@register.filter
def valid_mentions(content):
    """内容里真实存在的被 @ 用户名，逗号分隔，交给前端渲染器加个人主页链接。

    只给存在的用户加链接，否则 @ 一个不存在的名字会点到 404。
    先做一次纯文本判断，内容里没有 @ 就完全不查库。
    """
    text = content or ''
    if '@' not in text:
        return ''
    return ','.join(existing_usernames(extract_mentions(text)))


@register.inclusion_tag('forum/_avatar.html')
def avatar(user, size=32):
    """渲染用户头像。

    有上传头像就用图片，没有则回退成「用户名首字 + 稳定底色」的字母头像，
    两处渲染出来的尺寸与圆角完全一致，页面里可以直接当图标用。

    用法：{% avatar post.author 40 %}
    """
    name = ''
    url = ''

    if user is not None:
        if hasattr(user, 'get_username'):
            name = user.get_username()
            url = avatar_url(user)
        else:
            name = str(user)

    name = name.strip() or '匿名用户'
    try:
        size = max(16, min(256, int(size)))
    except (TypeError, ValueError):
        size = 32

    return {
        'avatar_url': url,
        'avatar_name': name,
        'size': size,
        # 字号按直径的 45% 取整，字母在不同尺寸下视觉重心一致
        'font_size': max(9, round(size * 0.45)),
        'color': fallback_color(name),
        'initial': fallback_initial(name),
    }
