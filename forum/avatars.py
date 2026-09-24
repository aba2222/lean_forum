"""头像相关的纯函数工具：上传校验、压缩归一化、默认字母头像。

放在独立模块里，方便表单、模板标签和测试共用同一套规则；
所有函数都不碰数据库，便于单独测试。
"""

import zlib
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError

#: 上传原图大小上限
AVATAR_MAX_BYTES = 2 * 1024 * 1024

#: 归一化后最长边尺寸，头像不需要更大的图
AVATAR_MAX_EDGE = 512

#: 未设置头像时，按用户名散列取的底色（均配白字，对比度足够）
FALLBACK_COLORS = (
    '#1D4ED8',  # 蓝
    '#6D28D9',  # 紫
    '#BE123C',  # 玫红
    '#9A3412',  # 赭石
    '#15803D',  # 绿
    '#115E59',  # 墨绿
    '#0E7490',  # 青
    '#7E22CE',  # 紫罗兰
)


def fallback_color(name):
    """按用户名稳定取一个底色——同一个人每次渲染颜色一致。"""
    key = (name or '').encode('utf-8')
    return FALLBACK_COLORS[zlib.crc32(key) % len(FALLBACK_COLORS)]


def fallback_initial(name):
    """默认头像显示的首字。"""
    for char in (name or '').strip():
        return char.upper()
    return '?'


def normalize_avatar(upload):
    """校验并归一化上传的头像，返回可直接存盘的 ContentFile。

    - 限制原图大小；
    - 用 Pillow 真正解码一次，非图片文件直接拒绝；
    - 按 EXIF 方向摆正、等比缩到 AVATAR_MAX_EDGE 以内；
    - 有透明通道的存 PNG，其余存 JPEG（质量 88 + 渐进式），避免动辄几 MB 的头像。
    """
    if upload is None:
        return None

    if getattr(upload, 'size', 0) > AVATAR_MAX_BYTES:
        raise ValidationError(
            f'头像文件不能超过 {AVATAR_MAX_BYTES // (1024 * 1024)} MB。'
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

    image.thumbnail((AVATAR_MAX_EDGE, AVATAR_MAX_EDGE), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    if image_format == 'JPEG':
        image.save(buffer, image_format, quality=88, optimize=True, progressive=True)
    else:
        image.save(buffer, image_format, optimize=True)

    return ContentFile(buffer.getvalue(), name=f'avatar{suffix}')


def delete_avatar_file(field_file):
    """删除头像文件；接受 FieldFile，也接受文件名字符串。"""
    name = getattr(field_file, 'name', field_file)
    if not isinstance(name, str) or not name:
        return
    try:
        default_storage.delete(name)
    except OSError:
        # 文件已不在了不算错误，换头像流程不该因为磁盘状态失败
        pass


def avatar_url(user):
    """取用户头像 URL，没有头像时返回空串（前端回退到字母头像）。"""
    if user is None:
        return ''

    profile = getattr(user, 'profile', None)
    if profile is None:
        return ''

    avatar = getattr(profile, 'avatar', None)
    if avatar and getattr(avatar, 'name', ''):
        try:
            return avatar.url
        except ValueError:
            return ''
    return ''
