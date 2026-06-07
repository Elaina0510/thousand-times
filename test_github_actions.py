"""模拟 GitHub Actions 环境测试脚本。"""

from __future__ import annotations

import os
import sys
import io
import traceback

# 设置标准输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def test_imports() -> bool:
    """测试所有模块导入。"""
    print("=" * 50)
    print("测试模块导入...")
    print("=" * 50)

    modules = [
        "config",
        "utils",
        "scoring",
        "technical_analysis",
        "fundamental_analysis",
        "stock_filter",
        "etf_analyzer",
        "news_analysis",
        "report_generator",
        "chart_generator",
        "push_service",
        "main",
    ]

    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except Exception as e:
            print(f"  ❌ {module}: {e}")
            traceback.print_exc()
            all_ok = False

    return all_ok


def test_config_loading() -> bool:
    """测试配置加载。"""
    print()
    print("=" * 50)
    print("测试配置加载...")
    print("=" * 50)

    try:
        from config import load_config
        config = load_config()
        print(f"  ✅ 配置加载成功")
        print(f"     - LLM API URL: {config.llm_api_url[:30] if config.llm_api_url else '未设置'}...")
        print(f"     - LLM API Key: {'已设置' if config.llm_api_key else '未设置'}")
        return True
    except Exception as e:
        print(f"  ❌ 配置加载失败: {e}")
        traceback.print_exc()
        return False


def test_stock_filter() -> bool:
    """测试股票池筛选（不实际调用 API）。"""
    print()
    print("=" * 50)
    print("测试股票池筛选模块...")
    print("=" * 50)

    try:
        from stock_filter import get_stock_pool
        from config import FilterConfig
        print(f"  ✅ 股票池筛选模块导入成功")
        return True
    except Exception as e:
        print(f"  ❌ 股票池筛选模块导入失败: {e}")
        traceback.print_exc()
        return False


def test_technical_analysis() -> bool:
    """测试技术分析模块。"""
    print()
    print("=" * 50)
    print("测试技术分析模块...")
    print("=" * 50)

    try:
        from technical_analysis import get_kline_data, calc_technical_signals
        print(f"  ✅ 技术分析模块导入成功")
        return True
    except Exception as e:
        print(f"  ❌ 技术分析模块导入失败: {e}")
        traceback.print_exc()
        return False


def main() -> None:
    """主测试函数。"""
    print()
    print("=" * 60)
    print("GitHub Actions 环境模拟测试")
    print("=" * 60)
    print()

    # 检查环境变量
    print("环境变量检查:")
    print(f"  PUSHPLUS_TOKEN: {'已设置' if os.environ.get('PUSHPLUS_TOKEN') else '未设置'}")
    print(f"  LLM_API_URL: {'已设置' if os.environ.get('LLM_API_URL') else '未设置'}")
    print(f"  LLM_API_KEY: {'已设置' if os.environ.get('LLM_API_KEY') else '未设置'}")
    print()

    # 运行测试
    results = []
    results.append(("模块导入", test_imports()))
    results.append(("配置加载", test_config_loading()))
    results.append(("股票池筛选", test_stock_filter()))
    results.append(("技术分析", test_technical_analysis()))

    # 打印总结
    print()
    print("=" * 60)
    print("测试总结")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败，请检查上述错误。")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
