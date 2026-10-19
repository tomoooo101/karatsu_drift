import json
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import CostRecord, Like, Post, User, Vehicle, VehicleModel


def api_error(message, status=400, **extra):
    return JsonResponse({"error": message, **extra}, status=status)


def request_data(request):
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        return request.POST
    try:
        return json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def api_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return api_error("ログインしてください。", 401)
        return view(request, *args, **kwargs)

    return wrapped


def current_user(user):
    return {
        "id": str(user.pk),
        "email": user.email,
        "name": user.display_name,
        "photoUrl": default_storage.url(user.photo_path) if user.photo_path else "",
    }


def vehicle_data(vehicle):
    model = vehicle.model
    return {
        "id": str(vehicle.pk),
        "make": model.maker,
        "model": model.model_name,
        "year": model.model_year or "",
        "nickname": vehicle.nickname,
        "photoUrl": default_storage.url(vehicle.photo_path) if vehicle.photo_path else "",
        "shareForStats": vehicle.share_for_stats,
        "active": vehicle.is_active,
    }


def cost_data(record):
    return {
        "id": str(record.pk),
        "carId": str(record.vehicle_id),
        "category": record.get_category_display(),
        "categoryCode": record.category,
        "amount": int(record.amount),
        "date": record.occurred_on.isoformat(),
        "memo": record.memo,
    }


def post_data(post, liked_ids):
    return {
        "id": str(post.pk),
        "author": post.author.display_name,
        "authorId": str(post.author_id),
        "authorPhotoUrl": default_storage.url(post.author.photo_path) if post.author.photo_path else "",
        "model": post.model_name,
        "text": post.text,
        "photo": post.photo_note,
        "photoUrl": post.photo_url if post.photo_url.startswith("/media/") else "",
        "likes": post.like_count,
        "liked": str(post.pk) in liked_ids,
        "createdAt": post.created_at.isoformat(),
    }


@ensure_csrf_cookie
def home(request):
    index_path = settings.BASE_DIR.parent / "frontend" / "index.html"
    try:
        return FileResponse(index_path.open("rb"), content_type="text/html; charset=utf-8")
    except FileNotFoundError:
        return api_error("フロント画面が見つかりません。", 404)


@require_GET
def session_status(request):
    if request.user.is_authenticated:
        return JsonResponse({"authenticated": True, "user": current_user(request.user)})
    return JsonResponse({"authenticated": False})


@require_POST
def register(request):
    data = request_data(request)
    if not isinstance(data, dict):
        return api_error("入力内容を読み取れませんでした。")
    email = str(data.get("email", "")).strip().lower()
    name = str(data.get("name", "")).strip()
    password = str(data.get("password", ""))
    if not email:
        return api_error("メールアドレスを入力してください。")
    try:
        validate_email(email)
    except ValidationError:
        return api_error("有効なメールアドレスを入力してください。")
    if len(email) > 254:
        return api_error("メールアドレスは254文字以内で入力してください。")
    if not name or len(name) > 30:
        return api_error("表示名は1〜30文字で入力してください。")
    if password != str(data.get("passwordConfirm", "")):
        return api_error("確認用パスワードが一致しません。")
    if len(password) < 8:
        return api_error("パスワードは8文字以上にしてください。")
    try:
        validate_password(password)
    except ValidationError as exc:
        return api_error(" ".join(exc.messages))
    try:
        user = User.objects.create_user(email=email, display_name=name, password=password)
    except IntegrityError:
        return api_error("このメールアドレスはすでに登録されています。", 409)
    login(request, user)
    return JsonResponse({"authenticated": True, "user": current_user(user)}, status=201)


@require_POST
def login_view(request):
    data = request_data(request)
    if not isinstance(data, dict):
        return api_error("入力内容を読み取れませんでした。")
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = authenticate(request, email=email, password=password)
    if user is None:
        return api_error("メールアドレスまたはパスワードが違います。", 401)
    login(request, user)
    return JsonResponse({"authenticated": True, "user": current_user(user)})


@require_POST
@api_login_required
def logout_view(request):
    logout(request)
    return JsonResponse({"authenticated": False})


@require_GET
@api_login_required
def bootstrap(request):
    vehicles = list(
        Vehicle.objects.filter(owner=request.user, is_active=True)
        .select_related("model")
        .order_by("-created_at")
    )
    costs = list(
        CostRecord.objects.filter(vehicle__owner=request.user)
        .select_related("vehicle", "vehicle__model")[:1000]
    )
    posts = list(
        Post.objects.filter(is_public=True)
        .select_related("author")
        .annotate(like_count=Count("likes"))[:200]
    )
    liked_ids = set(
        str(value)
        for value in Like.objects.filter(user=request.user, post__in=posts).values_list("post_id", flat=True)
    )
    return JsonResponse(
        {
            "user": current_user(request.user),
            "vehicles": [vehicle_data(vehicle) for vehicle in vehicles],
            "costs": [cost_data(cost) for cost in costs],
            "posts": [post_data(post, liked_ids) for post in posts],
            "categories": [{"code": code, "label": label} for code, label in CostRecord.Category.choices],
        }
    )


@require_GET
@api_login_required
def post_feed(request):
    posts = list(
        Post.objects.filter(is_public=True)
        .select_related("author")
        .annotate(like_count=Count("likes"))[:200]
    )
    liked_ids = {
        str(value)
        for value in Like.objects.filter(user=request.user, post__in=posts).values_list("post_id", flat=True)
    }
    response = JsonResponse({"posts": [post_data(post, liked_ids) for post in posts]})
    response["Cache-Control"] = "no-store"
    return response


@require_POST
@api_login_required
def profile(request):
    data = request_data(request)
    if not isinstance(data, dict):
        return api_error("入力内容を読み取れませんでした。")
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    if not name or len(name) > 30:
        return api_error("表示名は1〜30文字で入力してください。")
    if email:
        try:
            validate_email(email)
        except ValidationError:
            return api_error("メールアドレスの形式を確認してください。")
    if email and User.objects.exclude(pk=request.user.pk).filter(email__iexact=email).exists():
        return api_error("このメールアドレスはすでに使われています。", 409)
    request.user.display_name = name
    if email:
        request.user.email = email
    request.user.save(update_fields=["display_name", "email", "updated_at"])
    return JsonResponse({"user": current_user(request.user)})


@require_POST
@api_login_required
def profile_photo(request):
    user = request.user
    upload = request.FILES.get("photoFile")
    if not upload and request.POST.get("reset") == "true":
        delete_user_avatar_file(user)
        user.photo_path = ""
        user.save(update_fields=["photo_path", "updated_at"])
        return JsonResponse({"photoUrl": ""})
    if not upload:
        return api_error("プロフィール写真を選択してください。")
    error = validate_image(upload)
    if error:
        return api_error(error)
    suffix = Path(upload.name).suffix.lower()
    relative_path = default_storage.save(f"profiles/{user.pk}/{uuid4().hex}{suffix}", upload)
    old_path = user.photo_path
    user.photo_path = relative_path
    user.save(update_fields=["photo_path", "updated_at"])
    if old_path:
        default_storage.delete(old_path)
    return JsonResponse({"photoUrl": default_storage.url(relative_path)})


@require_POST
@api_login_required
def account_delete(request):
    data = request_data(request)
    if not isinstance(data, dict) or not request.user.check_password(str(data.get("password", ""))):
        return api_error("パスワードを確認してください。", 403)
    user = request.user
    delete_user_photo_files(user)
    delete_user_avatar_file(user)
    delete_vehicle_photo_files(user)
    logout(request)
    user.delete()
    return JsonResponse({"deleted": True})


@require_POST
@api_login_required
def vehicle_create(request):
    data = request_data(request)
    if not isinstance(data, dict):
        return api_error("入力内容を読み取れませんでした。")
    maker = str(data.get("make", "")).strip()
    model_name = str(data.get("model", "")).strip()
    nickname = str(data.get("nickname", "")).strip()
    year_text = str(data.get("year", "")).strip()
    if not maker or len(maker) > 80 or not model_name or len(model_name) > 100:
        return api_error("メーカー名と車種名を入力してください。")
    if len(nickname) > 50:
        return api_error("車両名は50文字以内で入力してください。")
    year = None
    if year_text:
        if not year_text.isdigit() or not 1950 <= int(year_text) <= timezone.localdate().year + 1:
            return api_error("年式は1950年から来年までで入力してください。")
        year = int(year_text)
    model, _ = VehicleModel.objects.get_or_create(maker=maker, model_name=model_name, model_year=year)
    vehicle = Vehicle.objects.create(
        owner=request.user,
        model=model,
        nickname=nickname,
        share_for_stats=data.get("shareForStats") is True,
    )
    return JsonResponse({"vehicle": vehicle_data(vehicle)}, status=201)


@require_POST
@api_login_required
def vehicle_delete(request, vehicle_id):
    vehicle = Vehicle.objects.filter(owner=request.user, pk=vehicle_id).first()
    if not vehicle:
        return api_error("車両が見つかりません。", 404)
    if vehicle.cost_records.exists():
        return api_error("維持費記録がある車両は削除できません。先に記録を削除してください。", 409)
    delete_vehicle_photo_file(vehicle)
    vehicle.delete()
    return JsonResponse({"deleted": True})


@require_POST
@api_login_required
def vehicle_photo(request, vehicle_id):
    vehicle = Vehicle.objects.filter(owner=request.user, pk=vehicle_id).first()
    if not vehicle:
        return api_error("車両が見つかりません。", 404)
    upload = request.FILES.get("photoFile")
    if not upload and request.POST.get("reset") == "true":
        delete_vehicle_photo_file(vehicle)
        vehicle.photo_path = ""
        vehicle.save(update_fields=["photo_path", "updated_at"])
        return JsonResponse({"photoUrl": ""})
    if not upload:
        return api_error("画像ファイルを選択してください。")
    error = validate_image(upload)
    if error:
        return api_error(error)
    suffix = Path(upload.name).suffix.lower()
    relative_path = default_storage.save(
        f"vehicles/{vehicle.owner_id}/{vehicle.vehicle_id}/{uuid4().hex}{suffix}", upload
    )
    old_path = vehicle.photo_path
    vehicle.photo_path = relative_path
    vehicle.save(update_fields=["photo_path", "updated_at"])
    if old_path:
        default_storage.delete(old_path)
    return JsonResponse({"photoUrl": default_storage.url(relative_path)})


@require_POST
@api_login_required
def vehicle_share(request, vehicle_id):
    vehicle = Vehicle.objects.filter(owner=request.user, pk=vehicle_id).first()
    if not vehicle:
        return api_error("車両が見つかりません。", 404)
    data = request_data(request)
    if not isinstance(data, dict) or not isinstance(data.get("shareForStats"), bool):
        return api_error("共有設定を指定してください。")
    vehicle.share_for_stats = data["shareForStats"]
    vehicle.save(update_fields=["share_for_stats", "updated_at"])
    return JsonResponse({"shareForStats": vehicle.share_for_stats})


def parse_cost(data):
    try:
        amount = Decimal(str(data.get("amount", "")))
        occurred_on = date.fromisoformat(str(data.get("date", "")))
    except (InvalidOperation, ValueError, TypeError):
        return None, "金額と日付を正しく入力してください。"
    category = str(data.get("category", ""))
    allowed = dict(CostRecord.Category.choices)
    if category not in allowed:
        return None, "費目を選択してください。"
    if amount < 1 or amount != amount.to_integral_value() or amount > Decimal("9999999999"):
        return None, "金額は1円以上の整数で入力してください。"
    memo = str(data.get("memo", "")).strip()
    if len(memo) > 500:
        return None, "メモは500文字以内で入力してください。"
    return {"amount": amount, "occurred_on": occurred_on, "category": category, "memo": memo}, None


@require_POST
@api_login_required
def cost_create(request):
    data = request_data(request)
    if not isinstance(data, dict):
        return api_error("入力内容を読み取れませんでした。")
    fields, error = parse_cost(data)
    if error:
        return api_error(error)
    vehicle = Vehicle.objects.filter(owner=request.user, pk=data.get("carId"), is_active=True).first()
    if not vehicle:
        return api_error("登録済みの車両を選択してください。")
    record = CostRecord.objects.create(vehicle=vehicle, **fields)
    return JsonResponse({"cost": cost_data(record)}, status=201)


@require_POST
@api_login_required
def cost_update(request, record_id):
    record = CostRecord.objects.filter(vehicle__owner=request.user, pk=record_id).select_related("vehicle", "vehicle__model").first()
    if not record:
        return api_error("維持費記録が見つかりません。", 404)
    data = request_data(request)
    if not isinstance(data, dict):
        return api_error("入力内容を読み取れませんでした。")
    fields, error = parse_cost(data)
    if error:
        return api_error(error)
    vehicle = Vehicle.objects.filter(owner=request.user, pk=data.get("carId"), is_active=True).first()
    if not vehicle:
        return api_error("登録済みの車両を選択してください。")
    for key, value in fields.items():
        setattr(record, key, value)
    record.vehicle = vehicle
    record.save(update_fields=["vehicle", "amount", "occurred_on", "category", "memo"])
    return JsonResponse({"cost": cost_data(record)})


@require_POST
@api_login_required
def cost_delete(request, record_id):
    deleted, _ = CostRecord.objects.filter(vehicle__owner=request.user, pk=record_id).delete()
    if not deleted:
        return api_error("維持費記録が見つかりません。", 404)
    return JsonResponse({"deleted": True})


@require_GET
@api_login_required
def car_search(request):
    term = request.GET.get("q", "").strip()
    records = CostRecord.objects.filter(
        vehicle__share_for_stats=True,
        vehicle__is_active=True,
    ).select_related("vehicle__model")
    if term:
        from django.db.models import Q

        records = records.filter(Q(vehicle__model__maker__icontains=term) | Q(vehicle__model__model_name__icontains=term))
    grouped = {}
    for record in records.iterator():
        model = record.vehicle.model
        key = (model.maker, model.model_name, model.model_year)
        item = grouped.setdefault(key, {"count": 0, "total": 0, "months": set()})
        item["count"] += 1
        item["total"] += record.amount
        item["months"].add(record.occurred_on.strftime("%Y-%m"))
    results = []
    for (maker, model_name, year), item in sorted(grouped.items()):
        months = len(item["months"])
        results.append({
            "make": maker,
            "model": model_name,
            "year": year or "",
            "count": item["count"],
            "total": int(item["total"]),
            "avg": round(item["total"] / months) if months else 0,
            "months": months,
        })
    return JsonResponse({"results": results})


def validate_image(upload):
    if upload.size > 5 * 1024 * 1024:
        return "画像は5MB以下にしてください。"
    if Path(upload.name).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        return "JPEG、PNG、WebP形式の画像を選択してください。"
    try:
        from PIL import Image

        image = Image.open(upload)
        image.verify()
        upload.seek(0)
    except Exception:
        return "画像ファイルを読み取れませんでした。"
    return None


@require_POST
@api_login_required
def post_create(request):
    data = request_data(request)
    if data is None:
        return api_error("入力内容を読み取れませんでした。")
    model_name = str(data.get("model", "")).strip()
    text = str(data.get("text", "")).strip()
    photo_note = str(data.get("photo", "")).strip()
    if not model_name or len(model_name) > 60:
        return api_error("車種は1〜60文字で入力してください。")
    if not text or len(text) > 500:
        return api_error("投稿内容は1〜500文字で入力してください。")
    if len(photo_note) > 200:
        return api_error("写真メモは200文字以内で入力してください。")
    upload = request.FILES.get("photoFile")
    photo_url = ""
    if upload:
        error = validate_image(upload)
        if error:
            return api_error(error)
        ext = Path(upload.name).suffix.lower()
        relative_path = default_storage.save(f"posts/{timezone.now():%Y/%m}/{uuid4().hex}{ext}", upload)
        photo_url = default_storage.url(relative_path)
    post = Post.objects.create(
        author=request.user,
        model_name=model_name,
        text=text,
        photo_note=photo_note,
        photo_url=photo_url,
    )
    post.like_count = 0
    return JsonResponse({"post": post_data(post, set())}, status=201)


@require_POST
@api_login_required
def post_delete(request, post_id):
    post = Post.objects.filter(pk=post_id, author=request.user).first()
    if post:
        delete_post_photo_file(post)
    deleted, _ = Post.objects.filter(pk=post_id, author=request.user).delete()
    if not deleted:
        return api_error("自分の投稿が見つかりません。", 404)
    return JsonResponse({"deleted": True})


def delete_post_photo_file(post):
    if post.photo_url.startswith(settings.MEDIA_URL):
        default_storage.delete(post.photo_url[len(settings.MEDIA_URL):])


def delete_user_photo_files(user):
    for post in Post.objects.filter(author=user).only("photo_url"):
        delete_post_photo_file(post)


def delete_user_avatar_file(user):
    if user.photo_path:
        default_storage.delete(user.photo_path)


def delete_vehicle_photo_file(vehicle):
    if vehicle.photo_path:
        default_storage.delete(vehicle.photo_path)


def delete_vehicle_photo_files(user):
    for vehicle in Vehicle.objects.filter(owner=user).only("photo_path"):
        delete_vehicle_photo_file(vehicle)


@require_POST
@api_login_required
def like_toggle(request, post_id):
    post = Post.objects.filter(pk=post_id, is_public=True).first()
    if not post:
        return api_error("投稿が見つかりません。", 404)
    created = False
    with transaction.atomic():
        _, created = Like.objects.get_or_create(post=post, user=request.user)
    count = post.likes.count()
    return JsonResponse({"liked": True, "likes": count, "created": created})


@require_POST
@api_login_required
def unlike(request, post_id):
    deleted, _ = Like.objects.filter(post_id=post_id, user=request.user).delete()
    post = Post.objects.filter(pk=post_id, is_public=True).first()
    if not post:
        return api_error("投稿が見つかりません。", 404)
    return JsonResponse({"liked": False, "likes": post.likes.count(), "removed": bool(deleted)})
