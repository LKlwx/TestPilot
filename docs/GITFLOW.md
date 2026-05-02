# Git分支管理规范

> 本项目主分支命名为 main

## 分支类型

| 分支 | 用途 | 命名规则 |
|------|------|----------|
| main | 生产环境代码 | 保持稳定，不直接提交 |
| develop | 开发环境代码 | 集成分支 |
| feature/* | 新功能开发 | feature/功能名 |
| bugfix/* | 普通Bug修复 | bugfix/功能名 |
| hotfix/* | 紧急修复 | hotfix/问题描述 |
| release/* | 发布准备 | release/版本号 |

## 常用命令

```bash
# 创建功能分支
git checkout -b feature/xxx develop

# 合并到develop
git checkout develop
git merge feature/xxx
git branch -d feature/xxx

# 创建release分支
git checkout -b release/v1.0 develop

# 发布完成合并到main
git checkout main
git merge release/v1.0
git tag -a v1.0 -m "版本说明"
```

## 代码评审要求

- feature分支合并到develop前需要Code Review
- 至少一人code review通过才能合并
- hotfix可直接合并到main和develop

## 注意事项

- 不允许直接在main/develop分支直接提交代码
- 分支合并时需要解决冲突
- 发布前需要打tag标记版本