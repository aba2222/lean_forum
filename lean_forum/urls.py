"""
URL configuration for lean_forum project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import re

from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings
from django.views.static import serve
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    re_path(r'^webpush/', include('webpush.urls')),
    path('', include('forum.urls')),
    path('', include('md_editor.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

# 上传文件与静态文件：显式挂在 URLconf 上，不只依赖 DEBUG。
# 只靠 if settings.DEBUG: static(...) 的话，一旦 DEBUG 是关闭的，
# /media/ 下的头像、帖子图片就会全部 404。
# 注意：DEBUG 打开时 runserver 的 staticfiles handler 会先于 URLconf 接管 /static/，
# 从各 app 的 static/ 目录直接取文件（无需 collectstatic），这里的规则是兜底。
if settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(
            r'^%s(?P<path>.*)$' % re.escape(settings.MEDIA_URL.lstrip('/')),
            serve,
            {'document_root': settings.MEDIA_ROOT},
        ),
    ]

if settings.SERVE_STATIC:
    urlpatterns += [
        re_path(
            r'^%s(?P<path>.*)$' % re.escape(settings.STATIC_URL.lstrip('/')),
            serve,
            {'document_root': settings.STATIC_ROOT},
        ),
    ]

