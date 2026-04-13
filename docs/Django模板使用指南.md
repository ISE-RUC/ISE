# Django 模板使用指南

## 模板基础

Django 模板是带有特殊标签的 HTML 文件，用于动态生成网页内容。

## 模板语法

### 1. 变量

使用 `{{ }}` 输出变量：

```html
<h1>{{ title }}</h1>
<p>欢迎，{{ user.username }}</p>
```

### 2. 标签

使用 `{% %}` 执行逻辑：

```html
{% if user.is_authenticated %}
    <p>已登录</p>
{% else %}
    <p>未登录</p>
{% endif %}

{% for item in items %}
    <li>{{ item.name }}</li>
{% endfor %}
```

### 3. 注释

```html
{# 这是单行注释 #}

{% comment %}
这是多行注释
可以写很多行
{% endcomment %}
```

## 模板继承

### 基础模板 (base.html)

```html
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}默认标题{% endblock %}</title>
</head>
<body>
    <header>
        <!-- 导航栏 -->
    </header>

    <main>
        {% block content %}
        <!-- 子模板内容将插入这里 -->
        {% endblock %}
    </main>

    <footer>
        {% block footer %}
        <!-- 页脚 -->
        {% endblock %}
    </footer>
</body>
</html>
```

### 子模板

```html
{% extends "base.html" %}

{% block title %}智能问答{% endblock %}

{% block content %}
<div class="card">
    <h1>智能问答页面</h1>
    <p>这里是具体内容</p>
</div>
{% endblock %}
```

## 常用标签

### if 条件判断

```html
{% if score >= 90 %}
    <span class="pill pill-success">优秀</span>
{% elif score >= 60 %}
    <span class="pill pill-primary">及格</span>
{% else %}
    <span class="pill pill-warning">不及格</span>
{% endif %}
```

### for 循环

```html
{% for notice in notices %}
    <div class="notice-item">{{ notice.content }}</div>
{% empty %}
    <p>暂无通知</p>
{% endfor %}
```

循环变量：

```html
{% for item in items %}
    <p>
        第 {{ forloop.counter }} 项：{{ item.name }}
        {% if forloop.first %}（第一项）{% endif %}
        {% if forloop.last %}（最后一项）{% endif %}
    </p>
{% endfor %}
```

### url 路由引用

```html
<!-- 基本用法 -->
<a href="{% url 'qa:index' %}">智能问答</a>

<!-- 带参数 -->
<a href="{% url 'qa:detail' id=123 %}">查看详情</a>

<!-- 带查询参数 -->
<a href="{% url 'qa:search' %}?q=入党流程">搜索</a>
```

### static 静态文件

```html
{% load static %}

<link rel="stylesheet" href="{% static 'css/main.css' %}">
<img src="{% static 'img/logo.png' %}" alt="Logo">
<script src="{% static 'js/app.js' %}"></script>
```

### include 包含其他模板

```html
<!-- 包含导航栏 -->
{% include "components/navbar.html" %}

<!-- 传递变量 -->
{% include "components/card.html" with title="标题" content="内容" %}
```

## 过滤器

过滤器用于修改变量的显示方式：

```html
<!-- 日期格式化 -->
{{ created_at|date:"Y-m-d H:i" }}

<!-- 字符串截断 -->
{{ description|truncatewords:20 }}

<!-- 默认值 -->
{{ user.nickname|default:"匿名用户" }}

<!-- 安全 HTML -->
{{ content|safe }}

<!-- 转义 HTML -->
{{ user_input|escape }}

<!-- 长度 -->
共 {{ items|length }} 项

<!-- 链式使用 -->
{{ text|lower|truncatewords:10 }}
```

## 在视图中传递数据

### 基于类的视图

```python
from django.views.generic import TemplateView

class IndexView(TemplateView):
    template_name = 'qa/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '智能问答'
        context['questions'] = [
            {'id': 1, 'text': '如何入党？'},
            {'id': 2, 'text': '请假流程是什么？'},
        ]
        return context
```

### 基于函数的视图

```python
from django.shortcuts import render

def index(request):
    context = {
        'title': '智能问答',
        'questions': [
            {'id': 1, 'text': '如何入党？'},
            {'id': 2, 'text': '请假流程是什么？'},
        ]
    }
    return render(request, 'qa/index.html', context)
```

## 实用示例

### 1. 列表展示

```html
<div class="notice-list">
    {% for notice in notices %}
    <div class="notice-item">
        <strong>{{ notice.title }}</strong>
        <span>{{ notice.created_at|date:"Y-m-d" }}</span>
        <p>{{ notice.content|truncatewords:30 }}</p>
    </div>
    {% empty %}
    <p class="empty-state">暂无通知</p>
    {% endfor %}
</div>
```

### 2. 表单

```html
<form method="post">
    {% csrf_token %}

    <div class="form-group">
        <label for="question">问题</label>
        <input type="text" id="question" name="question" required>
    </div>

    <div class="form-group">
        <label for="detail">详细描述</label>
        <textarea id="detail" name="detail" rows="5"></textarea>
    </div>

    <button type="submit" class="btn btn-primary">提交</button>
</form>
```

### 3. 分页

```html
<div class="pagination">
    {% if page_obj.has_previous %}
        <a href="?page=1">首页</a>
        <a href="?page={{ page_obj.previous_page_number }}">上一页</a>
    {% endif %}

    <span>第 {{ page_obj.number }} / {{ page_obj.paginator.num_pages }} 页</span>

    {% if page_obj.has_next %}
        <a href="?page={{ page_obj.next_page_number }}">下一页</a>
        <a href="?page={{ page_obj.paginator.num_pages }}">末页</a>
    {% endif %}
</div>
```

### 4. 状态标签

```html
{% if status == 'pending' %}
    <span class="pill pill-warning">待审批</span>
{% elif status == 'approved' %}
    <span class="pill pill-success">已通过</span>
{% elif status == 'rejected' %}
    <span class="pill pill-error">已拒绝</span>
{% endif %}
```

### 5. 空状态

```html
{% if items %}
    {% for item in items %}
        <div class="item">{{ item.name }}</div>
    {% endfor %}
{% else %}
    <div class="empty-state">
        <p>暂无数据</p>
        <a href="{% url 'create' %}" class="btn btn-primary">创建第一条</a>
    </div>
{% endif %}
```

## 自定义过滤器

如需创建自定义过滤器，在 app 目录下创建 `templatetags/` 文件夹：

```
apps/qa/
├── templatetags/
│   ├── __init__.py
│   └── qa_filters.py
```

`qa_filters.py`：

```python
from django import template

register = template.Library()

@register.filter
def highlight(text, keyword):
    """高亮关键词"""
    return text.replace(keyword, f'<mark>{keyword}</mark>')
```

使用：

```html
{% load qa_filters %}

<p>{{ content|highlight:"入党" }}</p>
```

## 最佳实践

### 1. 保持模板简洁

❌ 不推荐：

```html
{% for item in items %}
    {% if item.status == 'active' and item.score > 60 and item.category == 'important' %}
        <!-- 复杂逻辑 -->
    {% endif %}
{% endfor %}
```

✅ 推荐：在视图中处理逻辑

```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['important_items'] = [
        item for item in items
        if item.status == 'active' and item.score > 60 and item.category == 'important'
    ]
    return context
```

### 2. 使用有意义的变量名

```html
<!-- 推荐 -->
{% for notice in unread_notices %}
    <div>{{ notice.title }}</div>
{% endfor %}

<!-- 不推荐 -->
{% for n in list %}
    <div>{{ n.t }}</div>
{% endfor %}
```

### 3. 避免在模板中进行数据库查询

在视图中准备好所有数据，不要在模板中调用 `.all()` 等方法。

### 4. 使用 CSRF 保护

所有 POST 表单都必须包含 `{% csrf_token %}`：

```html
<form method="post">
    {% csrf_token %}
    <!-- 表单字段 -->
</form>
```

## 调试技巧

### 1. 显示变量内容

```html
<pre>{{ variable|pprint }}</pre>
```

### 2. 检查变量类型

```html
{{ variable|type }}
```

### 3. 显示所有上下文变量

```html
{% debug %}
```

## 参考资源

- [Django 模板官方文档](https://docs.djangoproject.com/zh-hans/4.2/topics/templates/)
- [Django 内置标签和过滤器](https://docs.djangoproject.com/zh-hans/4.2/ref/templates/builtins/)
