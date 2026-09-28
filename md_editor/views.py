from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils import timezone
from pathlib import Path
import uuid

#: 允许上传的图片类型 / 扩展名
IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

#: 允许上传的音频类型
#:
#: 同一份文件在不同浏览器/操作系统上给出的 content_type 并不一致
#: （wav 有 audio/wav、audio/x-wav、audio/wave；m4a 有 audio/mp4、
#: audio/x-m4a），所以这里把见过的都收进来，扩展名单独再校验一次。
AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/opus",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/vnd.wave",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    "audio/aac",
    "audio/flac",
    "audio/x-flac",
}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".ogg",
    ".oga",
    ".opus",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
}

#: 体积上限：音频比图片大得多，单独放宽
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024


def _classify(upload):
    """判断上传的是图片还是音频，认不出来的返回 None。"""
    content_type = (upload.content_type or "").lower()
    extension = Path(upload.name or "").suffix.lower()

    if content_type in IMAGE_TYPES and extension in IMAGE_EXTENSIONS:
        return "image"
    if content_type in AUDIO_TYPES and extension in AUDIO_EXTENSIONS:
        return "audio"
    return None


@require_POST
def upload_view(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error":"login required"},
            status=401
        )

    # 老客户端用 image 这个字段名传图片，音频走同一个接口
    upload = request.FILES.get("image") or request.FILES.get("file")
    if not upload:
        return JsonResponse(
            {"error": "no file"},
            status=400
        )

    kind = _classify(upload)
    if kind is None:
        return JsonResponse(
            {"error": "unsupported file type"},
            status=400
        )

    limit = MAX_IMAGE_BYTES if kind == "image" else MAX_AUDIO_BYTES
    if upload.size > limit:
        return JsonResponse(
            {"error": "too large", "limit": limit},
            status=400
        )

    ext = Path(upload.name).suffix
    now = timezone.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    filename = f"{uuid.uuid4()}{ext}"
    relative_path = f"{year}/{month}/{filename}"

    saved_path = default_storage.save(relative_path, upload)

    url = settings.MEDIA_URL + saved_path

    return JsonResponse({
        "url": url,
        "kind": kind,
    })
