"""打印应用接受的上传体积，以及反向代理该配多大。

存在的理由：nginx 的 `client_max_body_size` 默认只有 1 MB，而本站的头像上限是
2 MB（动图 6 MB）、编辑器音频上限是 25 MB。请求体超限时 nginx 会在请求到达
Django 之前就返回 413，页面上只会看到一张 nginx 的错误页 ——
应用侧完全不知道发生过什么，也就帮不上忙。

上限散在几个模块里，改了一个很容易忘了同步代理配置，所以这里从真正的常量
读出来，避免文档和代码各说各话。

用法：
    python manage.py upload_limits
"""

from django.core.management.base import BaseCommand


def _limits():
    """(说明, 字节数) 列表。放在函数里 import，避免命令注册时就拖起这些模块。"""
    from forum import avatars
    from md_editor import views as editor_views

    return [
        ('个人资料 · 头像（静态图）', avatars.AVATAR_MAX_BYTES),
        ('个人资料 · 头像（GIF/WebP 动图）', avatars.ANIMATED_AVATAR_MAX_BYTES),
        ('编辑器 · 帖子/评论图片', editor_views.MAX_IMAGE_BYTES),
        ('编辑器 · 帖子/评论音频', editor_views.MAX_AUDIO_BYTES),
    ]


#: 给多段表单的 boundary、文件名之类的开销留一点余量，别卡得刚好
PROXY_HEADROOM = 1.2


def _human(size):
    if size >= 1024 * 1024:
        return '%.0f MB' % (size / (1024 * 1024))
    if size >= 1024:
        return '%.0f KB' % (size / 1024)
    return '%d B' % size


class Command(BaseCommand):
    help = '打印各上传入口的体积上限，以及 nginx client_max_body_size 该配多少'

    def handle(self, *args, **options):
        limits = _limits()
        largest = max(size for _, size in limits)
        recommended = int(largest * PROXY_HEADROOM)

        width = max(len(name) for name, _ in limits)
        self.stdout.write('应用接受的上传上限：')
        for name, size in limits:
            self.stdout.write('  %-*s  %s' % (width, name, _human(size)))

        self.stdout.write('')
        self.stdout.write('反向代理必须放行到最大值以上，否则大文件会在到达 Django '
                          '之前就被 413 拒掉：')
        self.stdout.write('')
        self.stdout.write('  # nginx')
        self.stdout.write('  client_max_body_size %dm;' % (
            (recommended + 1024 * 1024 - 1) // (1024 * 1024)
        ))
        self.stdout.write('')
        self.stdout.write('放在 http{} 或对应的 server{}/location{} 里，然后 '
                          'nginx -s reload。')
