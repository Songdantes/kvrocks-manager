# KVrocks Manager

> **🌐 [English](README.md) | 中文文档**

一个用于管理 [Apache KVrocks](https://github.com/apache/kvrocks) 集群的全栈 Web 平台。支持集群增删改查、节点管理、扩缩容操作、KVrocks Controller 集成以及基于角色的访问控制。

## 功能特性

- **集群管理** — 创建和管理主从集群与分片集群，实时节点状态，拓扑可视化
- **扩缩容操作** — 故障转移、添加/移除分片、Slot 迁移、添加/移除节点，完整操作历史记录
- **Controller 集成** — 注册 KVrocks Controller，发现并导入已有集群，同步拓扑
- **节点管理** — 添加/移除节点，查看配置，执行命令，健康监控
- **权限控制（RBAC）** — 内置角色（super_admin、cluster_admin、operator、readonly），细粒度 `module:action` 权限
- **仪表盘** — 集群/节点数量与状态一目了然

## 概览

![仪表盘](docs/images/dashboard.png)

![集群拓扑](docs/images/cluster-topology.png)

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI, SQLAlchemy 2.0 (async), Python 3.11 |
| 前端 | Vue 3 (Composition API), Vite 5, Element Plus, Pinia, ECharts |
| 数据库 | MySQL 8.0（生产环境）, SQLite（开发环境） |
| 缓存 | Redis 7 |
| 部署 | Docker Compose, Nginx, Gunicorn |

## 快速开始

### Docker Compose（推荐）

<details>
<summary><strong>安装 Docker（如未安装）</strong></summary>

```bash
# 安装 yum-utils
yum install -y yum-utils

# 添加 Docker 阿里云镜像源
yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo

# 安装 Docker
yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动并设置开机自启
systemctl start docker && systemctl enable docker

# 验证
docker --version
docker compose version
```

如果 Docker Hub 拉取镜像慢，配置镜像加速：

```bash
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.m.daocloud.io",
    "https://hub-mirror.c.163.com"
  ]
}
EOF
systemctl daemon-reload && systemctl restart docker
```

</details>

```bash
# 克隆仓库
git clone https://github.com/Songdantes/kvrocks-manager.git
cd kvrocks-manager

# 配置环境变量
cp .env.example .env
# 编辑 .env — 设置 SECRET_KEY、MYSQL_ROOT_PASSWORD、MYSQL_PASSWORD

# 构建并启动
docker compose up -d
```

启动后可访问：
- 前端界面：http://localhost
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

默认登录账号：`admin` / `admin123`

<<<<<<< HEAD
=======
### 手动部署

> **注意：** 本项目依赖 Nginx、MySQL 和 Redis，请自行手动安装部署。

```bash
./deploy/deploy.sh manual
```

将自动配置：
- 带 gunicorn 的 Python 虚拟环境
- 后端 Systemd 服务
- Nginx 反向代理配置
- 前端静态文件构建

详见 `deploy/` 目录下的配置文件。

>>>>>>> a087710 (modify README.md)
### 本地开发

**后端：**

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.main  # 在 :8000 启动，支持热重载
```

本地开发默认使用 SQLite。设置 `DATABASE_URL` 环境变量可切换为 MySQL。

**前端：**

```bash
cd frontend
npm install
npm run dev  # 在 :3000 启动，/api 代理到 :8000
```

## 配置说明

所有后端配置通过环境变量驱动，详见 `backend/app/config.py`。主要变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接字符串 | `sqlite+aiosqlite:///./kvrocks_manager.db` |
| `SECRET_KEY` | JWT 签名密钥 | *（生产环境必填）* |
| `REDIS_URL` | Redis 连接地址 | `redis://localhost:6379/0` |
| `KVROCKS_CONTROLLER_URL` | Controller 地址（可选） | *（无）* |
| `KVROCKS_DEFAULT_NAMESPACE` | 默认 Controller 命名空间 | `default` |

## API 概览

所有路由位于 `/api` 前缀下，认证使用 JWT Bearer Token。

| 模块 | 端点 | 说明 |
|------|------|------|
| `/api/auth` | login, logout, me, refresh | 认证 |
| `/api/clusters` | CRUD + 状态刷新 | 集群管理 |
| `/api/nodes` | CRUD + 操作 | 节点管理 |
| `/api/clusters/{id}/scaling` | topology, failover, add/remove shard, migrate slots, tasks | 扩缩容操作 |
| `/api/controllers` | CRUD + discover, import, health check | Controller 集成 |
| `/api/users` | CRUD + 密码管理 | 用户管理 |
| `/api/roles` | CRUD | 角色管理 |
| `/api/permissions` | list | 权限列表 |

后端运行时可通过 `/docs`（Swagger UI）查看完整的交互式 API 文档。

## 扩缩容操作

针对由 [KVrocks Controller](https://github.com/apache/kvrocks-controller) 管理的分片集群：

| 操作 | 说明 |
|------|------|
| 故障转移 | 将从节点提升为主节点 |
| 添加分片 | 添加新分片（含主节点和可选从节点） |
| 移除分片 | 移除分片（先将 Slot 迁移到其他分片） |
| Slot 迁移 | 在分片之间移动 Slot 范围 |
| 添加/移除节点 | 水平扩展单个分片 |

所有扩缩容操作均有详细的执行日志记录。

## 权限控制（RBAC）

内置角色及可配置权限：

| 角色 | 访问级别 |
|------|----------|
| `super_admin` | 完全访问（隐式） |
| `cluster_admin` | 集群/节点/扩缩容 CRUD，备份，命令执行 |
| `operator` | 只读 + 节点操作，执行命令，查看任务 |
| `readonly` | 所有资源只读访问 |

可创建自定义角色，任意组合权限。

## 部署

### Docker Compose

参见 `docker-compose.yml` 了解完整部署配置。需要 `.env` 文件配置数据库密码和密钥。

### 手动部署

```bash
./deploy/deploy.sh manual
```

将自动配置：
- 带 gunicorn 的 Python 虚拟环境
- 后端 Systemd 服务
- Nginx 反向代理
- 前端静态文件构建

详见 `deploy/` 目录下的配置文件。

## 许可证

[Apache License 2.0](LICENSE)
