# 族谱管理系统

这是一个用于数据库课程/实验验收的族谱管理 Demo，包含 PostgreSQL 数据库设计、FastAPI 后端、Vue 前端、10 万级模拟数据生成、CSV 导入导出、核心 SQL 与实验报告。

## 技术栈

- 数据库：PostgreSQL，本地 Windows 安装，默认端口 `5432`
- 后端：FastAPI、SQLAlchemy、Alembic、JWT
- 前端：Vue 3、Vite、TypeScript、Lucide
- 数据工程：Python CSV 生成脚本、PowerShell + `psql` 导入导出脚本

## Windows 安装 PostgreSQL

1. 下载并安装 PostgreSQL 16 或更高版本。
2. 安装时记录 `postgres` 超级用户密码。
3. 将 PostgreSQL 的 `bin` 目录加入 PATH，例如：

```powershell
$env:Path += ";C:\Program Files\PostgreSQL\16\bin"
psql --version
```

4. 创建数据库用户和数据库：

```powershell
psql -U postgres
```

```sql
CREATE USER genealogy_app WITH PASSWORD 'genealogy_password';
CREATE DATABASE genealogy OWNER genealogy_app;
\c genealogy
CREATE EXTENSION IF NOT EXISTS pg_trgm;
\q
```

## 后端启动

所有 Python 命令都应在 `backend/.venv` 中运行。

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

默认 API 地址：`http://localhost:8000`

## 前端启动

```powershell
cd frontend
npm install
npm run dev
```

默认前端地址：`http://127.0.0.1:5173`

## 生成与导入演示数据

先激活 `backend/.venv`，再回到仓库根目录执行：

```powershell
python scripts/generate_demo_data.py --output data/generated
python scripts/validate_generated_data.py --input data/generated
.\scripts\import_csv.ps1 -Database genealogy -User genealogy_app -DataDir data\generated -Reset
```

默认生成：

- 10 个族谱
- 105000 名成员
- 第 1 个族谱 52000 名成员
- 每个族谱 30 代
- 无孤立成员

`-Reset` 会清空当前数据库中的业务数据并重新导入演示数据。新注册账号默认没有族谱，所以注册后看不到数据是正常的；导入演示数据后，请使用下面的演示账号查看已有族谱和成员。

演示账号：

- 邮箱：`user01@example.com`
- 密码：`Genealogy@123`

## 导出分支备份

```powershell
.\scripts\export_branch.ps1 -Database genealogy -User genealogy_app -RootMemberId 1 -Output data\exports\branch_1.csv
```

## 性能对比

```powershell
.\scripts\run_performance_compare.ps1 -Database genealogy -User genealogy_app -RootMemberId 1
```

脚本会对“查询某曾祖父的所有曾孙”执行无索引/有索引的 `EXPLAIN ANALYZE` 对比。

## 检查命令

后端：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m ruff check app tests ..\scripts
python -m pytest tests
```

前端：

```powershell
cd frontend
npm audit --audit-level=moderate
npm run build
```

## 目录结构

```text
backend/          FastAPI 后端、模型、测试、Alembic 配置
database/         PostgreSQL 建表、索引、核心查询、性能对比 SQL
docs/report/      实验报告、SQL 查询逻辑报告、截图目录
frontend/         Vue 3 前端
scripts/          数据生成、校验、导入、导出、性能脚本
```

## Git 注意事项

- `AGENTS.md`、`AGENT.md`、`.agents/`、`.codex/` 不纳入 Git。
- `.env`、大 CSV、数据库文件、构建产物不提交。
- 本仓库只提交源码、脚本、配置、报告和可复现命令。
