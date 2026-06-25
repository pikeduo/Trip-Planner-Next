"""运行时控制台日志捕获工具。

该模块把标准输出和标准错误包装成可同时写入控制台与日志文件的对象，
用于在服务运行时保留控制台日志，方便排查后端启动、接口调用或异步任务中的问题。
"""

import sys
from pathlib import Path
from typing import TextIO


class ConsoleLogWriter:
    """同时写入控制台和日志文件的文本输出包装器。

    Python 的 sys.stdout 和 sys.stderr 只要求对象实现 write/flush 等文件类方法。
    因此这里通过包装原始控制台流，在不改变业务代码 print/log 输出方式的前提下，
    将同一份输出复制一份到日志文件中。
    """

    def __init__(self, console: TextIO, log_file: TextIO) -> None:
        # console 保留原始终端输出，log_file 用于持久化保存运行日志。
        self.console = console
        self.log_file = log_file

    def write(self, message: str) -> int:
        """写入一段文本，同时输出到控制台和日志文件。

        控制台编码在不同操作系统或终端环境中可能不一致，遇到无法编码的字符时，
        使用 replace 策略转换成安全文本，避免日志输出因为 UnicodeEncodeError 中断服务。
        """
        try:
            self.console.write(message)
        except UnicodeEncodeError:
            safe_message = message.encode(self.console.encoding or "utf-8", errors="replace").decode(
                self.console.encoding or "utf-8",
                errors="replace",
            )
            self.console.write(safe_message)

        # 日志文件统一使用 UTF-8 打开，因此保留原始 message，便于后续排查中文或 emoji 输出。
        self.log_file.write(message)
        return len(message)

    def flush(self) -> None:
        """刷新控制台和日志文件缓冲区，确保输出及时落盘。"""
        self.console.flush()
        self.log_file.flush()

    def __getattr__(self, name: str):
        """把未显式实现的属性转发给原始控制台对象。

        这样可以最大程度模拟 sys.stdout/sys.stderr 的原有行为，
        避免第三方库访问 encoding、isatty 等属性时出现兼容性问题。
        """
        return getattr(self.console, name)


def install_console_log(log_path: Path) -> None:
    """安装控制台日志捕获器。

    参数:
        log_path: 运行日志文件路径。

    调用后，后续写入 sys.stdout 和 sys.stderr 的内容会同时出现在控制台与日志文件中。
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
    sys.stdout = ConsoleLogWriter(sys.stdout, log_file)
    sys.stderr = ConsoleLogWriter(sys.stderr, log_file)
