from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name



class SubCategory(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ['category', 'slug']
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.category.name} → {self.name}"



class Brand(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ('subcategory', 'slug')

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='products/')
    is_main = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.product.name}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['product'],
                condition=models.Q(is_main=True),
                name='unique_main_image_per_product'
            )
        ]


class ProductVariant(models.Model):
    UNIT_CHOICES = [
        ('kg', 'Kilogram'),
        ('g', 'Gram'),
        ('l', 'Liter'),
        ('ml', 'Milliliter'),
        ('pcs', 'Pieces'),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )

    name = models.CharField(max_length=100, help_text="Masalan: 1kg, 500g, 1L")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Masalan: 1, 0.5, 6"
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=50, unique=True)

    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0

    class Meta:
        unique_together = [('product', 'name'), ('product', 'sku')]


class Discount(models.Model):
    variant = models.OneToOneField(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='discount'
    )

    percent = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    is_active = models.BooleanField(default=True)


    @property
    def is_valid(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date

    def __str__(self):
        return f"{self.percent}% for {self.variant}"
