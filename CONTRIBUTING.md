# 贡献指南 Contributing Guide

感谢您对长文本转图片应用的关注！我们欢迎任何形式的贡献。

## 如何贡献

### 报告问题 (Issues)
- 在提交问题前，请先搜索现有的 Issues
- 使用清晰的标题描述问题
- 提供详细的问题描述和复现步骤
- 如果可能，请提供错误截图

### 提交代码 (Pull Requests)
1. Fork 这个仓库
2. 创建您的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

### 开发环境设置

#### 前端开发
```bash
cd frontend
npm install
npm run dev
```

#### 后端开发
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

### 代码规范
- 前端：遵循 Vue.js 官方风格指南
- 后端：遵循 PEP 8 Python 代码规范
- 提交信息：使用清晰的中文或英文描述

### 测试
- 确保所有现有测试通过
- 为新功能添加相应的测试
- 测试覆盖率应保持在合理水平

## 开发指南

### 项目结构
```
├── frontend/          # Vue.js 前端应用
├── backend/           # FastAPI 后端服务
├── deploy/            # 部署配置文件
└── README.md          # 项目说明
```

### 功能开发流程
1. 在 Issues 中讨论新功能
2. 创建功能分支
3. 开发并测试功能
4. 提交 Pull Request
5. 代码审查
6. 合并到主分支

## 联系方式
如有任何问题，请通过 GitHub Issues 联系我们。

感谢您的贡献！🎉