"""
API route configuration.

The project uses django-ninja to expose JSON APIs and generate OpenAPI docs.
"""
from ninja import NinjaAPI
from ninja.security import django_auth


api = NinjaAPI(
    title="ISE Platform API",
    version="1.0.0",
    description="Information System Engineering platform API documentation",
    docs_url="/docs/",
)


@api.get("/hello")
def hello(request):
    """Example endpoint."""
    from utils.response import success

    return success(data={"message": "Hello World"})


@api.get("/protected", auth=django_auth)
def protected(request):
    """Example endpoint requiring Django session authentication."""
    from utils.response import success

    return success(
        data={
            "user": request.user.username,
            "message": "This is a protected endpoint",
        }
    )


from apps.certificate.api import router as certificate_router


api.add_router("/certificates/", certificate_router, tags=["Certificate workflow"])
