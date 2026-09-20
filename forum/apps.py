from django.apps import AppConfig


class ForumConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'forum'

    def ready(self):
        # 注册「新建用户自动建 Profile」的信号
        from . import signals  # noqa: F401
