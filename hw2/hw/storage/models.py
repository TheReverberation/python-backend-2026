from dataclasses import dataclass
from typing import Self


@dataclass(slots=True)
class ItemInfoPatch:
    name: str | None = None
    price: float | None = None


@dataclass(slots=True)
class ItemInfo:
    name: str
    price: float
    deleted: bool = False

    @staticmethod
    def patch(item: ItemInfoPatch, info: ItemInfoPatch) -> Self:
        return ItemInfo(
            name=info.name or item.name,
            price=info.price or item.price,
            deleted=item.deleted,
        )

    @staticmethod
    def patch_checked(item: ItemInfoPatch, info: ItemInfoPatch) -> tuple[Self, bool]:
        patched = ItemInfo.patch(item, info)
        return patched, item != patched


@dataclass(slots=True)
class ItemEntity:
    id: int
    info: ItemInfo


@dataclass(slots=True)
class CartItem:
    id: int
    name: str
    quantity: int
    available: bool


@dataclass(slots=True)
class Cart:
    id: int
    items: list[CartItem]
    price: float

    @property
    def quantity(self) -> int:
        return sum(item.quantity for item in self.items)
