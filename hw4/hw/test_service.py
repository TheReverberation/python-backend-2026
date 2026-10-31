from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from faker import Faker
from fastapi.testclient import TestClient
from shop_api.main import app
from sqlalchemy.exc import IntegrityError
from storage import storage
from storage.models import ItemInfo, ItemInfoPatch
from storage.storage import Storage

client = TestClient(app)
faker = Faker()


@pytest.fixture()
def existing_empty_cart_id() -> int:
    return client.post("/cart").json()["id"]


@pytest.fixture(scope="session")
def existing_items(database) -> list[int]:
    items = [
        {
            "name": f"Тестовый товар {i}",
            "price": faker.pyfloat(positive=True, min_value=10.0, max_value=500.0),
        }
        for i in range(10)
    ]

    return [client.post("/item", json=item).json()["id"] for item in items]


@pytest.fixture(scope="session", autouse=True)
def existing_not_empty_carts(existing_items: list[int]) -> list[int]:
    carts = []

    for i in range(20):
        cart_id: int = client.post("/cart").json()["id"]
        for item_id in faker.random_elements(existing_items, unique=False, length=i):
            client.post(f"/cart/{cart_id}/add/{item_id}")

        carts.append(cart_id)

    return carts


@pytest.fixture()
def existing_not_empty_cart_id(
    existing_empty_cart_id: int,
    existing_items: list[int],
) -> int:
    for item_id in faker.random_elements(existing_items, unique=False, length=3):
        client.post(f"/cart/{existing_empty_cart_id}/add/{item_id}")

    return existing_empty_cart_id


@pytest.fixture()
def existing_item() -> dict[str, Any]:
    return client.post(
        "/item",
        json={
            "name": f"Тестовый товар {uuid4().hex}",
            "price": faker.pyfloat(min_value=10.0, max_value=100.0),
        },
    ).json()


@pytest.fixture()
def deleted_item(existing_item: dict[str, Any]) -> dict[str, Any]:
    item_id = existing_item["id"]
    client.delete(f"/item/{item_id}")

    existing_item["deleted"] = True
    return existing_item


def test_post_cart() -> None:
    response = client.post("/cart")

    assert response.status_code == HTTPStatus.CREATED
    assert "location" in response.headers
    assert "id" in response.json()


@pytest.mark.parametrize(
    ("cart", "not_empty"),
    [
        ("existing_empty_cart_id", False),
        ("existing_not_empty_cart_id", True),
    ],
)
def test_get_cart(request, cart: int, not_empty: bool) -> None:
    cart_id = request.getfixturevalue(cart)

    response = client.get(f"/cart/{cart_id}")

    assert response.status_code == HTTPStatus.OK
    response_json = response.json()

    len_items = len(response_json["items"])
    assert len_items > 0 if not_empty else len_items == 0

    if not_empty:
        price = 0

        for item in response_json["items"]:
            item_id = item["id"]
            price += client.get(f"/item/{item_id}").json()["price"] * item["quantity"]

        assert response_json["price"] == pytest.approx(price, 1e-8)
    else:
        assert response_json["price"] == 0.0


@pytest.mark.parametrize(
    ("query", "status_code"),
    [
        ({}, HTTPStatus.OK),
        ({"offset": 1, "limit": 2}, HTTPStatus.OK),
        ({"min_price": 1000.0}, HTTPStatus.OK),
        ({"max_price": 20.0}, HTTPStatus.OK),
        ({"min_quantity": 1}, HTTPStatus.OK),
        ({"max_quantity": 0}, HTTPStatus.OK),
        ({"offset": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"limit": 0}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"limit": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"min_price": -1.0}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"max_price": -1.0}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"min_quantity": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"max_quantity": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
    ],
)
def test_get_cart_list(query: dict[str, Any], status_code: int):
    response = client.get("/cart", params=query)

    assert response.status_code == status_code

    if status_code == HTTPStatus.OK:
        data = response.json()

        assert isinstance(data, list)

        if "min_price" in query:
            assert all(item["price"] >= query["min_price"] for item in data)

        if "max_price" in query:
            assert all(item["price"] <= query["max_price"] for item in data)

        for cart in data:
            quantity = sum(item["quantity"] for item in cart["items"])
            if "min_quantity" in query:
                assert quantity >= query["min_quantity"]
            if "max_quantity" in query:
                assert quantity <= query["max_quantity"]


def test_post_item() -> None:
    item = {"name": "test item", "price": 9.99}
    response = client.post("/item", json=item)

    assert response.status_code == HTTPStatus.CREATED

    data = response.json()
    assert item["price"] == data["price"]
    assert item["name"] == data["name"]


def test_get_item(existing_item: dict[str, Any]) -> None:
    item_id = existing_item["id"]

    response = client.get(f"/item/{item_id}")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == existing_item


@pytest.mark.parametrize(
    ("query", "status_code"),
    [
        ({"offset": 2, "limit": 5}, HTTPStatus.OK),
        ({"min_price": 5.0}, HTTPStatus.OK),
        ({"max_price": 5.0}, HTTPStatus.OK),
        ({"show_deleted": True}, HTTPStatus.OK),
        ({"offset": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"limit": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"limit": 0}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"min_price": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"max_price": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
    ],
)
def test_get_item_list(query: dict[str, Any], status_code: int) -> None:
    response = client.get("/item", params=query)

    assert response.status_code == status_code

    if status_code == HTTPStatus.OK:
        data = response.json()

        assert isinstance(data, list)

        if "min_price" in query:
            assert all(item["price"] >= query["min_price"] for item in data)

        if "max_price" in query:
            assert all(item["price"] <= query["max_price"] for item in data)

        if "show_deleted" in query and query["show_deleted"] is False:
            assert all(item["deleted"] is False for item in data)


@pytest.mark.parametrize(
    ("body", "status_code"),
    [
        ({}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"price": 9.99}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"name": "new name", "price": 9.99}, HTTPStatus.OK),
    ],
)
def test_put_item(
    existing_item: dict[str, Any],
    body: dict[str, Any],
    status_code: int,
) -> None:
    item_id = existing_item["id"]
    response = client.put(f"/item/{item_id}", json=body)

    assert response.status_code == status_code

    if status_code == HTTPStatus.OK:
        new_item = existing_item.copy()
        new_item.update(body)
        assert response.json() == new_item


@pytest.mark.parametrize(
    ("item", "body", "status_code"),
    [
        ("deleted_item", {}, HTTPStatus.NOT_MODIFIED),
        ("deleted_item", {"price": 9.99}, HTTPStatus.NOT_MODIFIED),
        ("deleted_item", {"name": "new name", "price": 9.99}, HTTPStatus.NOT_MODIFIED),
        ("existing_item", {}, HTTPStatus.OK),
        ("existing_item", {"price": 9.99}, HTTPStatus.OK),
        ("existing_item", {"name": "new name", "price": 9.99}, HTTPStatus.OK),
        (
            "existing_item",
            {"name": "new name", "price": 9.99, "odd": "value"},
            HTTPStatus.UNPROCESSABLE_ENTITY,
        ),
        (
            "existing_item",
            {"name": "new name", "price": 9.99, "deleted": True},
            HTTPStatus.UNPROCESSABLE_ENTITY,
        ),
    ],
)
def test_patch_item(request, item: str, body: dict[str, Any], status_code: int) -> None:
    item_data: dict[str, Any] = request.getfixturevalue(item)
    item_id = item_data["id"]
    response = client.patch(f"/item/{item_id}", json=body)

    assert response.status_code == status_code

    if status_code == HTTPStatus.OK:
        patch_response_body = response.json()

        response = client.get(f"/item/{item_id}")
        patched_item = response.json()

        assert patched_item == patch_response_body


def test_delete_item(existing_item: dict[str, Any]) -> None:
    item_id = existing_item["id"]

    response = client.delete(f"/item/{item_id}")
    assert response.status_code == HTTPStatus.OK

    response = client.get(f"/item/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND

    response = client.delete(f"/item/{item_id}")
    assert response.status_code == HTTPStatus.OK


def create_item(client, name="milk", price=10):
    response = client.post("/item", json={"name": name, "price": price})
    assert response.status_code == 201
    return response.json()


def create_cart(client):
    response = client.post("/cart")
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize(
    ("method", "path", "body", "status"),
    [
        ("GET", "/item/999", None, 404),
        ("GET", "/cart/999", None, 404),
        ("PUT", "/item/999", {"name": "missing", "price": 10}, 404),
        ("PATCH", "/item/999", {"price": 10}, 304),
        ("POST", "/cart/999/add/999", None, 404),
    ],
)
def test_missing_resources(isolated_client, method, path, body, status):
    response = isolated_client.request(method, path, json=body)
    assert response.status_code == status
    assert isolated_client.get("/item").json() == []
    assert isolated_client.get("/cart").json() == []


@pytest.mark.parametrize("deleted", [False, True])
def test_cannot_add_unavailable_item(isolated_client, deleted):
    cart_id = create_cart(isolated_client)
    item_id = 999
    if deleted:
        item_id = create_item(isolated_client)["id"]
        assert isolated_client.delete(f"/item/{item_id}").status_code == 200
    response = isolated_client.post(f"/cart/{cart_id}/add/{item_id}")
    assert response.status_code == 404
    assert isolated_client.get(f"/cart/{cart_id}").json() == {
        "id": cart_id,
        "items": [],
        "price": 0,
    }


def test_deleted_item_is_excluded_from_cart_total(isolated_client):
    first = create_item(isolated_client, "first", 30)
    second = create_item(isolated_client, "second", 40)
    cart_id = create_cart(isolated_client)
    for item in (first, first, second):
        assert isolated_client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 200
    assert isolated_client.delete(f"/item/{first['id']}").status_code == 200
    assert isolated_client.get("/item").json() == [second]
    assert isolated_client.get("/item", params={"show_deleted": True}).json() == [
        {**first, "deleted": True},
        second,
    ]
    assert isolated_client.get(f"/cart/{cart_id}").json() == {
        "id": cart_id,
        "items": [
            {"id": first["id"], "name": "first", "quantity": 2, "available": False},
            {"id": second["id"], "name": "second", "quantity": 1, "available": True},
        ],
        "price": 40,
    }
    carts = isolated_client.get("/cart", params={"max_price": 40, "min_quantity": 3}).json()
    assert [cart["id"] for cart in carts] == [cart_id]


def test_repeated_add_increments_quantity(isolated_client):
    item = create_item(isolated_client, price=7)
    cart_id = create_cart(isolated_client)
    for _ in range(2):
        response = isolated_client.post(f"/cart/{cart_id}/add/{item['id']}")
        assert response.status_code == 200
    assert response.json()["items"] == [
        {"id": item["id"], "name": "milk", "quantity": 2, "available": True},
    ]
    assert response.json()["price"] == 14


def test_created_item_returns_price_stored_by_postgres(isolated_client):
    item = create_item(isolated_client, price=61.864840240353)
    assert item["price"] == 61.86484024
    assert isolated_client.get(f"/item/{item['id']}").json() == item


@pytest.mark.parametrize(
    ("query", "indices"),
    [
        ({"min_price": 10, "max_price": 20}, [1, 2]),
        ({"min_price": 10, "max_price": 20, "offset": 1, "limit": 1}, [2]),
        ({"offset": 10}, []),
        ({"min_price": 20, "max_price": 10}, []),
    ],
)
def test_item_filter_boundaries_and_pagination(isolated_client, query, indices):
    items = [create_item(isolated_client, price=price) for price in (5, 10, 20, 30)]
    response = isolated_client.get("/item", params=query)
    assert response.status_code == 200
    assert response.json() == [items[i] for i in indices]


@pytest.mark.parametrize(
    ("query", "indices"),
    [
        ({"max_price": 0}, [0]),
        ({"max_quantity": 0}, [0]),
        ({"min_price": 10, "max_price": 20}, [1, 2]),
        ({"min_quantity": 1, "max_quantity": 2}, [1, 2]),
        ({"min_price": 10, "max_quantity": 2, "offset": 1, "limit": 1}, [2]),
        ({"offset": 10}, []),
        ({"min_quantity": 3, "max_quantity": 1}, []),
    ],
)
def test_cart_filter_boundaries_and_pagination(isolated_client, query, indices):
    item = create_item(isolated_client, price=10)
    carts = []
    for quantity in range(4):
        cart_id = create_cart(isolated_client)
        for _ in range(quantity):
            assert isolated_client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 200
        carts.append(isolated_client.get(f"/cart/{cart_id}").json())
    response = isolated_client.get("/cart", params=query)
    assert response.status_code == 200
    assert response.json() == [carts[i] for i in indices]


@pytest.mark.parametrize("body", [{}, {"price": 0}, {"name": "renamed"}])
def test_patch_preserves_other_fields(isolated_client, body):
    item = create_item(isolated_client)
    response = isolated_client.patch(f"/item/{item['id']}", json=body)
    assert response.status_code == 200
    assert response.json() == {**item, **body}
    assert isolated_client.get(f"/item/{item['id']}").json() == response.json()


@pytest.mark.parametrize("body", [{"deleted": True}, {"unexpected": 1}])
def test_invalid_patch_does_not_change_item(isolated_client, body):
    item = create_item(isolated_client)
    response = isolated_client.patch(f"/item/{item['id']}", json={"price": 99, **body})
    assert response.status_code == 422
    assert isolated_client.get(f"/item/{item['id']}").json() == item


def test_put_deleted_item_does_not_restore_it(isolated_client):
    item = create_item(isolated_client)
    assert isolated_client.delete(f"/item/{item['id']}").status_code == 200
    response = isolated_client.put(f"/item/{item['id']}", json={"name": "new", "price": 99})
    assert response.status_code == 404
    assert isolated_client.get("/item", params={"show_deleted": True}).json() == [
        {**item, "deleted": True},
    ]


def test_startup_and_metrics(isolated_client):
    # The fixture enters TestClient's context, executing the real application lifespan.
    assert isolated_client.get("/cart").json() == []
    item = create_item(isolated_client)
    assert isolated_client.get(f"/item/{item['id']}").json() == item
    response = isolated_client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


@pytest.mark.parametrize("missing", ["item", "cart"])
def test_foreign_keys_and_transaction_rollback(isolated_client, missing):
    item = create_item(isolated_client)
    cart_id = create_cart(isolated_client)
    with pytest.raises(IntegrityError):
        storage.add_item_to_cart(
            999 if missing == "cart" else cart_id,
            999 if missing == "item" else item["id"],
        )
    assert storage.get_cart(cart_id).quantity == 0
    storage.add_item_to_cart(cart_id, item["id"])
    assert storage.get_cart(cart_id).quantity == 1
    assert storage.get_cart(cart_id).price == item["price"]


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
