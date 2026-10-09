from __future__ import annotations

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, NonNegativeInt, PositiveInt

from hw2.hw.storage.models import CartItem, ItemEntity, ItemInfo, ItemInfoPatch


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False

    @staticmethod
    def from_item(item: ItemEntity) -> ItemResponse:
        return ItemResponse(
            id=item.id,
            name=item.info.name,
            price=item.info.price,
            deleted=item.info.deleted,
        )


class ItemRequest(BaseModel):
    name: str
    price: float
    deleted: bool = False

    def as_item_info(self):
        return ItemInfo(
            name=self.name,
            price=self.price,
            deleted=self.deleted,
        )


class ItemPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = None

    def as_item_patch(self):
        return ItemInfoPatch(name=self.name, price=self.price)


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItem]
    price: float


class CartListRequest(BaseModel):
    offset: NonNegativeInt | None = 0
    limit: PositiveInt | None = 10
    min_price: NonNegativeFloat | None = None
    max_price: NonNegativeFloat | None = None
    min_quantity: NonNegativeInt | None = None
    max_quantity: NonNegativeInt | None = None
