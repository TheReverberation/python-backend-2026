from collections import Counter
from dataclasses import dataclass

from hw2.hw.storage.models import ItemEntity, ItemInfo, ItemInfoPatch

from .helpers import yota
from .models import Cart, CartItem


class ItemStorage:
    def __init__(self):
        self._data = dict[int, ItemInfo]()
        self._id_generator = yota()

    def next_id(self):
        return next(self._id_generator)

    def add(self, item: ItemInfo) -> ItemEntity:
        id = self.next_id()
        self._data[id] = item
        return ItemEntity(id, item)

    def get_item(self, id: int) -> ItemEntity:
        self._require_item(id, check_deleted=True)
        return ItemEntity(id, self._data[id])

    def _require_item(self, id: int, check_deleted=False):
        if id not in self._data or (check_deleted and self._data[id].deleted):
            raise RuntimeError(f"Item {id} not found.")

    def get_items(
        self,
        offset: int = 0,
        limit: int = 10,
        min_price: float | None = None,
        max_price: float | None = None,
        show_deleted: bool = False,
    ) -> list[ItemEntity]:
        items = [ItemEntity(id, info) for id, info in self._data.items()]
        items = [
            item 
            for item in items 
            if (min_price is None or min_price <= item.info.price) \
            and (max_price is None or item.info.price <= max_price) \
            and (not item.info.deleted or show_deleted) \
            and (item.id >= offset)
        ]
        return items[:limit]

    def delete_item(self, id: int) -> ItemEntity:
        self._require_item(id)
        self._data[id].deleted = True
        return self.get_item(id)

    def put_item(self, id: int, item: ItemInfo) -> ItemEntity:
        self._require_item(id)
        self._data[id] = item 
        return self.get_item(id)

    def patch_item(self, id: int, patch: ItemInfoPatch) -> ItemEntity:
        self._require_item(id)
        patched, _ = ItemInfo.patch_checked(self._data[id], patch)
        self.put_item(id, patched)
        return self.get_item(id)


@dataclass
class CartItemRecord:
    id: int
    quantity: int 

    @staticmethod
    def from_counter(counter: Counter[int]) -> list[CartItemRecord]:
        return [CartItemRecord(id, cnt) for id, cnt in counter.items()]


@dataclass
class CartRecord:
    id: int 
    items: list[CartItemRecord]


class CartStorage:
    def __init__(self):
        self.carts = dict[int, Counter[int]]()
        self.id_generator = yota()

    def next_id(self):
        return next(self.id_generator)

    def add(self) -> int:
        id = self.next_id()
        self.carts[id] = Counter[int]()
        return id

    def get(self, id: int) -> CartRecord:
        self._require_cart(id)
        return CartRecord(id, CartItemRecord.from_counter(self.carts[id]))

    def get_cart_ids(self) -> list[int]:
        return list(self.carts.keys())

    def add_item(self, id: int, item_id: int) -> None:
        self._require_cart(id)
        self.carts[id][item_id] += 1

    def _require_cart(self, id: int):
        if id not in self.carts:
                    raise RuntimeError(f"Cart {id} not found")


class Storage:
    def __init__(self):
        self.item_storage = ItemStorage()
        self.cart_storage = CartStorage()

    def add_item(self, item: ItemInfo) -> ItemEntity:
        return self.item_storage.add(item)

    def get_item(self, id: int) -> ItemEntity | None:
        try:
            return self.item_storage.get_item(id)
        except RuntimeError:
            return None

    def get_items(self, *args, **kwargs) -> list[ItemEntity]:
        return self.item_storage.get_items(*args, **kwargs)

    def delete_item(self, id: int) -> ItemEntity | None:
        try:
            return self.item_storage.delete_item(id)
        except RuntimeError:
            return None

    def put_item(self, id: int, item: ItemInfo) -> ItemEntity | None:
        try:
            return self.item_storage.put_item(id, item)
        except RuntimeError:
            return None

    def patch_item(self, id: int, patch: ItemInfoPatch) -> ItemEntity | None:
        try:
            return self.item_storage.patch_item(id, patch)
        except RuntimeError:
            return None

    

    def add_cart(self) -> int:
        return self.cart_storage.add()

    def get_cart(self, id: int) -> Cart | None:
        try:
            cart_record = self.cart_storage.get(id)
            items = []
            price = 0.0
            for item_record in cart_record.items:
                item_info = self.item_storage.get_item(item_record.id).info
                items.append(CartItem(
                    id=item_record.id,
                    name=item_info.name,
                    quantity=item_record.quantity,
                    available=not item_info.deleted,
                ))
                if not item_info.deleted:
                    price += item_record.quantity * item_info.price
            return Cart(id, items, price)
        except RuntimeError:
            return None

    def add_item_to_cart(self, cart_id: id, item_id: id):
        self.cart_storage._require_cart(cart_id)
        self.item_storage._require_item(item_id)
        self.cart_storage.add_item(cart_id, item_id)

    def get_carts(
        self,
        offset: int = 0,
        limit: int = 10,
        min_price: float | None = None,
        max_price: float | None = None,
        min_quantity: int | None = None,
        max_quantity: int | None = None,
    ) -> list[Cart]:
        carts = [self.get_cart(id) for id in self.cart_storage.get_cart_ids()]
        carts = [
            cart 
            for cart in carts 
            if (min_price is None or min_price <= cart.price) \
            and (max_price is None or cart.price <= max_price) \
            and (min_quantity is None or min_quantity <= cart.quantity) \
            and (max_quantity is None or cart.quantity <= max_quantity) \
            and cart.id >= offset
        ]
        return carts[:limit]
        

    