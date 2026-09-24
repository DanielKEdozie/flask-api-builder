"""Tests for flask-api-builder modern MethodView and endpoint features."""
import pytest
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from marshmallow import fields
from flask_api_builder import FlaskApiBuilder, ApiBuilder, SchemaBuilder


@pytest.fixture
def app_and_db():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db = SQLAlchemy(app)
    ma = Marshmallow(app)
    api_ext = FlaskApiBuilder(app, db=db, ma=ma)

    class Item(db.Model):
        __tablename__ = "items"
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)

    with app.app_context():
        db.create_all()

    class ItemSchema(ma.SQLAlchemyAutoSchema):
        class Meta:
            model = Item
            load_instance = True

    return app, db, ma, Item, ItemSchema


def test_resource_name_support(app_and_db):
    app, db, ma, Item, ItemSchema = app_and_db

    builder = ApiBuilder(
        app,
        Item,
        ItemSchema,
        resource_name="products",
    )

    assert builder.resource_name == "products"
    assert builder.endpoint == "products"
    assert builder.url_prefix == "/products"

    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "products_list" in endpoints
    assert "products_create" in endpoints
    assert "products_retrieve" in endpoints


def test_legacy_endpoint_alias_still_works(app_and_db):
    app, db, ma, Item, ItemSchema = app_and_db

    builder = ApiBuilder(
        app,
        Item,
        ItemSchema,
        endpoint="legacy_items",
    )

    assert builder.resource_name == "legacy_items"
    assert builder.endpoint == "legacy_items"
    assert builder.url_prefix == "/legacy_items"

    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "legacy_items_list" in endpoints
    assert "legacy_items_retrieve" in endpoints


def test_default_methodview_endpoints_no_legacy_aliases(app_and_db):
    app, db, ma, Item, ItemSchema = app_and_db

    ApiBuilder(
        app,
        Item,
        ItemSchema,
        resource_name="items",
        url_prefix="/items",
    )

    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}

    # Verify default action naming is present
    assert "items_list" in endpoints
    assert "items_create" in endpoints
    assert "items_retrieve" in endpoints
    assert "items_update" in endpoints
    assert "items_patch" in endpoints
    assert "items_delete" in endpoints

    # Verify legacy alias endpoints are stripped and NOT present
    assert "items_collection" not in endpoints
    assert "items_detail" not in endpoints
    assert "items_singleton" not in endpoints


def test_custom_method_endpoints(app_and_db):
    app, db, ma, Item, ItemSchema = app_and_db

    ApiBuilder(
        app,
        Item,
        ItemSchema,
        resource_name="widgets",
        url_prefix="/widgets",
        method_endpoints={
            "retrieve": "detail",
            "list": "all",
        },
    )

    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}

    assert "widgets_detail" in endpoints
    assert "widgets_all" in endpoints
    assert "widgets_create" in endpoints
    assert "widgets_delete" in endpoints
    assert "widgets_collection" not in endpoints


def test_responses_accepts_pagination_key(app_and_db):
    app, db, ma, Item, ItemSchema = app_and_db

    with app.app_context():
        db.session.add_all([Item(name="Item 1"), Item(name="Item 2")])
        db.session.commit()

    ApiBuilder(
        app,
        Item,
        ItemSchema,
        resource_name="pag_items",
        url_prefix="/pag-items",
        responses={
            "pagination": lambda data: {
                "custom_envelope": True,
                "data": data["items"],
                "meta": {
                    "total_records": data["total"],
                    "current_page": data["page"],
                }
            }
        }
    )

    client = app.test_client()
    res = client.get("/pag-items")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data.get("custom_envelope") is True
    assert json_data["meta"]["total_records"] == 2
    assert len(json_data["data"]) == 2


def test_responses_accepts_paginated_key(app_and_db):
    app, db, ma, Item, ItemSchema = app_and_db

    with app.app_context():
        db.session.add_all([Item(name="Alpha"), Item(name="Beta")])
        db.session.commit()

    ApiBuilder(
        app,
        Item,
        ItemSchema,
        resource_name="paged_items",
        url_prefix="/paged-items",
        responses={
            "paginated": lambda data: {
                "paginated_envelope": True,
                "rows": data["items"],
            }
        }
    )

    client = app.test_client()
    res = client.get("/paged-items")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data.get("paginated_envelope") is True
    assert len(json_data["rows"]) == 2