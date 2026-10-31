from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from shop_api.routers import cart_router, item_router
from storage import storage
from storage.models import ItemInfo

app = FastAPI(title="Shop API")
Instrumentator().instrument(app).expose(app)

app.include_router(item_router)
app.include_router(cart_router)

for i in range(5):
    storage.add_item(ItemInfo(name=f"name_{i}", price=i))
