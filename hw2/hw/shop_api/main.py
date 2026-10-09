from fastapi import FastAPI

from hw2.hw.shop_api.routers import cart_router, item_router
from hw2.hw.storage import storage
from hw2.hw.storage.models import ItemInfo

app = FastAPI(title="Shop API")

app.include_router(item_router)
app.include_router(cart_router)

for i in range(5):
    storage.add_item(ItemInfo(name=f"name_{i}", price=i))

