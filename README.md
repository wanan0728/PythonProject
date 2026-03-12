# RAG智能客服系统

基于LangChain和Streamlit的RAG智能问答系统，支持邮箱验证码注册。

## 功能特性
- 用户注册登录（邮箱验证码）
- 知识库文档上传（TXT）
- 智能问答（基于通义千问）
- 对话历史记录
- 多用户隔离

## 目录结构
- `app/`: 应用主程序
- `core/`: 核心业务逻辑
- `auth/`: 用户认证
- `history/`: 历史记录
- `config/`: 配置文件
- `data/`: 数据存储
- `utils/`: 工具函数

## 安装运行
1. 安装依赖：`pip install -r requirements.txt`
2. 配置.env文件
3. 运行：`streamlit run app/app_qa.py`