# 长文本转图片应用 - 生产环境部署指南

## 概述

本应用支持将长文本智能拆分并生成对应图片，集成了字节火山方舟doubao 1.6 Thinking API和SeeDream 4.0 API。本指南将帮助您在阿里云服务器上部署应用，并配置SSL证书实现HTTPS访问。

## 架构说明

```
用户请求 → Nginx (SSL终端) → 前端静态文件 / API代理 → 后端FastAPI服务
```

- **前端**: Vue.js 3 + Vite构建的SPA应用
- **后端**: FastAPI + Python 3.11
- **代理**: Nginx反向代理，支持SSL/TLS
- **容器化**: Docker + Docker Compose

## 部署前准备

### 1. 服务器要求
- **操作系统**: Ubuntu 20.04+ 或 CentOS 7+
- **内存**: 最低2GB，推荐4GB+
- **存储**: 最低20GB可用空间
- **网络**: 公网IP，开放80、443端口

### 2. 域名和SSL证书
- 已备案的域名
- 阿里云SSL证书（已购买）
- DNS解析指向服务器IP

### 3. API密钥
- 字节火山方舟doubao API密钥
- SeeDream API密钥

## 快速部署（推荐）

### 方式一：一键部署脚本

```bash
# 1. 上传项目文件到服务器
scp -r long-text-to-images-app root@your-server-ip:/tmp/

# 2. 连接服务器
ssh root@your-server-ip

# 3. 进入部署目录
cd /tmp/long-text-to-images-app/deploy

# 4. 给脚本执行权限
chmod +x deploy.sh

# 5. 运行部署脚本
./deploy.sh
```

脚本会自动：
- 安装系统依赖
- 配置防火墙
- 设置SSL证书
- 部署Docker容器
- 配置Nginx
- 启动所有服务

### 方式二：手动部署

#### 1. 安装依赖
```bash
# Ubuntu/Debian
apt update
apt install -y docker.io docker-compose nginx openssl curl

# CentOS/RHEL
yum update -y
yum install -y docker docker-compose nginx openssl curl

# 启动Docker
systemctl enable docker
systemctl start docker
```

#### 2. 配置SSL证书
```bash
# 创建SSL目录
mkdir -p /etc/nginx/ssl

# 上传阿里云SSL证书文件
# 将 your-domain.com.pem 和 your-domain.com.key 上传到 /etc/nginx/ssl/

# 设置权限
chmod 644 /etc/nginx/ssl/*.pem
chmod 600 /etc/nginx/ssl/*.key
```

#### 3. 修改配置文件
```bash
# 编辑Nginx配置
vim deploy/nginx/nginx.conf

# 替换以下内容：
# - your-domain.com → 您的实际域名
# - SSL证书路径
```

#### 4. 配置环境变量
```bash
# 创建后端环境变量文件
cat > backend/.env << EOF
DOUBAO_API_KEY=your_doubao_api_key
SEEDREAM_API_KEY=your_seedream_api_key
ENVIRONMENT=production
EOF
```

#### 5. 部署应用
```bash
# 进入部署目录
cd deploy

# 启动服务
docker-compose up -d --build

# 配置Nginx
cp nginx/nginx.conf /etc/nginx/nginx.conf
nginx -t
systemctl restart nginx
```

## 配置说明

### Nginx配置特性
- **SSL/TLS**: 支持TLS 1.2和1.3
- **安全头**: HSTS、X-Frame-Options等
- **Gzip压缩**: 优化传输性能
- **反向代理**: API请求代理到后端
- **静态文件**: 高效服务前端资源

### Docker服务
- **backend**: FastAPI后端服务（端口8000）
- **frontend**: Vue.js前端构建
- **nginx**: 反向代理和SSL终端

### 安全配置
- SSL证书自动重定向HTTP到HTTPS
- 安全的密码套件配置
- 防止常见Web攻击的安全头

## 验证部署

### 1. 检查服务状态
```bash
# 检查Docker容器
docker-compose ps

# 检查Nginx状态
systemctl status nginx

# 检查端口监听
netstat -tlnp | grep -E ':(80|443|8000)'
```

### 2. 测试访问
```bash
# 测试HTTPS访问
curl -I https://your-domain.com

# 测试API
curl https://your-domain.com/api/health

# 测试API文档
curl https://your-domain.com/docs
```

### 3. SSL证书验证
- 在线检测：https://www.ssllabs.com/ssltest/
- 浏览器访问：检查绿色锁图标

## 管理命令

### 日常运维
```bash
# 查看应用日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 更新应用
git pull
docker-compose up -d --build

# 查看资源使用
docker stats
```

### 备份和恢复
```bash
# 备份配置文件
tar -czf backup-$(date +%Y%m%d).tar.gz /opt/text-to-images

# 备份SSL证书
cp -r /etc/nginx/ssl /backup/ssl-$(date +%Y%m%d)
```

## 监控和日志

### 日志位置
- **Nginx访问日志**: `/var/log/nginx/access.log`
- **Nginx错误日志**: `/var/log/nginx/error.log`
- **应用日志**: `docker-compose logs`

### 性能监控
```bash
# 系统资源
htop
df -h
free -h

# 网络连接
ss -tuln

# Docker资源
docker system df
docker stats
```

## 故障排除

### 常见问题

1. **SSL证书错误**
   ```bash
   # 检查证书有效性
   openssl x509 -in /etc/nginx/ssl/your-domain.com.pem -text -noout
   
   # 检查证书和私钥匹配
   openssl x509 -noout -modulus -in certificate.pem | openssl md5
   openssl rsa -noout -modulus -in private.key | openssl md5
   ```

2. **端口占用**
   ```bash
   # 查看端口占用
   lsof -i :80
   lsof -i :443
   
   # 停止冲突服务
   systemctl stop apache2
   ```

3. **Docker容器启动失败**
   ```bash
   # 查看详细错误
   docker-compose logs backend
   docker-compose logs frontend
   
   # 重新构建
   docker-compose build --no-cache
   ```

4. **API调用失败**
   - 检查API密钥配置
   - 验证网络连接
   - 查看后端日志

### 性能优化

1. **启用缓存**
   - Redis缓存（可选）
   - Nginx静态文件缓存

2. **负载均衡**
   - 多后端实例
   - Nginx upstream配置

3. **CDN加速**
   - 阿里云CDN
   - 静态资源分离

## 更新和维护

### 应用更新
```bash
# 1. 备份当前版本
docker-compose down
cp -r /opt/text-to-images /backup/app-$(date +%Y%m%d)

# 2. 更新代码
git pull origin main

# 3. 重新部署
docker-compose up -d --build

# 4. 验证更新
curl -I https://your-domain.com/health
```

### SSL证书更新
```bash
# 1. 备份旧证书
cp -r /etc/nginx/ssl /backup/ssl-old

# 2. 上传新证书
# 替换证书文件

# 3. 重启Nginx
nginx -t
systemctl reload nginx

# 4. 验证新证书
openssl x509 -in /etc/nginx/ssl/your-domain.com.pem -noout -dates
```

## 联系支持

如果在部署过程中遇到问题，请检查：
1. 服务器系统要求
2. 网络和防火墙配置
3. SSL证书格式和权限
4. API密钥配置
5. Docker和Nginx日志

---

**注意**: 请确保定期备份重要数据和配置文件，并保持系统和依赖的及时更新。