import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, display_name, password=None, **extra_fields):
        if not email:
            raise ValueError("メールアドレスは必須です。")
        user = self.model(
            email=self.normalize_email(email).strip().lower(),
            display_name=display_name.strip(),
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, display_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("管理者は staff と superuser が必要です。")
        return self.create_user(email, display_name, password, **extra_fields)


class User(AbstractBaseUser):
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    password = models.CharField(max_length=255, db_column="password_hash")
    email = models.EmailField(max_length=254, unique=True)
    display_name = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        db_table = "users"
        ordering = ["display_name", "email"]

    def __str__(self):
        return self.display_name

    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser


class VehicleModel(models.Model):
    model_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    maker = models.CharField(max_length=80)
    model_name = models.CharField(max_length=100)
    model_year = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1950), MaxValueValidator(2100)]
    )
    engine_displacement_cc = models.PositiveIntegerField(null=True, blank=True)
    fuel_type = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "vehicle_models"
        ordering = ["maker", "model_name", "model_year"]
        indexes = [models.Index(fields=["maker", "model_name", "model_year"], name="ix_vehicle_model_name")]

    def __str__(self):
        year = f" ({self.model_year})" if self.model_year else ""
        return f"{self.maker} {self.model_name}{year}"


class Vehicle(models.Model):
    vehicle_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vehicles", db_column="owner_user_id")
    model = models.ForeignKey(VehicleModel, on_delete=models.PROTECT, related_name="vehicles", db_column="model_id")
    nickname = models.CharField(max_length=50, blank=True)
    registration_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    share_for_stats = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "vehicles"
        ordering = ["-is_active", "-created_at"]
        indexes = [models.Index(fields=["owner", "is_active"], name="ix_vehicle_owner_active")]

    def __str__(self):
        return self.nickname or str(self.model)


class CostRecord(models.Model):
    class Category(models.TextChoices):
        FUEL = "FUEL", "ガソリン"
        TAX = "TAX", "自動車税"
        INSURANCE = "INSURANCE", "保険"
        INSPECTION = "INSPECTION", "車検"
        MAINTENANCE = "MAINTENANCE", "整備・修理"
        PARKING = "PARKING", "駐車場"
        TOLL = "TOLL", "高速料金"
        OTHER = "OTHER", "その他"

    record_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="cost_records", db_column="vehicle_id")
    category = models.CharField(max_length=20, choices=Category.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    occurred_on = models.DateField()
    memo = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cost_records"
        ordering = ["-occurred_on", "-created_at"]
        indexes = [
            models.Index(fields=["vehicle", "occurred_on"], name="ix_cost_vehicle_date"),
            models.Index(fields=["category", "occurred_on"], name="ix_cost_category_date"),
        ]
        constraints = [
            models.CheckConstraint(check=Q(amount__gte=0), name="ck_cost_amount_nonnegative"),
            models.CheckConstraint(
                check=Q(category__in=["FUEL", "TAX", "INSURANCE", "INSPECTION", "MAINTENANCE", "PARKING", "TOLL", "OTHER"]),
                name="ck_cost_category_allowed",
            ),
        ]

    def __str__(self):
        return f"{self.get_category_display()} {self.amount}円 ({self.occurred_on})"


class Post(models.Model):
    post_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts", db_column="author_user_id")
    model_name = models.CharField(max_length=60)
    text = models.CharField(max_length=500)
    photo_url = models.CharField(max_length=500, blank=True)
    photo_note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        db_table = "posts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author.display_name}: {self.text[:40]}"


class Like(models.Model):
    like_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes", db_column="post_id")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="likes", db_column="user_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "likes"
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="uq_like_post_user")]
        indexes = [models.Index(fields=["user", "created_at"], name="ix_like_user_created")]

    def __str__(self):
        return f"{self.user} likes {self.post_id}"
