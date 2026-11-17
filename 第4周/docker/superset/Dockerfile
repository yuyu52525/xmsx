# ============================================================================
# Superset 镜像（在官方 4.1.2 之上补两件事）
#   1) Hive / MySQL 驱动：官方镜像不带 pyhive，连不上 HiveServer2
#   2) superset_config.py：元数据库、密钥、超时、跨源连接限制、Hive 目录兼容补丁
# 构建：docker compose build superset
# ============================================================================
FROM apache/superset:4.1.2

USER root

# 国内网络下 pypi 直连很慢，换清华源；--root-user-action 抑制 pip 的 root 警告
RUN pip install --no-cache-dir --root-user-action=ignore \
        -i https://pypi.tuna.tsinghua.edu.cn/simple \
        --trusted-host pypi.tuna.tsinghua.edu.cn \
        pyhive==0.7.0 \
        thrift==0.16.0 \
        thrift_sasl==0.4.3 \
        pure-sasl==0.6.2 \
        PyMySQL==1.1.1

# 配置文件：Superset 通过 SUPERSET_CONFIG_PATH 读取
COPY superset_config.py /app/pythonpath/superset_config.py
# 启动期辅助脚本（都幂等，失败不会阻塞 gunicorn 之外的正常启动）
COPY create_admin.py /app/create_admin.py
COPY bootstrap.py /app/bootstrap.py
COPY check_superset.py /app/check_superset.py
ENV SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py

USER superset

# run-server.sh 是镜像自带的 gunicorn 启动脚本（端口由 SUPERSET_PORT 控制）
CMD ["/usr/bin/run-server.sh"]