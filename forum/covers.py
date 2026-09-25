"""个人主页的背景图。

和头像（forum/avatars.py）是一套思路：真正解码一次 + 缩到合适尺寸后重新编码，
但约束完全不同 —— 背景是横幅，不是正方形小图：

- 尺寸上限放宽到 1920x640，头像那套 512 会把横幅压成一团
- 不做动图处理，横幅不需要动画
- 有透明通道的仍然存 PNG（和头像同一条规则），其余存 JPEG

没上传背景图时用按用户名生成的渐变兜底 —— 和默认字母头像同一个色板，
所以同一个人的头像底色和背景色是一套的。
"""

import logging
import uuid
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError

from .avatars import fallback_color

logger = logging.getLogger(__name__)

#: 上传原图大小上限
COVER_MAX_BYTES = 5 * 1024 * 1024

#: 缩放后最长边。宽度按桌面最宽的情况给足，高度够一条横幅就行
COVER_MAX_WIDTH = 1920
COVER_MAX_HEIGHT = 640

#: 渐变兜底里暗色的比例（越小越暗）
FALLBACK_SHADE = 0.45


def cover_upload_to(instance, filename):
    """背景图落盘路径：covers/u<user_id>/<uuid><ext>。"""
    suffix = Path(filename).suffix.lower()
    if suffix == '.jpeg':
        suffix = '.jpg'
    if suffix not in ('.jpg', '.png', '.webp', '.gif'):
        suffix = '.jpg'
    return f"covers/u{instance.user_id}/{uuid.uuid4().hex}{suffix}"


def normalize_cover(upload):
    """校验并归一化上传的背景图，返回可直接存盘的 ContentFile。"""
    if upload is None:
        return None

    if getattr(upload, 'size', 0) > COVER_MAX_BYTES:
        raise ValidationError(
            f'背景图不能超过 {COVER_MAX_BYTES // (1024 * 1024)} MB。'
        )

    try:
        upload.seek(0)
    except (AttributeError, OSError):
        pass

    try:
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError('无法识别的图片文件，请上传 JPG / PNG / WebP 格式的图片。')

    image = ImageOps.exif_transpose(image)

    has_alpha = image.mode in ('RGBA', 'LA') or (
        image.mode == 'P' and 'transparency' in image.info
    )
    if has_alpha:
        image = image.convert('RGBA')
        image_format, suffix = 'PNG', '.png'
    else:
        image = image.convert('RGB')
        image_format, suffix = 'JPEG', '.jpg'

    # thumbnail 只缩不放：小图不会被拉大糊掉
    image.thumbnail((COVER_MAX_WIDTH, COVER_MAX_HEIGHT), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    if image_format == 'JPEG':
        image.save(buffer, image_format, quality=85, optimize=True, progressive=True)
    else:
        image.save(buffer, image_format, optimize=True)

    return ContentFile(buffer.getvalue(), name=f'cover{suffix}')


def delete_cover_file(field_file):
    """删除背景图文件；接受 FieldFile，也接受文件名字符串。"""
    name = getattr(field_file, 'name', field_file)
    if not isinstance(name, str) or not name:
        return
    try:
        default_storage.delete(name)
    except OSError:
        # 文件已不在了不算错误，换背景图的流程不该因为磁盘状态失败
        pass


def cover_url(user):
    """取背景图 URL，没有则返回空串（前端回退到渐变）。"""
    if user is None:
        return ''

    profile = getattr(user, 'profile', None)
    if profile is None:
        return ''

    cover = getattr(profile, 'cover', None)
    if cover and getattr(cover, 'name', ''):
        try:
            return cover.url
        except ValueError:
            return ''
    return ''


def shade(color, factor=FALLBACK_SHADE):
    """把 #rrggbb 按比例调暗，用来做渐变的下半段。"""
    value = (color or '').lstrip('#')
    if len(value) != 6:
        return color
    try:
        channels = [int(value[index:index + 2], 16) for index in (0, 2, 4)]
    except ValueError:
        return color
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(c * factor))) for c in channels)


def fallback_cover(name):
    """没上传背景图时的渐变，按用户名稳定取色。"""
    base = fallback_color(name)
    return f'linear-gradient(135deg, {base} 0%, {shade(base)} 100%)'


def cover_background(user):
    """返回可直接塞进 style 的 CSS 值：有图用图，没图用渐变。"""
    name = ''
    if user is not None:
        name = user.get_username() if hasattr(user, 'get_username') else str(user)

    url = cover_url(user)
    if url:
        return f'url("{url}")'
    return fallback_cover(name)
