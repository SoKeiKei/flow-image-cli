#!/usr/bin/env python3
"""
Flow Token Receiver - 本地 Token 接收服务

用于接收 Chrome 插件发送的 session-token 并保存到 ~/.flow-cli/token.json

用法:
    python flow_token_server.py

默认监听: http://localhost:8765/token
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Token 文件路径
TOKEN_FILE = Path.home() / ".flow-cli" / "token.json"

# 确保目录存在
TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)


class TokenHandler(BaseHTTPRequestHandler):
    """处理 Token 接收请求"""

    def log_message(self, format, *args):
        """自定义日志输出"""
        print(f"[{self.log_date_time_string()}] {format % args}")

    def do_POST(self):
        """处理 POST 请求"""
        if self.path != "/token":
            self.send_error(404, "Not Found")
            return

        try:
            # 读取请求体
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            session_token = data.get("session_token")

            if not session_token:
                self.send_error(400, "Missing session_token")
                return

            # 读取现有 token 文件（保留其他字段）
            existing_data = {}
            if TOKEN_FILE.exists():
                try:
                    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    pass

            # 更新 session_token
            existing_data["st"] = session_token

            # 保存到文件
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)

            # 发送成功响应
            response = {
                "success": True,
                "message": f"Token 已保存到 {TOKEN_FILE}",
                "token_length": len(session_token)
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

            print(f"完成: Token 已更新 (长度: {len(session_token)})")

        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            self.send_error(500, str(e))
            print(f"错误: {e}")

    def do_GET(self):
        """处理 GET 请求 - 返回当前状态"""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return

        if self.path == "/token":
            # 返回当前 token 状态（不显示完整 token）
            response = {"has_token": False}

            if TOKEN_FILE.exists():
                try:
                    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("st"):
                            response["has_token"] = True
                            response["token_length"] = len(data["st"])
                except:
                    pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        self.send_error(404, "Not Found")


def main():
    """启动服务器"""
    host = "127.0.0.1"  # 使用 127.0.0.1 而非 localhost
    port = 8765

    # 检查端口是否被占用
    try:
        server = HTTPServer((host, port), TokenHandler)
    except OSError:
        print(f"端口 {port} 已被占用，尝试使用随机端口...")
        port = 0
        server = HTTPServer((host, port), TokenHandler)
        port = server.server_address[1]

    print(f"""
╔══════════════════════════════════════════════════════╗
║         Flow Token Receiver                          ║
╠══════════════════════════════════════════════════════╣
║  服务器地址: http://{host}:{port}/token              ║
║  Token 文件: {TOKEN_FILE}           ║
╠══════════════════════════════════════════════════════╣
║  在 Chrome 插件中配置以下地址:                         ║
║  http://{host}:{port}/token                       ║
╠══════════════════════════════════════════════════════╣
║  按 Ctrl+C 停止服务器                                 ║
╚══════════════════════════════════════════════════════╝
    """)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
