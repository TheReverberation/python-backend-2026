from concurrent.futures import ThreadPoolExecutor

from storage import storage
from storage.models import ItemInfo, ItemInfoPatch
from storage.storage import Storage


def test_persistence_and_zero_patch():
    item = storage.add_item(ItemInfo("persistent", 12))
    assert Storage().get_item(item.id) == item
    assert storage.patch_item(item.id, ItemInfoPatch(price=0)).info.price == 0


def test_deleted_item_stays_in_cart():
    item = storage.add_item(ItemInfo("deleted", 12))
    cart = storage.add_cart()
    storage.add_item_to_cart(cart, item.id)
    storage.delete_item(item.id)
    result = storage.get_cart(cart)
    assert result.price == 0
    assert result.items[0].available is False


def test_concurrent_quantity_increment():
    item = storage.add_item(ItemInfo("concurrent", 12))
    cart = storage.add_cart()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: storage.add_item_to_cart(cart, item.id), range(20)))
    assert storage.get_cart(cart).items[0].quantity == 20
