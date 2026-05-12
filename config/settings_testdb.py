from .settings import *  # noqa: F403,F401


DATABASES["default"]["NAME"] = BASE_DIR / "db_test.sqlite3"  # noqa: F405
