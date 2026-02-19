from django.db import transaction
from cart.models import Cart, CartItem
from catalog.models import ProductVariant


class CartService:
    @staticmethod
    def get_or_create_cart(user):
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart


    @staticmethod
    @transaction.atomic
    def add_to_cart(user, variant_id: int, quantity: int = 1):
        if quantity < 1:
            raise ValueError("quantity must be greater than 0")

        cart = CartService.get_or_create_cart(user)

        try:
            variant = (
                ProductVariant.objects
                .select_for_update()
                .get(id=variant_id, is_active=True)
            )
        except ProductVariant.DoesNotExist:
            raise ValueError("Variant not found or inactive.")

        item = (
            CartItem.objects
            .select_for_update()
            .filter(cart=cart, variant=variant)
            .first()
        )

        current_qty = item.quantity if item else 0
        new_qty = current_qty + quantity

        if variant.stock_quantity < new_qty:
            raise ValueError("Not enough stock.")

        if item:
            item.quantity = new_qty
            item.save(update_fields=["quantity"])
        else:
            item = CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)

        return item


    @staticmethod
    @transaction.atomic
    def remove_from_cart(user, variant_id: int):
        cart = CartService.get_or_create_cart(user)

        CartItem.objects.filter(
            cart=cart,
            variant_id=variant_id
        ).delete()


    @staticmethod
    @transaction.atomic
    def change_quantity(user, variant_id: int, quantity: int):
        cart = CartService.get_or_create_cart(user)

        if quantity < 1:
            CartItem.objects.filter(cart=cart, variant_id=variant_id).delete()
            return None

        try:
            variant = (
                ProductVariant.objects
                .select_for_update()
                .get(id=variant_id, is_active=True)
            )
        except ProductVariant.DoesNotExist:
            raise ValueError("Variant not found or inactive.")

        if variant.stock_quantity < quantity:
            raise ValueError("Not enough stock.")

        item = (
            CartItem.objects
            .select_for_update()
            .filter(cart=cart, variant_id=variant_id)
            .first()
        )

        if not item:
            raise ValueError("Item not found in cart.")

        item.quantity = quantity
        item.save(update_fields=["quantity"])
        return item


    @staticmethod
    @transaction.atomic
    def clear_cart(user):
        cart = CartService.get_or_create_cart(user)
        cart.items.all().delete()
