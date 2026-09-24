# flask-api-builder

Convention-based RESTful CRUD API endpoints & Marshmallow schema generator for Flask + SQLAlchemy:

- **`ApiBuilder`**: Automatic CRUD endpoints for collection + item routes (`list`, `create`, `retrieve`, `update`, `patch`, `delete`).
  - Filtering, search, sorting, and pagination out-of-the-box.
  - MethodView architecture with standard endpoint naming (`api.<endpoint>`, `api.<endpoint>_item`).
  - Nested routes & Singletons (`view_args`, `view_args_ref`, `singleton=True`).
  - **Custom endpoints & logic**: `extra_methods`, `extra_actions`, and `@builder.action(...)` decorator.
  - **4-tier customization**: `overrides`, `schemas`, `responses` (envelopes), `errors` (formatters).
- **`SchemaBuilder`**: Declarative `marshmallow-sqlalchemy` schema generator from SQLAlchemy models:
  - Automatic relationship discovery & nesting (`auto_relationships=True` or `relationships={'only': ...}`).
  - **Automatic cardinality detection**: Uses SQLAlchemy `relationship.uselist` under the hood to automatically configure single vs. list (`many=True`) relationships without manual flags.
  - Per-field tuning via `rel_fields={'field': {'only': ..., 'exclude': ..., 'write': ..., 'depth': ...}}`.
  - Computed output fields via `methods={'key': lambda obj: ...}`.
  - Optional WTForms-Alchemy integration via `schema.build_form()`.

## Install

From GitHub:

```bash
pip install git+https://github.com/DanielKEdozie/flask-api-builder.git
```

Or in `requirements.txt`:

```text
flask-api-builder @ git+https://github.com/DanielKEdozie/flask-api-builder.git@v2.2.0
```

## Quick Start

```python
from flask import Flask, Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_api_builder import FlaskApiBuilder, ApiBuilder, SchemaBuilder

app = Flask(__name__)
db = SQLAlchemy(app)
ma = Marshmallow(app)

# Initialize extension with global response and error envelopes:
api_ext = FlaskApiBuilder()
api_ext.init_app(app, db=db, ma=ma, responses={
    'paginated': lambda data, ctx: {
        'data': data['items'],
        'pagination': {
            'page': data['page'],
            'per_page': data['per_page'],
            'pages': data['pages'],
            'total': data['total'],
        }
    }
}, errors={
    422: lambda err, ctx: {'success': False, 'errors': err.messages},
    404: lambda err, ctx: {'success': False, 'message': 'Not found'},
})

# 1. Generate Schema with automatic relationship discovery:
CategorySchema = SchemaBuilder(
    Category,
    auto_relationships=True,
    depth=1,
    rel_fields={
        'products': {'only': ('id', 'name', 'price'), 'write': False}
    }
)

ProductSchema = SchemaBuilder(
    Product,
    relationships={'only': ('category',)},
    rel_fields={'category': {'only': ('id', 'name')}},
)

# 2. Build CRUD API Endpoints:
api_bp = Blueprint('api', __name__, url_prefix='/api')

ApiBuilder(
    api_bp,
    model=Product,
    schema=ProductSchema,
    resource_name='products',
    url_prefix='/products',
    filter_fields=('category_id', 'is_active'),
    search_fields=('name', 'sku'),
    sort_field='name',
    paginate=True,
    # Custom RPC / action endpoints:
    extra_actions={
        'duplicate': lambda item, builder: {'duplicated_id': item.id},
        'stats': {
            'methods': ['GET'],
            'detail': False,
            'handler': lambda query, builder: {'total': query.count()},
        }
    }
)

app.register_blueprint(api_bp)
```

## Appending Custom Views & Methods (`extra_methods` / `extra_actions` / `@builder.action`)

Append custom logic and views directly onto an established route prefix (e.g. `/products`). Actions registered on a blueprint (e.g. `api`) automatically yield endpoint names like `api.products_publish` (accessible via `url_for('api.products_publish', publish_id=...)`).

You can write standard Flask-style views, inspect `request.method`, receive route variables by name, and choose whether to inherit from `ApiBuilder` or define your own schema:

```python
from flask import Blueprint, request
from flask_api_builder import ApiBuilder

api = Blueprint('api', __name__, url_prefix='/api')

# Define custom view with standard Flask logic:
def publish(publish_id=None):
    if request.method == 'POST':
        return {'status': 'published', 'id': publish_id}
    return {'status': 'draft', 'id': publish_id}

# Option A: Register via extra_methods in constructor
products = ApiBuilder(
    api,
    Product,
    schema=ProductSchema,
    resource_name='products',
    extra_methods={
        'publish': {
            'methods': ['POST', 'GET'],
            'path': '/<publish_id>/publish',
            'handler': publish,
        },
        'discount': {
            'methods': ['POST'],
            'path': '/<publish_id>/discount',
            'schema': DiscountSchema,  # Custom action schema
            'handler': lambda publish_id, data: {'id': publish_id, 'percent': data['percent']},
        },
    }
)

# Option B: Register dynamically with decorators
@products.action('archive', path='/<publish_id>/archive', methods=['POST'])
def archive_product(builder, publish_id=None):
    item = builder.session.get(builder.model, int(publish_id))
    item.status = 'archived'
    builder.session.commit()
    return {'status': item.status, 'id': publish_id}
```

## License

MIT
