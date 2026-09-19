# 阿里云轻量服务器部署

本方案使用 Docker Compose 部署 Nginx、Vue 前端和 FastAPI 后端；Neo4j 使用 AuraDB 外部实例，SQLite 数据库和上传文件存储在服务器磁盘。

## 配置建议

- **2 vCPU / 2 GiB / 40 GiB**：可用于演示、答辩或少量用户试用。一次只处理一个文档，避免并发上传和抽取。
- **推荐 2 vCPU / 4 GiB**：更适合持续使用。文档 OCR、知识提取和 DeepSeek 问答同时进行时，2 GiB 容易触发内存不足。
- 不要在这台 2 GiB 实例上运行本地 Neo4j；请使用 Neo4j AuraDB，或将服务器升到至少 4 GiB。

## 首次部署

1. 在阿里云防火墙放行 TCP `22`、`80`；绑定域名并启用 HTTPS 后再放行 `443`。
2. 安装 Docker Engine 和 Docker Compose plugin，然后克隆仓库：

   ```bash
   git clone https://github.com/yuanshendawang666/KnowledgeGraph-Navigator.git
   cd KnowledgeGraph-Navigator
   ```

3. 创建生产环境变量。不要把真实密钥提交到 Git：

   ```bash
   cp backend/.env.production.example backend/.env
   nano backend/.env
   openssl rand -hex 32
   ```

   填写 `NEO4J_*`、`DEEPSEEK_API_KEY` 和随机生成的 `SECRET_KEY`。若已绑定域名，同时在服务器 Shell 中设置：

   ```bash
   export CORS_ORIGINS=https://你的域名
   ```

4. 构建并启动：

   ```bash
   docker compose up -d --build
   docker compose ps
   curl http://127.0.0.1/health
   ```

   浏览器访问 `http://服务器公网IP`。首次注册的账号和上传数据保存在 `data/`、`uploads/`，后续更新不会丢失。

## 更新与排障

```bash
git pull --ff-only origin main
docker compose up -d --build
docker compose logs -f backend
```

若内存不足，执行 `free -h` 和 `docker stats` 确认，再升级到 4 GiB；不要用关闭 Neo4j/问答功能来规避问题。
