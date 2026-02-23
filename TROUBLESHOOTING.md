# 常见问题排查

## 首页 500 错误：`no such column: forum_item.content`

### 问题描述

访问首页时返回 `Server Error (500)`，控制台报错：

```
django.db.utils.OperationalError: no such column: forum_item.content
```

### 原因

`Item` 模型继承了 `MarkdownModel`（定义了 `content` 字段），但数据库表中缺少该列，通常是模型变更后未执行迁移导致的。

### 解决方法

```bash
python manage.py makemigrations
python manage.py migrate
```

> 如果使用虚拟环境，请确保先激活虚拟环境再执行上述命令。
