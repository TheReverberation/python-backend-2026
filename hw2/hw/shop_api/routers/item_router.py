from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeInt, PositiveFloat, PositiveInt

from hw2.hw.shop_api.contracts import (
    ItemPatchRequest,
    ItemRequest,
    ItemResponse,
)
from hw2.hw.storage import storage

router = APIRouter(prefix="/item")

@router.get("/")
async def get_items(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[PositiveFloat | None, Query()] = None,
    max_price: Annotated[PositiveFloat | None, Query()] = None,
    show_deleted: Annotated[bool | None, Query()] = False,
) -> list[ItemResponse]:
    return [ItemResponse.from_item(item) for item in storage.get_items(offset, limit, min_price, max_price, show_deleted)]


@router.get("/{id}")
async def get_item(id: int) -> ItemResponse:
    entity = storage.get_item(id)
    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{id} was not found",
        )
    
    return ItemResponse.from_item(entity)


@router.post(
    "/",
    status_code=HTTPStatus.CREATED,
)
async def post_item(item: ItemRequest, response: Response) -> ItemResponse:
    entity = storage.add_item(item.as_item_info())
    return ItemResponse.from_item(entity)


@router.delete(
    "/{id}",
    status_code=HTTPStatus.OK
)
async def delete_item(id: int) -> None:
    storage.delete_item(id)


@router.put("/{id}")
async def put_item(id: int, item: ItemRequest) -> ItemResponse:
    entity = storage.put_item(id, item.as_item_info())
    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{id} was not found",
        )
    return ItemResponse.from_item(entity)


@router.patch("/{id}")
async def patch_item(id: int, patch: ItemPatchRequest) -> ItemResponse:
    entity = storage.patch_item(id, patch.as_item_patch())
    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Request resource /item/{id} was not found",
        )
    return ItemResponse.from_item(entity)