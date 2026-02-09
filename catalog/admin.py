from django.contrib import admin
from .models import (
    Category,
    SubCategory,
    Brand,
    Product,
    ProductVariant,
    ProductImage,
    Discount
)

admin.site.register(Category)
admin.site.register(SubCategory)
admin.site.register(Brand)
admin.site.register(Product)
admin.site.register(ProductVariant)
admin.site.register(ProductImage)
admin.site.register(Discount)

