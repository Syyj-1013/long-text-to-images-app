# SSL证书配置指南

## 阿里云SSL证书部署步骤

### 1. 下载SSL证书
从阿里云SSL证书控制台下载证书文件，通常包含：
- `your-domain.com.pem` (证书文件)
- `your-domain.com.key` (私钥文件)

### 2. 上传证书到服务器
```bash
# 创建SSL证书目录
sudo mkdir -p /etc/nginx/ssl

# 上传证书文件（替换为您的实际文件名）
sudo scp your-domain.com.pem root@your-server-ip:/etc/nginx/ssl/
sudo scp your-domain.com.key root@your-server-ip:/etc/nginx/ssl/

# 设置证书文件权限
sudo chmod 600 /etc/nginx/ssl/your-domain.com.key
sudo chmod 644 /etc/nginx/ssl/your-domain.com.pem
```

### 3. 修改Nginx配置
编辑 `deploy/nginx/nginx.conf` 文件，更新以下内容：

```nginx
# 替换域名
server_name your-actual-domain.com www.your-actual-domain.com;

# 替换SSL证书路径
ssl_certificate /etc/nginx/ssl/your-actual-domain.com.pem;
ssl_certificate_key /etc/nginx/ssl/your-actual-domain.com.key;
```

### 4. Docker部署配置

#### 方式一：使用Docker Compose（推荐）
```bash
# 进入部署目录
cd deploy

# 创建SSL证书目录
mkdir -p ssl

# 复制证书文件到ssl目录
cp /path/to/your-domain.com.pem ssl/
cp /path/to/your-domain.com.key ssl/

# 启动服务
docker-compose up -d
```

#### 方式二：直接在服务器部署
```bash
# 安装Nginx
sudo apt update
sudo apt install nginx

# 复制配置文件
sudo cp nginx/nginx.conf /etc/nginx/nginx.conf

# 测试配置
sudo nginx -t

# 重启Nginx
sudo systemctl restart nginx
```

### 5. 防火墙配置
```bash
# 开放HTTP和HTTPS端口
sudo ufw allow 80
sudo ufw allow 443

# 或者使用iptables
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### 6. 域名解析配置
在您的域名DNS管理中添加A记录：
```
类型: A
主机记录: @
记录值: 您的服务器IP地址
TTL: 600

类型: A
主机记录: www
记录值: 您的服务器IP地址
TTL: 600
```

### 7. 验证SSL证书
```bash
# 检查SSL证书
openssl x509 -in /etc/nginx/ssl/your-domain.com.pem -text -noout

# 测试HTTPS连接
curl -I https://your-domain.com

# 在线SSL检测
# 访问: https://www.ssllabs.com/ssltest/
```

### 8. 自动续期（如果使用Let's Encrypt）
如果后续需要免费SSL证书，可以使用Certbot：
```bash
# 安装Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# 测试自动续期
sudo certbot renew --dry-run
```

## 常见问题

### 1. 证书格式问题
- 确保使用PEM格式的证书
- 如果是其他格式，需要转换：
```bash
# PKCS#12 转 PEM
openssl pkcs12 -in certificate.p12 -out certificate.pem -nodes
```

### 2. 权限问题
```bash
# 确保Nginx用户可以读取证书
sudo chown -R nginx:nginx /etc/nginx/ssl
sudo chmod 600 /etc/nginx/ssl/*.key
sudo chmod 644 /etc/nginx/ssl/*.pem
```

### 3. 端口占用
```bash
# 检查端口占用
sudo netstat -tlnp | grep :443
sudo netstat -tlnp | grep :80

# 停止占用端口的服务
sudo systemctl stop apache2  # 如果安装了Apache
```

## 安全建议

1. **定期更新证书**：SSL证书有有效期，需要定期更新
2. **使用强密码套件**：配置文件中已包含安全的SSL配置
3. **启用HSTS**：强制使用HTTPS连接
4. **隐藏服务器信息**：避免暴露服务器版本信息
5. **定期安全扫描**：使用工具检测SSL配置安全性

## 监控和日志

```bash
# 查看Nginx访问日志
sudo tail -f /var/log/nginx/access.log

# 查看Nginx错误日志
sudo tail -f /var/log/nginx/error.log

# 查看SSL证书到期时间
openssl x509 -in /etc/nginx/ssl/your-domain.com.pem -noout -dates
```