"""幂等创建 Superset 管理员（容器启动时执行，已存在则跳过）

为什么不用 `superset fab create-admin`：
  它在 compose 的 `/bin/sh -c "..."` 里被拆参数时会退化成"交互模式"，
  容器日志里只看到 `Username [admin]:`，然后卡住/失败（实测踩过）。
  改成在 app context 里直接调 FAB 的 security manager，参数传递不依赖 shell 引号。
"""

from __future__ import annotations

import os
import sys

USERNAME = os.getenv("ADMIN_USERNAME", "admin")
PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
EMAIL = os.getenv("ADMIN_EMAIL", "admin@ydsh.local")


def main() -> int:
    from superset.app import create_app

    app = create_app()
    with app.app_context():
        sm = app.appbuilder.sm
        if sm.find_user(username=USERNAME):
            print(f"[create_admin] 管理员 {USERNAME} 已存在，跳过")
            return 0
        role = sm.find_role("Admin")
        if role is None:
            print("[create_admin] 找不到 Admin 角色，请先跑 superset init", file=sys.stderr)
            return 1
        sm.add_user(
            username=USERNAME,
            first_name="云购",
            last_name="生活",
            email=EMAIL,
            password=PASSWORD,
            role=role,
        )
        print(f"[create_admin] 已创建管理员 {USERNAME} / {EMAIL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())