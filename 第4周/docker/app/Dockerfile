# ============================================================================
# Python 应用镜像：数据服务(API) + Streamlit 问答 共用同一个镜像
#   两个服务用不同 command 启动，避免维护两份依赖。
# 构建：docker compose build api
# ============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8

WORKDIR /app

# 先装依赖再拷代码，改代码不会让依赖层失效
COPY docker/app/requirements.txt /app/requirements.txt
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
        --trusted-host pypi.tuna.tsinghua.edu.cn \
        -r /app/requirements.txt

# 代码：py/ 与 web/ 都进镜像（api 服务要托管大屏静态文件）
COPY py /app/py
COPY web /app/web

WORKDIR /app/py
EXPOSE 8000 8501

# 默认起数据服务；streamlit 服务在 compose 里覆盖 command
CMD ["python", "api_server.py"]