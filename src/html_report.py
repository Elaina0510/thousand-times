"""HTML报告生成模块 — 生成包含图表的静态网页报告。"""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("thousand-times")


def _image_to_base64(image_path: str) -> str:
    """将图片转换为base64编码。

    Args:
        image_path: 图片文件路径。

    Returns:
        base64编码的图片数据URI。
    """
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        base64_str = base64.b64encode(image_data).decode("utf-8")
        return f"data:image/png;base64,{base64_str}"
    except Exception as e:
        logger.warning(f"图片转base64失败 {image_path}: {e}")
        return ""


def generate_html_report(
    report_text: str,
    chart_dir: str = "charts",
    output_dir: str = "public",
    report_date: str | None = None,
) -> str:
    """生成HTML报告。

    Args:
        report_text: Markdown格式的报告文本。
        chart_dir: 图表目录。
        output_dir: 输出目录。
        report_date: 报告日期，默认今天。

    Returns:
        生成的HTML文件路径。
    """
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "archive"), exist_ok=True)

    # 收集图表文件
    charts: dict[str, str] = {}
    if os.path.exists(chart_dir):
        for filename in os.listdir(chart_dir):
            if filename.endswith(".png"):
                code = filename.replace(".png", "")
                filepath = os.path.join(chart_dir, filename)
                charts[code] = _image_to_base64(filepath)

    # 生成HTML内容
    html_content = _build_html(report_text, charts, report_date)

    # 写入文件
    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 同时保存到归档目录
    archive_path = os.path.join(output_dir, "archive", f"{report_date}.html")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"HTML报告已生成: {output_path}")
    return output_path


def _build_html(report_text: str, charts: dict[str, str], report_date: str) -> str:
    """构建HTML页面。

    Args:
        report_text: Markdown格式的报告文本。
        charts: 图表数据 {代码: base64数据}。
        report_date: 报告日期。

    Returns:
        HTML内容。
    """
    # 解析报告文本，提取各部分
    sections = _parse_report_sections(report_text)

    # 构建图表HTML
    charts_html = _build_charts_html(charts)

    # 构建新闻HTML
    news_html = _build_news_html(sections.get("news", ""))

    # 构建股票信号HTML
    signals_html = _build_signals_html(sections.get("signals", ""))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A股每日分析报告 — {report_date}</title>
    <style>
        {_get_css()}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 A股每日分析报告</h1>
            <p class="date">{report_date}</p>
        </header>

        <main>
            <section class="signals-section">
                <h2>📈 买卖信号</h2>
                {signals_html}
            </section>

            <section class="charts-section">
                <h2>📉 K线图表</h2>
                <div class="charts-grid">
                    {charts_html}
                </div>
            </section>

            <section class="news-section">
                <h2>📰 今日政策要闻</h2>
                {news_html}
            </section>
        </main>

        <footer>
            <p>⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。</p>
            <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </footer>
    </div>
</body>
</html>"""


def _parse_report_sections(report_text: str) -> dict[str, str]:
    """解析报告文本为各个部分。

    Args:
        report_text: 报告文本。

    Returns:
        各部分内容的字典。
    """
    sections: dict[str, str] = {
        "signals": "",
        "news": "",
    }

    lines = report_text.split("\n")
    current_section = "signals"
    signal_lines: list[str] = []
    news_lines: list[str] = []

    for line in lines:
        if "📰" in line or "政策要闻" in line:
            current_section = "news"
        elif "⚠️" in line and "以上分析仅供参考" in line:
            continue

        if current_section == "signals":
            signal_lines.append(line)
        elif current_section == "news":
            news_lines.append(line)

    sections["signals"] = "\n".join(signal_lines)
    sections["news"] = "\n".join(news_lines)

    return sections


def _build_charts_html(charts: dict[str, str]) -> str:
    """构建图表HTML。

    Args:
        charts: 图表数据。

    Returns:
        图表HTML。
    """
    if not charts:
        return '<p class="no-data">暂无图表数据</p>'

    html_parts: list[str] = []
    for code, data_uri in sorted(charts.items()):
        if data_uri:
            html_parts.append(f"""
            <div class="chart-card">
                <h3>{code}</h3>
                <img src="{data_uri}" alt="{code} K线图" loading="lazy">
            </div>
            """)

    return "\n".join(html_parts)


def _build_news_html(news_text: str) -> str:
    """构建新闻HTML。

    Args:
        news_text: 新闻文本。

    Returns:
        新闻HTML。
    """
    if not news_text.strip():
        return '<p class="no-data">暂无新闻数据</p>'

    lines = news_text.strip().split("\n")
    items: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 解析新闻行：序号. 标题 → 方向行业 [详情](链接)
        if ". " in line and "→" in line:
            # 提取链接
            link = ""
            if "[详情](" in line:
                start = line.find("[详情](") + 7
                end = line.find(")", start)
                if end > start:
                    link = line[start:end]
                    line = line[:line.find("[详情](")].strip()

            items.append(f'<li>{line}{f" <a href=\'{link}\' target=\'_blank\'>🔗</a>" if link else ""}</li>')
        elif line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            items.append(f"<li>{line}</li>")

    if items:
        return f"<ul>{''.join(items)}</ul>"
    return f"<pre>{news_text}</pre>"


def _build_signals_html(signals_text: str) -> str:
    """构建信号HTML。

    Args:
        signals_text: 信号文本。

    Returns:
        信号HTML。
    """
    if not signals_text.strip():
        return '<p class="no-data">暂无信号数据</p>'

    # 将Markdown转换为简单HTML
    html = signals_text

    # 转换标题
    html = html.replace("🟢 买入区", '<h3 class="buy-zone">🟢 买入区</h3>')
    html = html.replace("🟡 观望区", '<h3 class="watch-zone">🟡 观望区</h3>')
    html = html.replace("🔴 卖出区", '<h3 class="sell-zone">🔴 卖出区</h3>')

    # 转换分隔线
    html = html.replace("━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "<hr>")

    # 转换链接
    import re
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', html)

    # 转换换行
    html = html.replace("\n", "<br>")

    return f'<div class="signals-content">{html}</div>'


def _get_css() -> str:
    """获取CSS样式。

    Returns:
        CSS样式字符串。
    """
    return """
        :root {
            --bg-color: #1a1a2e;
            --card-bg: #16213e;
            --text-color: #eaeaea;
            --text-secondary: #a0a0a0;
            --accent-green: #00d253;
            --accent-yellow: #ffab00;
            --accent-red: #fc424a;
            --border-color: #2d3748;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            text-align: center;
            padding: 40px 0;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 40px;
        }

        header h1 {
            font-size: 2em;
            margin-bottom: 10px;
        }

        header .date {
            color: var(--text-secondary);
            font-size: 1.2em;
        }

        section {
            margin-bottom: 40px;
        }

        section h2 {
            font-size: 1.5em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--border-color);
        }

        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }

        .chart-card {
            background: var(--card-bg);
            border-radius: 8px;
            padding: 15px;
            border: 1px solid var(--border-color);
        }

        .chart-card h3 {
            margin-bottom: 10px;
            color: var(--text-secondary);
        }

        .chart-card img {
            width: 100%;
            height: auto;
            border-radius: 4px;
        }

        .signals-content {
            background: var(--card-bg);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }

        .buy-zone { color: var(--accent-green); margin: 15px 0 10px; }
        .watch-zone { color: var(--accent-yellow); margin: 15px 0 10px; }
        .sell-zone { color: var(--accent-red); margin: 15px 0 10px; }

        hr {
            border: none;
            border-top: 1px solid var(--border-color);
            margin: 15px 0;
        }

        .news-section ul {
            list-style: none;
            background: var(--card-bg);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }

        .news-section li {
            padding: 10px 0;
            border-bottom: 1px solid var(--border-color);
        }

        .news-section li:last-child {
            border-bottom: none;
        }

        .news-section a {
            color: var(--accent-yellow);
            text-decoration: none;
        }

        .news-section a:hover {
            text-decoration: underline;
        }

        .no-data {
            color: var(--text-secondary);
            text-align: center;
            padding: 40px;
            background: var(--card-bg);
            border-radius: 8px;
        }

        footer {
            text-align: center;
            padding: 40px 0;
            border-top: 1px solid var(--border-color);
            margin-top: 40px;
            color: var(--text-secondary);
        }

        footer p {
            margin: 5px 0;
        }

        @media (max-width: 768px) {
            .charts-grid {
                grid-template-columns: 1fr;
            }

            header h1 {
                font-size: 1.5em;
            }
        }
    """


if __name__ == "__main__":
    # 测试用例
    test_report = """📊 A股每日分析报告 — 2026-06-13

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟢 买入区（综合评分 ≥ 70）

【1】贵州茅台 (600519) — 综合评分：80分
├ 技术信号：MA5/10金叉，MACD金叉
└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/600519/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📰 今日政策要闻

1. 央行宣布降准0.5个百分点 → 利好银行、地产 [详情](https://example.com/news1)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。"""

    output = generate_html_report(test_report, chart_dir="charts", output_dir="public")
    print(f"生成完成: {output}")
