"""注册用户自动建档：新建 User 时同时建好空的 Profile。

这样模板里可以直接用 user.profile，不必到处写兜底逻辑；
历史用户由 0002 数据迁移补齐。
"""

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=User, dispatch_uid='forum.ensure_profile')
def ensure_profile(sender, instance, created, **kwargs):
    if not created:
        return
    Profile.objects.get_or_create(user=instance)
