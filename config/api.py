"""
API 路由配置
使用 django-ninja 构建 RESTful API
"""
from ninja import NinjaAPI
from ninja.security import django_auth
from apps.certificate.views import router as certificate_router

# 创建 API 实例
api = NinjaAPI(
    title="ISE Platform API",
    version="1.0.0",
    description="信息系统工程平台 API 文档",
    docs_url="/docs/",  # Swagger UI 地址
)

# 示例路由
@api.get("/hello")
def hello(request):
    """示例接口：Hello World"""
    from utils.response import success
    return success(data={"message": "Hello World"})


@api.get("/protected", auth=django_auth)
def protected(request):
    """示例接口：需要登录的接口"""
    from utils.response import success
    return success(data={
        "user": request.user.username,
        "message": "This is a protected endpoint"
    })


# 在这里导入并注册各个 app 的 API 路由
# 例如：
# from apps.users.api import router as users_router
# api.add_router("/users/", users_router)
from apps.qa.views import router as qa_router
from apps.profile.views import router as profile_router

api.add_router("/qa/", qa_router, tags=["问答系统"])

api.add_router("/certificate/", certificate_router, tags=["电子证明与审批"])

api.add_router("/profile/", profile_router, tags=["荣誉画像"])

