"""论坛通用模板标签：头像渲染等。"""

from django import template

from forum.avatars import avatar_url, fallback_color, fallback_initial

register = template.Library()


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


@register.inclusion_tag('forum/_user_link.html')
def user_link(user, size=0, css_class=''):
    """渲染一个指向个人主页的昵称链接，并挂上悬停名片。

    用法：
        {% user_link post.author %}                      只显示昵称
        {% user_link post.author 24 %}                   头像 + 昵称
        {% user_link post.author 24 "text-decoration-none" %}

    名片数据放在 data-user-card 里（值是接口 URL），由
    static/forum/user-card.js 在第一次悬停时才去取。
    """
    username = ''
    if user is not None:
        if hasattr(user, 'get_username'):
            username = user.get_username()
        else:
            username = str(user)
    username = username.strip()

    try:
        size = int(size)
    except (TypeError, ValueError):
        size = 0

    return {
        'user': user,
        'username': username,
        'size': max(0, size),
        'css_class': css_class,
    }
