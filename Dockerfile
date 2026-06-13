# 健康影响评估智能初筛系统 — NiceGUI 容器化部署
FROM python:3.11-slim

WORKDIR /app

# 时区(日志/时间戳用本地时间)
ENV TZ=Asia/Shanghai

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 运行端口(可被平台的 PORT 环境变量覆盖)
ENV PORT=8080
EXPOSE 8080

# 持久化目录(案例/反馈)——部署时建议挂载卷到 /app/cases 与 /app/feedback
VOLUME ["/app/cases", "/app/feedback"]

CMD ["python", "app_nicegui.py"]
