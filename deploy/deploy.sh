#!/bin/bash

# 长文本转图片应用一键部署脚本
# 支持阿里云SSL证书配置

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "请使用root用户运行此脚本"
        exit 1
    fi
}

# 检查系统类型
check_system() {
    if [[ -f /etc/redhat-release ]]; then
        OS="centos"
        PM="yum"
    elif [[ -f /etc/debian_version ]]; then
        OS="ubuntu"
        PM="apt"
    else
        log_error "不支持的操作系统"
        exit 1
    fi
    log_info "检测到操作系统: $OS"
}

# 安装依赖
install_dependencies() {
    log_info "安装系统依赖..."
    
    if [[ $OS == "ubuntu" ]]; then
        apt update
        apt install -y curl wget git nginx docker.io docker-compose openssl
        systemctl enable docker
        systemctl start docker
    elif [[ $OS == "centos" ]]; then
        yum update -y
        yum install -y curl wget git nginx docker docker-compose openssl
        systemctl enable docker
        systemctl start docker
    fi
    
    log_success "依赖安装完成"
}

# 配置防火墙
setup_firewall() {
    log_info "配置防火墙..."
    
    if command -v ufw &> /dev/null; then
        ufw --force enable
        ufw allow 22
        ufw allow 80
        ufw allow 443
        ufw allow 8000
    elif command -v firewall-cmd &> /dev/null; then
        systemctl enable firewalld
        systemctl start firewalld
        firewall-cmd --permanent --add-port=22/tcp
        firewall-cmd --permanent --add-port=80/tcp
        firewall-cmd --permanent --add-port=443/tcp
        firewall-cmd --permanent --add-port=8000/tcp
        firewall-cmd --reload
    fi
    
    log_success "防火墙配置完成"
}

# 创建项目目录
setup_directories() {
    log_info "创建项目目录..."
    
    mkdir -p /opt/text-to-images
    mkdir -p /opt/text-to-images/ssl
    mkdir -p /opt/text-to-images/logs
    mkdir -p /opt/text-to-images/data
    
    log_success "目录创建完成"
}

# 配置SSL证书
setup_ssl() {
    log_info "配置SSL证书..."
    
    echo "请提供以下信息:"
    read -p "域名 (例如: example.com): " DOMAIN
    read -p "SSL证书文件路径 (.pem): " CERT_PATH
    read -p "SSL私钥文件路径 (.key): " KEY_PATH
    
    if [[ -f "$CERT_PATH" && -f "$KEY_PATH" ]]; then
        cp "$CERT_PATH" "/opt/text-to-images/ssl/${DOMAIN}.pem"
        cp "$KEY_PATH" "/opt/text-to-images/ssl/${DOMAIN}.key"
        chmod 644 "/opt/text-to-images/ssl/${DOMAIN}.pem"
        chmod 600 "/opt/text-to-images/ssl/${DOMAIN}.key"
        
        log_success "SSL证书配置完成"
    else
        log_warning "SSL证书文件不存在，将使用HTTP模式"
        USE_SSL=false
    fi
}

# 生成Nginx配置
generate_nginx_config() {
    log_info "生成Nginx配置..."
    
    if [[ $USE_SSL == true ]]; then
        # 使用HTTPS配置
        sed "s/your-domain.com/$DOMAIN/g" nginx/nginx.conf > /etc/nginx/nginx.conf
        sed -i "s/your-domain.com.pem/${DOMAIN}.pem/g" /etc/nginx/nginx.conf
        sed -i "s/your-domain.com.key/${DOMAIN}.key/g" /etc/nginx/nginx.conf
    else
        # 生成HTTP配置
        cat > /etc/nginx/nginx.conf << EOF
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    server {
        listen 80;
        server_name $DOMAIN;
        
        location / {
            root /var/www/html;
            index index.html;
            try_files \$uri \$uri/ /index.html;
        }
        
        location /api/ {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        }
        
        location /docs {
            proxy_pass http://127.0.0.1:8000;
        }
    }
}
EOF
    fi
    
    nginx -t
    log_success "Nginx配置生成完成"
}

# 部署应用
deploy_application() {
    log_info "部署应用..."
    
    # 复制项目文件
    cp -r ../* /opt/text-to-images/
    
    # 设置环境变量
    echo "请配置API密钥:"
    read -p "火山方舟API密钥: " DOUBAO_API_KEY
    read -p "SeeDream API密钥: " SEEDREAM_API_KEY
    
    cat > /opt/text-to-images/backend/.env << EOF
DOUBAO_API_KEY=$DOUBAO_API_KEY
SEEDREAM_API_KEY=$SEEDREAM_API_KEY
ENVIRONMENT=production
EOF
    
    # 使用Docker Compose部署
    cd /opt/text-to-images/deploy
    docker-compose up -d --build
    
    log_success "应用部署完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."
    
    systemctl enable nginx
    systemctl start nginx
    systemctl reload nginx
    
    log_success "服务启动完成"
}

# 检查服务状态
check_services() {
    log_info "检查服务状态..."
    
    # 检查Docker容器
    docker-compose ps
    
    # 检查Nginx
    systemctl status nginx --no-pager
    
    # 检查端口
    netstat -tlnp | grep -E ':(80|443|8000)'
    
    log_success "服务检查完成"
}

# 显示部署信息
show_info() {
    log_success "=== 部署完成 ==="
    echo
    log_info "访问地址:"
    if [[ $USE_SSL == true ]]; then
        echo "  前端: https://$DOMAIN"
        echo "  API文档: https://$DOMAIN/docs"
    else
        echo "  前端: http://$DOMAIN"
        echo "  API文档: http://$DOMAIN/docs"
    fi
    echo
    log_info "管理命令:"
    echo "  查看日志: docker-compose logs -f"
    echo "  重启服务: docker-compose restart"
    echo "  停止服务: docker-compose down"
    echo "  更新应用: docker-compose up -d --build"
    echo
    log_info "配置文件位置:"
    echo "  项目目录: /opt/text-to-images"
    echo "  Nginx配置: /etc/nginx/nginx.conf"
    echo "  SSL证书: /opt/text-to-images/ssl"
    echo
}

# 主函数
main() {
    log_info "开始部署长文本转图片应用..."
    
    USE_SSL=true
    
    check_root
    check_system
    install_dependencies
    setup_firewall
    setup_directories
    setup_ssl
    generate_nginx_config
    deploy_application
    start_services
    check_services
    show_info
    
    log_success "部署完成！"
}

# 执行主函数
main "$@"