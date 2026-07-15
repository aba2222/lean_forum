from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils import timezone
from pathlib import Path
import uuid

allowed_types = [
    "image/jpeg",
    "image/png",
    "image/webp",
]

allowed_ext = [
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
]

@require_POST
def uplaod_view(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error":"login required"},
            status=401
        )

    image = request.FILES.get("image")
    if not image:
        return JsonResponse(
            {"error": "no image"},
            status=400
        )
    
    if image.content_type not in allowed_types:
        return JsonResponse(
            {"error": "invalid image"},
            status=400
        )
    
    if image.size > 10 * 1024 * 1024:
        return JsonResponse(
            {"error":"too large"},
            status=400
        )
    
    ext = Path(image.name).suffix
    if ext.lower() not in allowed_ext:
        return JsonResponse(
            {"error":"invalid extension"},
            status=400
        )
    
    now = timezone.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    filename = f"{uuid.uuid4()}{ext}"
    relative_path = f"{year}/{month}/{filename}"

    saved_path = default_storage.save(relative_path, image)

    url = settings.MEDIA_URL + saved_path

    return JsonResponse({
        "url": url
    })
