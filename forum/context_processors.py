"""模板全局上下文。"""

from .models import Notification


def notifications(request):
    """导航栏铃铛的未读数。

    未登录直接给 0，不产生查询；已登录才查一次 count()。
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'unread_notification_count': 0}
    return {
        'unread_notification_count': Notification.objects.filter(
            recipient=user, is_read=False
        ).count()
    }
