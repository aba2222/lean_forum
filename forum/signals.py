"""注册用户自动建档：新建 User 时同时建好空的 Profile。

这样模板里可以直接用 user.profile，不必到处写兜底逻辑；
历史用户由 0002 数据迁移补齐。

另外在登录时顺手刷新一次 IP 归属地——个人主页上显示的就是这个值，
而它只能在我们看得到用户请求的时候才算得出来。
"""

import logging

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .geolocation import refresh_profile_region
from .models import Profile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User, dispatch_uid='forum.ensure_profile')
def ensure_profile(sender, instance, created, **kwargs):
    if not created:
        return
    Profile.objects.get_or_create(user=instance)


@receiver(user_logged_in, dispatch_uid='forum.refresh_region_on_login')
def refresh_region_on_login(sender, request, user, **kwargs):
    """登录时刷新归属地。

    包一层 try/except：归属地是锦上添花的东西，
    外部接口抽风绝不能把登录本身搞失败。
    """
    try:
        profile = Profile.objects.filter(user=user).first()
        if profile is not None:
            refresh_profile_region(profile, request)
    except Exception:
        logger.warning(
            '登录时刷新 IP 归属地失败 user=%s', getattr(user, 'pk', None), exc_info=True
        )
