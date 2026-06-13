# 备案通过后:绑域名 hia.tjhealthycitylab.com + HTTPS(Alibaba Cloud Linux 3)

> 服务器:阿里云 ECS · 上海 · 公网 IP 106.15.57.87 · 应用已在本机 127.0.0.1:8502(systemd 服务 `hia`)。
> 下面用 Nginx 在 443 终止 HTTPS、反代到 8502。**先满足前置,再逐段执行。**

## 前置(三项都满足才往下)
1. **ICP 备案已通过**(`hia.tjhealthycitylab.com` 或主域名 `tjhealthycitylab.com` 已备案)。
2. **安全组**入方向放行 **TCP 80** 和 **443**。
3. **DNS 解析**:阿里云域名解析 → 加 A 记录:主机记录 `hia`,记录值 `106.15.57.87`。
   验证:本机 `ping hia.tjhealthycitylab.com` 解析到该 IP(DNS 生效约几分钟)。

## 1. 装 Nginx
```bash
dnf install -y nginx && systemctl enable --now nginx
```

## 2. 先建 HTTP 站(供证书验证 + 跳转 HTTPS)
```bash
mkdir -p /var/www/acme
cat > /etc/nginx/conf.d/hia.conf <<'EOF'
server {
    listen 80;
    server_name hia.tjhealthycitylab.com;
    location /.well-known/acme-challenge/ { root /var/www/acme; }
    location / { return 301 https://$host$request_uri; }
}
EOF
nginx -t && systemctl reload nginx
```

## 3. 申请免费证书(acme.sh + Let's Encrypt)
```bash
curl https://get.acme.sh | sh -s email=你的邮箱@example.com
~/.acme.sh/acme.sh --set-default-ca --server letsencrypt
~/.acme.sh/acme.sh --issue -d hia.tjhealthycitylab.com --webroot /var/www/acme
```
(若签发失败,多半是 DNS 没生效或 80 端口没通——回查前置 2、3。)

## 4. 安装证书 + 自动续期时 reload Nginx
```bash
mkdir -p /etc/nginx/ssl
~/.acme.sh/acme.sh --install-cert -d hia.tjhealthycitylab.com \
  --key-file       /etc/nginx/ssl/hia.key \
  --fullchain-file /etc/nginx/ssl/hia.crt \
  --reloadcmd      "systemctl reload nginx"
```

## 5. 换成 HTTPS 反代到 8502(带 WebSocket 头 + 大上传 + 长超时)
```bash
cat > /etc/nginx/conf.d/hia.conf <<'EOF'
server {
    listen 80;
    server_name hia.tjhealthycitylab.com;
    location /.well-known/acme-challenge/ { root /var/www/acme; }
    location / { return 301 https://$host$request_uri; }
}
server {
    listen 443 ssl;
    server_name hia.tjhealthycitylab.com;
    ssl_certificate     /etc/nginx/ssl/hia.crt;
    ssl_certificate_key /etc/nginx/ssl/hia.key;
    client_max_body_size 30m;          # 允许上传较大政策文档
    location / {
        proxy_pass http://127.0.0.1:8502;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;       # NiceGUI 依赖 WebSocket
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;        # AI 分析 30–60s,加长避免被切断
    }
}
EOF
nginx -t && systemctl reload nginx
```

## 6. 可能要做的一步(SELinux)
AL3 默认开 SELinux,可能拦 Nginx 反代本地端口;若 502,执行:
```bash
setsebool -P httpd_can_network_connect 1 && systemctl reload nginx
```

## 7. 验证 + 收尾
- 浏览器开 `https://hia.tjhealthycitylab.com` → 绿锁 + 口令门。
- 上 HTTPS 后,**8502 不必再对公网开放**:把安全组里 8502 那条规则删掉(只留 80/443),应用仍在本机被 Nginx 反代,更安全。
- 专家评审链接改发 `https://hia.tjhealthycitylab.com/review/<案例码>`。
