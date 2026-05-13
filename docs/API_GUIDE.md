# ISE Platform API 调用指南

## 概述

本文档提供 ISE 平台 API 的调用规范、认证方式、响应格式等说明。

本项目使用 **django-ninja** 构建 RESTful API，自动生成 OpenAPI 文档。

## API 文档访问

启动开发服务器后，可通过以下地址访问自动生成的 API 文档：

- **Swagger UI**: http://localhost:8000/api/docs/
- **OpenAPI Schema**: http://localhost:8000/api/openapi.json

## 统一响应格式

所有 API 响应均采用以下 JSON 格式：

```json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | 业务状态码，0 表示成功，非 0 表示失败 |
| msg | string | 响应消息，成功时为 "success"，失败时为具体错误信息 |
| data | any | 响应数据，可以是对象、数组或 null |

### 常见业务状态码

| code | 说明 |
|------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 使用示例

### 基础 API 示例

```python
from ninja import Router
from utils.response import success, error

router = Router()

@router.get("/users")
def list_users(request):
    """获取用户列表"""
    users = [
        {"id": 1, "username": "user1"},
        {"id": 2, "username": "user2"},
    ]
    return success(data={"users": users, "count": 2})

@router.get("/users/{user_id}")
def get_user(request, user_id: int):
    """获取用户详情"""
    if user_id == 0:
        return error(msg="用户不存在", code=404)
    
    return success(data={"id": user_id, "username": f"user{user_id}"})
```

### 使用 Schema 验证请求

```python
from ninja import Router, Schema
from utils.response import success, error

router = Router()

class UserIn(Schema):
    username: str
    email: str
    age: int = None

class UserOut(Schema):
    id: int
    username: str
    email: str

@router.post("/users", response=UserOut)
def create_user(request, data: UserIn):
    """创建用户"""
    # 自动验证 data 是否符合 UserIn schema
    user = {
        "id": 1,
        "username": data.username,
        "email": data.email
    }
    return success(data=user)
```

### 需要认证的 API

```python
from ninja import Router
from ninja.security import django_auth
from utils.response import success, error

router = Router()

@router.get("/me", auth=django_auth)
def get_current_user(request):
    """获取当前登录用户信息"""
    return success(data={
        "id": request.user.id,
        "username": request.user.username,
        "email": request.user.email
    })
```

### 错误处理

```python
from ninja import Router
from utils.response import success, error

router = Router()

@router.get("/items/{item_id}")
def get_item(request, item_id: int):
    """获取物品详情"""
    try:
        # 业务逻辑
        if item_id <= 0:
            return error(msg="无效的 ID", code=400)
        
        # 模拟查询
        item = {"id": item_id, "name": f"Item {item_id}"}
        return success(data=item)
    
    except Exception as e:
        return error(msg=str(e), code=500)
```

## 组织 API 路由

### 方式 1：小项目 - 直接在 `config/api.py` 中编写

适合 API 数量较少的项目：

```python
from ninja import NinjaAPI
from utils.response import success, error

api = NinjaAPI(title="ISE Platform API", version="1.0.0")

@api.get("/users")
def list_users(request):
    """获取用户列表"""
    return success(data={"users": []})

@api.get("/users/{user_id}")
def get_user(request, user_id: int):
    """获取用户详情"""
    return success(data={"id": user_id})
```

### 方式 2：大项目 - 在各 app 的 `views.py` 中创建路由

在现有的 `views.py` 中同时编写 Django 视图和 API 路由。

例如 `apps/users/views.py`：

```python
from django.views.generic import TemplateView
from ninja import Router
from utils.response import success, error

# Django 传统视图（返回 HTML）
class HomeView(TemplateView):
    template_name = 'home.html'

# API 路由（返回 JSON）
router = Router()

@router.get("/list")
def list_users(request):
    """用户列表"""
    return success(data={"users": []})

@router.get("/{user_id}")
def get_user(request, user_id: int):
    """用户详情"""
    return success(data={"id": user_id})
```

然后在 `config/api.py` 中注册：

```python
from ninja import NinjaAPI
from apps.users.views import router as users_router
from apps.qa.views import router as qa_router

api = NinjaAPI(title="ISE Platform API", version="1.0.0")

# 注册各个模块的路由
api.add_router("/users/", users_router, tags=["用户管理"])
api.add_router("/qa/", qa_router, tags=["问答系统"])
```

这样 API 路径会是：
- `/api/users/list`
- `/api/users/1`
- `/api/qa/...`

**优势**：不需要创建额外的 `api.py` 文件，在现有 `views.py` 中统一管理视图和 API。

## 认证方式

### Session 认证（默认）

django-ninja 支持 Django 的 session 认证：

```python
from ninja.security import django_auth

@router.get("/protected", auth=django_auth)
def protected_view(request):
    # request.user 是已认证的用户
    return success(data={"user": request.user.username})
```

**客户端调用**：
```bash
# 先登录获取 session
curl -X POST http://localhost:8000/users/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}' \
  -c cookies.txt

# 后续请求携带 cookie
curl http://localhost:8000/api/protected -b cookies.txt
```

### 自定义认证

```python
from ninja.security import HttpBearer

class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        # 验证 token
        if token == "valid_token":
            return token
        return None

auth = AuthBearer()

@router.get("/protected", auth=auth)
def protected_view(request):
    return success(data={"message": "Authenticated"})
```

## 分页

django-ninja 支持自定义分页：

```python
from ninja import Router, Schema
from ninja.pagination import paginate, PageNumberPagination
from utils.response import success

router = Router()

class ItemOut(Schema):
    id: int
    name: str

@router.get("/items", response=list[ItemOut])
@paginate(PageNumberPagination, page_size=20)
def list_items(request):
    """分页列表"""
    items = [{"id": i, "name": f"Item {i}"} for i in range(100)]
    return items
```

**请求参数**：
- `page`: 页码（从 1 开始）
- `page_size`: 每页数量（可选）

## 错误处理

### 客户端错误处理建议

```javascript
// JavaScript 示例
fetch('/api/users/1')
  .then(response => response.json())
  .then(result => {
    if (result.code === 0) {
      // 成功
      console.log(result.data);
    } else {
      // 业务错误
      alert(result.msg);
    }
  })
  .catch(error => {
    // 网络错误
    console.error('Network error:', error);
  });
```

### 常见错误响应

**参数错误**：
```json
{
  "code": 400,
  "msg": "用户名不能为空",
  "data": null
}
```

**未认证**：
```json
{
  "code": 401,
  "msg": "请先登录",
  "data": null
}
```

**无权限**：
```json
{
  "code": 403,
  "msg": "您没有权限执行此操作",
  "data": null
}
```

## API 开发规范

### 1. 使用统一响应函数

```python
from utils.response import success, error

# 成功
return success(data={"key": "value"})

# 失败
return error(msg="错误信息", code=400)
```

### 2. 使用 Schema 定义数据结构

```python
from ninja import Schema

class UserIn(Schema):
    username: str
    email: str
    age: int = None  # 可选字段

class UserOut(Schema):
    id: int
    username: str
    email: str
```

### 3. 添加文档注释

```python
@router.get("/users/{user_id}")
def get_user(request, user_id: int):
    """
    获取用户详情
    
    根据用户 ID 获取用户的详细信息
    """
    return success(data={"id": user_id})
```

### 4. HTTP 方法使用规范

| 方法 | 用途 | 示例 |
|------|------|------|
| GET | 获取资源 | GET /api/users/ |
| POST | 创建资源 | POST /api/users/ |
| PUT | 完整更新资源 | PUT /api/users/1/ |
| PATCH | 部分更新资源 | PATCH /api/users/1/ |
| DELETE | 删除资源 | DELETE /api/users/1/ |

### 5. URL 命名规范

- 使用小写字母和连字符
- 使用复数形式表示资源集合
- 使用 RESTful 风格

**示例**：
```
GET    /api/users/              # 获取用户列表
POST   /api/users/              # 创建用户
GET    /api/users/1/            # 获取用户详情
PUT    /api/users/1/            # 更新用户
DELETE /api/users/1/            # 删除用户
GET    /api/users/1/profile/    # 获取用户资料
```

## 测试工具

### cURL 示例

```bash
# GET 请求
curl http://localhost:8000/api/hello

# POST 请求
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser", "email": "user@example.com"}'

# 带认证的请求
curl http://localhost:8000/api/protected \
  -H "Authorization: Bearer your-token-here"
```

### Python requests 示例

```python
import requests

# GET 请求
response = requests.get('http://localhost:8000/api/users/')
result = response.json()
if result['code'] == 0:
    print(result['data'])

# POST 请求
response = requests.post(
    'http://localhost:8000/api/users/',
    json={'username': 'newuser', 'email': 'user@example.com'}
)
result = response.json()
```

## 版本控制

当前 API 版本：**v1.0.0**

未来如需版本控制，建议在 URL 中添加版本号：
```python
api_v1 = NinjaAPI(version="1.0.0", urls_namespace="api-v1")
api_v2 = NinjaAPI(version="2.0.0", urls_namespace="api-v2")

# 在 urls.py 中
path('api/v1/', api_v1.urls),
path('api/v2/', api_v2.urls),
```
