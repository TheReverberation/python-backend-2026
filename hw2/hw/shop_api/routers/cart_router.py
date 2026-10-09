from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from hw2.hw.shop_api.contracts import CartListRequest, CartResponse
from hw2.hw.storage import storage

router = APIRouter(prefix="/cart")

@router.post("/", status_code=HTTPStatus.CREATED)
def post_cart(response: Response) -> CartResponse:
    id = storage.add_cart()
    response.headers["location"]  = f"/cart/{id}"
    return storage.get_cart(id)


@router.get("/{id}")
def get_cart(id: int) -> CartResponse:
    cart = storage.get_cart(id)
    if not cart:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /cart/{id} was not found",
        )
    return cart


@router.get("/")
def get_carts(params: Annotated[CartListRequest, Query()]) -> list[CartResponse]:
    return storage.get_carts(**params.model_dump())
    

@router.post("/{cart_id}/add/{item_id}")
def add_cart_item(cart_id: int, item_id: int, response: Response) -> CartResponse:
    if storage.get_cart(cart_id) is None or storage.get_item(item_id) is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /cart/{cart_id} or /item/{item_id} was not found",
        )
    storage.add_item_to_cart(cart_id, item_id)
    return storage.get_cart(cart_id)
