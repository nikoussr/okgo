# app/api/v1/endpoints/__init__.py
from . import auth
from . import users
from . import trips
from . import vehicles
from . import reviews
from . import admin

__all__ = [
    "auth",
    "users",
    "trips",
    "vehicles",
    "reviews",
    "admin"
]