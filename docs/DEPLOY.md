# 部署指南(健康影响评估智能初筛系统 · NiceGUI)

> NiceGUI 是**常驻服务**(FastAPI/uvicorn + WebSocket),不能像 Streamlit Cloud 那样 serverless 托管,
> 需要一台**常开的服务器**。专家组协同要求**专家能访问到同一服务器**,所以必须部署到内网或公网。

## 选址建议

面向卫健委、专家多在国内 → **优先国内云主机(阿里云 / 腾讯云 ECS,2 核 4G 起步即可)**;
访问、备案合规、延迟都更好。国际平台(Render/Railway/Fly.io)部署更省事但国内访问可能慢/不稳。

| 方案 | 适合 | 备注 |
|---|---|---|
| **国内云主机 ECS + Docker/systemd + Nginx(HTTPS)** | 正式交付(推荐) | 数据留本机、可控、需备案绑域名 |
| Docker 跑在任意服务器 | 快速起 | 见下方 Docker 段 |
| 内网服务器 | 仅院内/委内访问 | 不出公网,最简单合规 |

## 必配环境变量(不放进代码/仓库)

| 变量 | 必填 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 是 | AI 初筛调用密钥 |
| `APP_PASSWORD` | 强烈建议 | 经办台(/、/panel)访问口令;不配则**任何人可用**(会刷你的 API) |
| `STORAGE_SECRET` | 建议 | 会话签名密钥,随便设一长串随机值 |
| `PORT` | 否 | 监听端口,默认 8080(容器)/8502(本地) |

> 专家评审页 `/review/<案例码>` 用**案例口令**进入,不受 `APP_PASSWORD` 限制(专家不是委内人员)。

## 方式一:Docker(最简单)

```bash
git clone https://github.com/swyhns-ship-it/hia-screening.git
cd hia-screening
docker build -t hia-screening .
docker run -d --name hia -p 8080:8080 \
  -e DEEPSEEK_API_KEY="sk-..." \
  -e APP_PASSWORD="设一个口令" \
  -e STORAGE_SECRET="$(openssl rand -hex 16)" \
  -v $(pwd)/cases:/app/cases -v $(pwd)/feedback:/app/feedback \
  hia-screening
```
`-v` 把案例/反馈挂到宿主机,容器重建也不丢。

## 方式二:直接跑(venv + systemd 常驻)

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
# /etc/systemd/system/hia.service 里设好 Environment= 的上述变量,ExecStart 指向:
#   .venv/bin/python app_nicegui.py
sudo systemctl enable --now hia
```

## Nginx 反代 + HTTPS(口令明文传输,务必上 HTTPS)

NiceGUI 用 WebSocket,Nginx 必须转发 Upgrade 头:
```nginx
server {
    listen 443 ssl;
    server_name your.domain;
    ssl_certificate     /path/fullchain.pem;
    ssl_certificate_key /path/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 上线后

- 经办把 `https://你的域名/review/<案例码>` + 口令发给专家。
- 数据持久化在 `cases/`、`feedback/`,定期备份(尤其云端容器重建会丢未挂载的数据)。
- 测试用过的 DeepSeek key 记得轮换;正式 key 只放服务器环境变量。
- 访问量大/多进程:NiceGUI 单进程即可支撑中小并发;如需扩展再议(NiceGUI 多 worker 需配 storage 后端)。
