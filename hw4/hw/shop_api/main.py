from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from shop_api.routers import cart_router, item_router
from storage.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)

app.include_router(item_router)
app.include_router(cart_router)
