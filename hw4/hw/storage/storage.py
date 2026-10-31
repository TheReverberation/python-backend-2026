from dataclasses import asdict

from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert

from .database import CartItemRow, CartRow, ItemRow, SessionLocal
from .models import Cart, CartItem, ItemEntity, ItemInfo, ItemInfoPatch


def item_entity(row: ItemRow) -> ItemEntity:
    return ItemEntity(row.id, ItemInfo(row.name, float(row.price), row.deleted))


def cart_entity(session, cart_id: int) -> Cart:
    rows = session.execute(
        select(ItemRow, CartItemRow.quantity)
        .join(CartItemRow, CartItemRow.item_id == ItemRow.id)
        .where(CartItemRow.cart_id == cart_id)
        .order_by(ItemRow.id)
    ).all()
    return Cart(
        cart_id,
        [CartItem(item.id, item.name, quantity, not item.deleted) for item, quantity in rows],
        float(sum(item.price * quantity for item, quantity in rows if not item.deleted)),
    )


class Storage:
    def add_item(self, item: ItemInfo) -> ItemEntity:
        with SessionLocal.begin() as session:
            row = ItemRow(**asdict(item))
            session.add(row)
            session.flush()
            return item_entity(row)

    def get_item(self, id: int) -> ItemEntity | None:
        with SessionLocal() as session:
            row = session.get(ItemRow, id)
            return item_entity(row) if row is not None and not row.deleted else None

    def get_items(self, offset=0, limit=10, min_price=None, max_price=None, show_deleted=False):
        query = select(ItemRow)
        if not show_deleted:
            query = query.where(ItemRow.deleted.is_(False))
        if min_price is not None:
            query = query.where(ItemRow.price >= min_price)
        if max_price is not None:
            query = query.where(ItemRow.price <= max_price)
        with SessionLocal() as session:
            return [
                item_entity(row)
                for row in session.scalars(query.order_by(ItemRow.id).offset(offset).limit(limit))
            ]

    def _update_item(self, id: int, values: dict, active_only=True) -> ItemEntity | None:
        query = update(ItemRow).where(ItemRow.id == id)
        if active_only:
            query = query.where(ItemRow.deleted.is_(False))
        with SessionLocal.begin() as session:
            row = session.scalars(query.values(**values).returning(ItemRow)).one_or_none()
            return item_entity(row) if row is not None else None

    def delete_item(self, id: int) -> ItemEntity | None:
        return self._update_item(id, {"deleted": True}, active_only=False)

    def put_item(self, id: int, item: ItemInfo) -> ItemEntity | None:
        return self._update_item(id, asdict(item))

    def patch_item(self, id: int, patch: ItemInfoPatch) -> ItemEntity | None:
        values = {key: value for key, value in asdict(patch).items() if value is not None}
        return self._update_item(id, values) if values else self.get_item(id)

    def add_cart(self) -> int:
        with SessionLocal.begin() as session:
            row = CartRow()
            session.add(row)
            session.flush()
            return row.id

    def get_cart(self, id: int) -> Cart | None:
        with SessionLocal() as session:
            return cart_entity(session, id) if session.get(CartRow, id) is not None else None

    def add_item_to_cart(self, cart_id: int, item_id: int) -> None:
        with SessionLocal.begin() as session:
            query = insert(CartItemRow).values(cart_id=cart_id, item_id=item_id, quantity=1)
            session.execute(
                query.on_conflict_do_update(
                    index_elements=[CartItemRow.cart_id, CartItemRow.item_id],
                    set_={"quantity": CartItemRow.quantity + 1},
                )
            )

    def get_carts(
        self,
        offset=0,
        limit=10,
        min_price=None,
        max_price=None,
        min_quantity=None,
        max_quantity=None,
    ) -> list[Cart]:
        price = func.coalesce(
            func.sum(
                case((ItemRow.deleted.is_(False), ItemRow.price * CartItemRow.quantity), else_=0)
            ),
            0,
        )
        quantity = func.coalesce(func.sum(CartItemRow.quantity), 0)
        query = (
            select(CartRow.id)
            .outerjoin(CartItemRow, CartItemRow.cart_id == CartRow.id)
            .outerjoin(ItemRow, ItemRow.id == CartItemRow.item_id)
            .group_by(CartRow.id)
        )
        for expression, lower, upper in (
            (price, min_price, max_price),
            (quantity, min_quantity, max_quantity),
        ):
            if lower is not None:
                query = query.having(expression >= lower)
            if upper is not None:
                query = query.having(expression <= upper)
        with SessionLocal() as session:
            ids = session.scalars(query.order_by(CartRow.id).offset(offset).limit(limit)).all()
            return [cart_entity(session, id) for id in ids]
