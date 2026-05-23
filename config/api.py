"""
API 路由配置
使用 django-ninja 构建 RESTful API。
"""

from ninja import NinjaAPI
from ninja.security import django_auth

from apps.certificate.views import router as certificate_router
from apps.qa.views import router as qa_router
from apps.users.views import router as users_router

api = NinjaAPI(
    title="ISE Platform API",
    version="1.0.0",
    description="信息系统工程平台 API 文档。",
    docs_url="/docs/",
)


@api.get("/hello")
def hello(request):
    from utils.response import success

    return success(data={"message": "Hello World"})


@api.get("/protected", auth=django_auth)
def protected(request):
    from utils.response import success

    return success(
        data={
            "user": request.user.username,
            "message": "This is a protected endpoint",
        }
    )


api.add_router("/users/", users_router, tags=["用户认证"])
api.add_router("/qa/", qa_router, tags=["问答系统"])
api.add_router("/certificate/", certificate_router, tags=["电子证明与审批"])
