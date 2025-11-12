"""
模块入口

允许使用 `python -m rss_note_writer` 运行命令行接口。
"""

import sys
from .cli import main


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n用户中断操作，程序退出")
        sys.exit(0)
    except Exception as e:
        print(f"程序启动错误: {e}")
        sys.exit(1)

