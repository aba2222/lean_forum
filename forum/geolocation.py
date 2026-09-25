"""把访问者的 IP 换成归属地。

个人主页上显示的是「浙江 杭州」这一级，**不保存也不展示完整 IP** ——
归属地只是用来替换原来那个需要用户自己手填的「所在地」。

查询是懒的：同一个 IP 且刚查过就不重复查；同一个用户换网络了才会再查一次。
查不到就留空，个人主页上那一行不显示，不会因为外部接口挂了而报错。
"""

import ipaddress
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

#: 内网 / 回环地址的说法，不往外查
PRIVATE_REGION = '本地网络'

#: 查不到时的返回值（空串表示「这一行不显示」）
UNKNOWN_REGION = ''

#: 同一个 IP 多久之内不重复查
REGION_REFRESH_INTERVAL = timedelta(hours=12)

#: 不同接口对同一件事的叫法不一样，按常见程度依次尝试
REGION_KEYS = ('regionName', 'region', 'pro', 'province', 'state', 'region_name')
CITY_KEYS = ('city', 'cityName', 'city_name')
COUNTRY_KEYS = ('country_name', 'countryName', 'country')

#: 归属地字段长度上限，和 Profile.region 保持一致
REGION_MAX_LENGTH = 60


def client_ip(request):
    """取真实客户端 IP，取不到返回空串。

    `X-Forwarded-For` 是**客户端可以自己伪造**的头，所以靠左的值不可信。
    真正可信的只有紧挨着我们的那一跳写进去的那一项，也就是从右往左数
    第 `FORUM_TRUSTED_PROXY_COUNT + 1` 个（0 层反代时就是 REMOTE_ADDR）。
    """
    if request is None:
        return ''

    forwarded = request.META.get('X-Forwarded-For', '') or ''
    chain = [part.strip() for part in forwarded.split(',') if part.strip()]
    chain.append((request.META.get('REMOTE_ADDR') or '').strip())

    try:
        trusted = max(0, int(getattr(settings, 'FORUM_TRUSTED_PROXY_COUNT', 0)))
    except (TypeError, ValueError):
        trusted = 0

    index = len(chain) - 1 - trusted
    if index < 0:
        index = 0
    candidate = chain[index] if chain else ''

    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return ''
    return candidate


def is_private_ip(ip):
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def _first(payload, keys):
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def format_region(payload):
    """从各家接口的返回里拼出「省 市」，拼不出就退到国家名。"""
    if not isinstance(payload, dict):
        return ''

    # 有的接口把结果包在 data / result 里
    for wrapper in ('data', 'result'):
        inner = payload.get(wrapper)
        if isinstance(inner, dict):
            payload = inner
            break

    region = _first(payload, REGION_KEYS)
    city = _first(payload, CITY_KEYS)
    country = _first(payload, COUNTRY_KEYS)

    parts = []
    for value in (region, city):
        if value and value != country and value not in parts:
            parts.append(value)

    text = ' '.join(parts) if parts else country
    return text[:REGION_MAX_LENGTH]


def resolve_region(ip):
    """IP → 归属地。查不到返回空串，任何异常都咽掉。

    这是渲染链路上的调用，绝不能因为外部接口超时/改版把页面带崩。
    """
    if not ip:
        return UNKNOWN_REGION

    if is_private_ip(ip):
        return PRIVATE_REGION

    template = (getattr(settings, 'FORUM_GEOIP_API', '') or '').strip()
    if not template:
        return UNKNOWN_REGION

    if '{ip}' not in template:
        logger.warning('FORUM_GEOIP_API 里没有 {ip} 占位符，跳过归属地查询')
        return UNKNOWN_REGION

    try:
        import requests

        response = requests.get(
            template.replace('{ip}', ip),
            timeout=float(getattr(settings, 'FORUM_GEOIP_TIMEOUT', 2)),
            headers={'User-Agent': 'lean_forum/1.0 (+ip-region)'},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.warning('归属地查询失败 ip=%s', ip, exc_info=True)
        return UNKNOWN_REGION

    return format_region(payload)


def refresh_profile_region(profile, request, force=False):
    """按当前请求的 IP 更新 profile.region，需要写库时返回 True。

    - IP 没变、且距上次查询不到 REGION_REFRESH_INTERVAL → 什么都不做
    - 查询失败时**保留原来的归属地**，只更新 last_ip / 查询时间
    """
    if profile is None:
        return False

    ip = client_ip(request)
    if not ip:
        return False

    now = timezone.now()
    unchanged = profile.last_ip == ip
    fresh = (
        profile.region_checked_at is not None
        and now - profile.region_checked_at < REGION_REFRESH_INTERVAL
    )
    if not force and unchanged and fresh:
        return False

    region = resolve_region(ip)

    profile.last_ip = ip
    profile.region_checked_at = now
    update_fields = ['last_ip', 'region_checked_at']
    if region:
        profile.region = region
        update_fields.append('region')
    profile.save(update_fields=update_fields)
    return True
