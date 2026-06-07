"""配置验证脚本 — 检查环境变量和依赖是否正确配置。"""

from __future__ import annotations

import os
import sys
import io

# 设置标准输出编码为 UTF-8（Windows 兼容）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


def check_config() -> bool:
    """检查配置是否完整。

    Returns:
        配置是否有效。
    """
    print("=" * 50)
    print("A股智能选股分析系统 - 配置检查")
    print("=" * 50)
    print()

    # 检查 Python 版本
    python_version = sys.version_info
    print(f"✅ Python 版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 10):
        print("   ⚠️  建议使用 Python 3.10+")
    print()

    # 检查依赖
    print("📦 依赖检查:")
    dependencies = [
        ("akshare", "AKShare"),
        ("pandas", "Pandas"),
        ("numpy", "NumPy"),
        ("mplfinance", "mplfinance"),
        ("matplotlib", "Matplotlib"),
        ("requests", "Requests"),
        ("bs4", "BeautifulSoup4"),
        ("dotenv", "python-dotenv"),
    ]

    all_deps_ok = True
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"  ✅ {name}")
        except ImportError:
            print(f"  ❌ {name} - 未安装")
            all_deps_ok = False
    print()

    # 检查环境变量
    print("🔧 环境变量检查:")

    pushplus_token = os.environ.get("PUSHPLUS_TOKEN", "")
    if pushplus_token:
        print("  ✅ PUSHPLUS_TOKEN: ***已设置***")
    else:
        print("  ❌ PUSHPLUS_TOKEN: 未设置")
        all_deps_ok = False

    llm_api_url = os.environ.get("LLM_API_URL", "")
    if llm_api_url:
        print(f"  ✅ LLM_API_URL: {llm_api_url}")
    else:
        print("  ⚠️  LLM_API_URL: 未设置（政策新闻分析将使用默认评分）")

    llm_api_key = os.environ.get("LLM_API_KEY", "")
    if llm_api_key:
        print("  ✅ LLM_API_KEY: ***已设置***")
    else:
        print("  ⚠️  LLM_API_KEY: 未设置（政策新闻分析将使用默认评分）")
    print()

    # 检查目录
    print("📁 目录检查:")
    directories = ["src", "tests", "charts", "logs", "doc"]
    for directory in directories:
        if os.path.exists(directory):
            print(f"  ✅ {directory}/")
        else:
            print(f"  ⚠️  {directory}/ - 不存在（将自动创建）")
    print()

    # 总结
    print("=" * 50)
    if all_deps_ok:
        print("✅ 配置检查通过！可以运行分析。")
        print()
        print("运行命令:")
        print("  python src/main.py")
    else:
        print("❌ 配置检查失败，请修复上述问题。")
    print("=" * 50)

    return all_deps_ok


if __name__ == "__main__":
    success = check_config()
    sys.exit(0 if success else 1)
