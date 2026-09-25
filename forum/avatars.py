"""头像相关的纯函数工具：上传校验、压缩归一化、默认字母头像。

放在独立模块里，方便表单、模板标签和测试共用同一套规则；
所有函数都不碰数据库，便于单独测试。
"""

import zlib
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

#: 静态头像的上传原图大小上限
AVATAR_MAX_BYTES = 2 * 1024 * 1024

#: 动图的上传上限放宽：帧一多 2 MB 装不下几个像样的动图
ANIMATED_AVATAR_MAX_BYTES = 6 * 1024 * 1024

#: 归一化后最长边尺寸，头像不需要更大的图
AVATAR_MAX_EDGE = 512

#: 动图最多保留的帧数
#:
#: 单文件大小限制挡不住「很小但帧数极多」的动图——逐帧解码再逐帧重编码
#: 会同时吃掉内存和 CPU，所以帧数单独设一个上限。
ANIMATED_AVATAR_MAX_FRAMES = 150

#: 重新编码后的动图体积上限
ANIMATED_AVATAR_MAX_OUTPUT_BYTES = 2 * 1024 * 1024

#: 能原样保留动画的格式
#:
#: APNG 不在这里：Pillow 对 APNG 的多帧支持不完整，这类文件会退化成静态首帧。
ANIMATED_AVATAR_FORMATS = ('GIF', 'WEBP')

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


def is_animated_image(image):
    """是不是需要按动图处理。

    单帧的 GIF 也走静态分支——重编码成 PNG/JPEG 更小，也没有动画可保。
    """
    return bool(getattr(image, 'is_animated', False)) and getattr(image, 'n_frames', 1) > 1


def _gif_frame(image):
    """把一帧转成 GIF 的调色板模式，并保住透明。

    GIF 每帧最多 256 色，这里留出最后一个索引（255）专门当透明色：
    先按 RGB 量化出 255 色，再用 alpha 掩码把该透明的区域涂成索引 255。
    直接 convert('P') 会把透明像素当成不透明颜色一起量化掉，
    结果就是本该透明的地方变成一块实色。
    """
    rgba = image.convert('RGBA')
    alpha = rgba.split()[-1]
    frame = rgba.convert('RGB').convert(
        'P', palette=Image.Palette.ADAPTIVE, colors=255
    )
    transparent = Image.eval(alpha, lambda value: 255 if value <= 128 else 0)
    frame.paste(255, transparent)
    frame.info['transparency'] = 255
    return frame


def normalize_animated_avatar(image):
    """把多帧图逐帧缩放后重新编码，保留动画。

    返回 ContentFile；格式不在 ANIMATED_AVATAR_FORMATS 里时返回 None，
    由调用方退回静态首帧。
    """
    image_format = (image.format or '').upper()
    if image_format not in ANIMATED_AVATAR_FORMATS:
        return None

    frames = []
    durations = []
    for frame in ImageSequence.Iterator(image):
        if len(frames) >= ANIMATED_AVATAR_MAX_FRAMES:
            raise ValidationError(
                f'动图最多支持 {ANIMATED_AVATAR_MAX_FRAMES} 帧，'
                '请先减少帧数或压缩后再上传。'
            )
        # 帧自己的 duration 优先；缺失时退回整图的，再不行按 100ms
        duration = frame.info.get('duration') or image.info.get('duration') or 100
        durations.append(int(duration))
        canvas = frame.convert('RGBA')
        canvas.thumbnail((AVATAR_MAX_EDGE, AVATAR_MAX_EDGE), Image.Resampling.LANCZOS)
        frames.append(canvas)

    if len(frames) < 2:
        return None

    if image_format == 'GIF':
        frames = [_gif_frame(frame) for frame in frames]

    save_kwargs = {
        'save_all': True,
        'append_images': frames[1:],
        'duration': durations,
        'loop': image.info.get('loop', 0),
    }
    if image_format == 'GIF':
        # 每帧绘制前先清回背景色，帧间透明区域才不会互相残留
        save_kwargs['disposal'] = 2
    else:
        save_kwargs['quality'] = 80
        save_kwargs['method'] = 4

    buffer = BytesIO()
    frames[0].save(buffer, image_format, **save_kwargs)
    payload = buffer.getvalue()

    if len(payload) > ANIMATED_AVATAR_MAX_OUTPUT_BYTES:
        raise ValidationError(
            f'动图压缩后仍然超过 {ANIMATED_AVATAR_MAX_OUTPUT_BYTES // (1024 * 1024)} MB，'
            '请缩短时长或减少帧数后再上传。'
        )

    return ContentFile(payload, name=f'avatar.{image_format.lower()}')


def normalize_avatar(upload):
    """校验并归一化上传的头像，返回可直接存盘的 ContentFile。

    - 限制原图大小（动图放宽到 ANIMATED_AVATAR_MAX_BYTES）；
    - 用 Pillow 真正解码一次，非图片文件直接拒绝；
    - 按 EXIF 方向摆正、等比缩到 AVATAR_MAX_EDGE 以内；
    - 有透明通道的存 PNG，其余存 JPEG（质量 88 + 渐进式），避免动辄几 MB 的头像；
    - GIF / WebP 多帧图逐帧缩放后重新编码，动画保留。
    """
    if upload is None:
        return None

    size = getattr(upload, 'size', 0)
    if size > ANIMATED_AVATAR_MAX_BYTES:
        raise ValidationError(
            f'头像文件不能超过 {ANIMATED_AVATAR_MAX_BYTES // (1024 * 1024)} MB。'
        )

    try:
        upload.seek(0)
    except (AttributeError, OSError):
        pass

    try:
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError(
            '无法识别的图片文件，请上传 JPG / PNG / WebP / GIF 格式的图片。'
        )

    if is_animated_image(image):
        animated = normalize_animated_avatar(image)
        if animated is not None:
            return animated
        # 读不出多帧（格式不支持）就退回静态首帧，没必要把用户的头像整个拒掉
        image.seek(0)

    if size > AVATAR_MAX_BYTES:
        raise ValidationError(
            f'头像文件不能超过 {AVATAR_MAX_BYTES // (1024 * 1024)} MB。'
        )

    # EXIF 摆正只对静态图做：exif_transpose 会返回单帧副本，用在动图上会吃掉动画
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
