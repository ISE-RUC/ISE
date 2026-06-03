# 党团事务模块

本目录用于承载 ISE 项目中的党团事务模块代码与说明文档。

当前仓库中的 `party` 模块已经不再是纯骨架，现已具备以下能力：

- 学生端首页、时间轴、材料页、历史页
- 管理端成员列表、审批工作台、规则配置、导入导出
- 管理端批量审批
- 提醒同步
- 审批撤回链路
- Excel 导入导出
- 基础自动化测试

主要代码位置：

- `models.py`：核心数据模型
- `views.py`：学生端与管理端视图
- `services/`：流程、审批、提醒、导入导出
- `forms.py`：上传、审批、规则、导入相关表单
- `docs/architecture.md`：设计说明

推荐优先阅读的文档：

- [docs/architecture.md](/C:/Users/LENOVO/Desktop/vs/ISE/apps/party/docs/architecture.md)
- [docs/党团模块管理员操作手册.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块管理员操作手册.md)
- [docs/党团模块学生端使用手册.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块学生端使用手册.md)
- [docs/党团模块测试库启动与验收清单.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块测试库启动与验收清单.md)

当前建议的后续任务顺序：

1. 先按验收清单完成完整人工检测
2. 收口人工验收发现的问题
3. 增强管理端高密度视图与联动
4. 推进提醒调度计划任务化
5. 评估并落地 `track_type=league` 入团流程
6. 继续整理交付与部署文档

更详细的任务拆分见：

- [docs/党团模块开发清单.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块开发清单.md)
- [docs/党团事务模块实施方案.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团事务模块实施方案.md)
