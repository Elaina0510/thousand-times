"""HTML报告生成模块 — 生成包含图表的静态网页报告。"""

from __future__ import annotations

import base64
import logging
import os
import re
from datetime import datetime

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

    # 收集图表文件（只收集报告中涉及的股票/ETF）
    charts = _collect_charts_for_report(report_text, chart_dir)

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


def _collect_charts_for_report(report_text: str, chart_dir: str) -> dict[str, str]:
    """从报告中提取股票/ETF代码，并收集对应的图表。

    Args:
        report_text: 报告文本。
        chart_dir: 图表目录。

    Returns:
        {代码: base64数据} 映射。
    """
    charts: dict[str, str] = {}

    if not os.path.exists(chart_dir):
        return charts

    # 从报告中提取所有股票/ETF代码（格式如：600519、510300等）
    code_pattern = r'\((\d{6})\)'
    codes_in_report = set(re.findall(code_pattern, report_text))

    # 只收集报告中涉及的图表
    for code in codes_in_report:
        filepath = os.path.join(chart_dir, f"{code}.png")
        if os.path.exists(filepath):
            charts[code] = _image_to_base64(filepath)

    logger.info(f"收集到 {len(charts)} 个图表（报告中涉及 {len(codes_in_report)} 个代码）")
    return charts


def _build_html(report_text: str, charts: dict[str, str], report_date: str) -> str:
    """构建HTML页面。"""
    # 解析报告为各个信号块
    signal_blocks = _parse_signal_blocks(report_text)
    news_section = _parse_news_section(report_text)

    # 构建信号HTML
    signals_html = _build_signals_html(signal_blocks, charts)

    # 构建新闻HTML
    news_html = _build_news_html(news_section)

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
                {signals_html}
            </section>

            <section class="news-section">
                <h2>📰 今日政策要闻</h2>
                {news_section if news_html else '<p class="no-data">暂无新闻数据</p>'}
            </section>
        </main>

        <footer>
            <p>⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。</p>
            <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </footer>
    </div>
</body>
</html>"""


def _parse_signal_blocks(report_text: str) -> list[dict]:
    """解析报告为信号块列表。

    每个信号块包含：区域标题、股票信息、图表代码。

    Returns:
        [{"zone": "买入区", "emoji": "🟢", "stocks": [{"code": "600519", "content": "..."}]}]
    """
    blocks: list[dict] = []
    current_block: dict | None = None

    # 匹配区域标题：🟢 买入区、🟡 观望区、🔴 卖出区
    zone_pattern = r'^([🟢🟡🔴])\s+(买入区|观望区|卖出区)'
    # 匹配股票代码：(600519)
    code_pattern = r'\((\d{6})\)'
    # 匹配分隔线
    separator_pattern = r'^━+$'

    for line in report_text.split('\n'):
        line = line.strip()

        if not line:
            continue

        # 检测分隔线
        if re.match(separator_pattern, line):
            continue

        # 检测区域标题
        zone_match = re.match(zone_pattern, line)
        if zone_match:
            emoji, zone_name = zone_match.groups()
            current_block = {
                "zone": zone_name,
                "emoji": emoji,
                "stocks": [],
            }
            blocks.append(current_block)
            continue

        # 检测股票/ETF条目
        if line.startswith('【') and current_block is not None:
            code_match = re.search(code_pattern, line)
            code = code_match.group(1) if code_match else ""

            current_block["stocks"].append({
                "code": code,
                "content": line,
            })

    return blocks


def _parse_news_section(report_text: str) -> str:
    """提取新闻部分。"""
    if '📰' not in report_text:
        return ""

    # 找到新闻部分的开始
    lines = report_text.split('\n')
    news_start = -1
    for i, line in enumerate(lines):
        if '📰' in line or '政策要闻' in line:
            news_start = i
            break

    if news_start == -1:
        return ""

    # 提取新闻内容（到免责声明之前）
    news_lines = []
    for line in lines[news_start:]:
        if '⚠️' in line and '以上分析仅供参考' in line:
            break
        if '━━━' in line and news_lines:  # 避免开头的分隔线
            break
        news_lines.append(line)

    return '\n'.join(news_lines)


def _build_signals_html(blocks: list[dict], charts: dict[str, str]) -> str:
    """构建信号HTML，每个股票下方附带对应图表。"""
    if not blocks:
        return '<p class="no-data">暂无信号数据</p>'

    html_parts: list[str] = []

    for block in blocks:
        zone_name = block["zone"]
        emoji = block["emoji"]

        # 区域标题
        zone_class = {
            "买入区": "buy-zone",
            "观望区": "watch-zone",
            "卖出区": "sell-zone",
        }.get(zone_name, "")

        html_parts.append(f'<div class="zone-block">')
        html_parts.append(f'<h2 class="{zone_class}">{emoji} {zone_name}</h2>')

        # 遍历该区域下的股票
        for stock in block["stocks"]:
            code = stock["code"]
            content = stock["content"]

            # 解析股票内容
            stock_html = _format_stock_item(content)

            html_parts.append(f'<div class="stock-item">')
            html_parts.append(f'<div class="stock-info">{stock_html}</div>')

            # 如果有对应图表，添加图表
            if code and code in charts:
                html_parts.append(f'<div class="chart-container">')
                html_parts.append(f'<img src="{charts[code]}" alt="{code} K线图" loading="lazy">')
                html_parts.append(f'</div>')

            html_parts.append(f'</div>')

        html_parts.append(f'</div>')

    return '\n'.join(html_parts)


def _format_stock_item(content: str) -> str:
    """格式化单个股票条目。"""
    # 将【1】格式转换为带样式的HTML
    content = re.sub(r'【(\d+)】', r'<span class="stock-index">【\1】</span>', content)

    # 转换链接
    content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', content)

    # 转换关键价位行
    content = content.replace('├', '<span class="separator">├</span>')
    content = content.replace('└', '<span class="separator">└</span>')

    # 转换信号区间emoji
    content = content.replace('🟢', '<span class="emoji-green">🟢</span>')
    content = content.replace('🟡', '<span class="emoji-yellow">🟡</span>')
    content = content.replace('🔴', '<span class="emoji-red">🔴</span>')

    # 用换行分隔各部分
    content = content.replace(' ├', '<br>├')
    content = content.replace(' └', '<br>└')

    return content


def _build_news_html(news_text: str) -> str:
    """构建新闻HTML。"""
    if not news_text.strip():
        return ""

    lines = news_text.strip().split("\n")
    items: list[str] = []

    for line in lines:
        line = line.strip()
        if not line or '📰' in line:
            continue

        # 提取链接
        link = ""
        link_pattern = r'\[详情\]\(([^)]+)\)'
        link_match = re.search(link_pattern, line)
        if link_match:
            link = link_match.group(1)
            line = re.sub(r'\s*\[详情\]\([^)]+\)', '', line)

        if line:
            link_html = f' <a href="{link}" target="_blank" class="news-link">🔗</a>' if link else ""
            items.append(f'<li>{line}{link_html}</li>')

    if items:
        return "<ul>" + "\n".join(items) + "</ul>"
    return ""


def _get_css() -> str:
    """获取CSS样式。"""
    return """
        :root {
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --text-color: #e6edf3;
            --text-secondary: #8b949e;
            --accent-green: #3fb950;
            --accent-yellow: #d29922;
            --accent-red: #f85149;
            --border-color: #30363d;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", "Microsoft YaHei", sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 30px;
        }

        header h1 {
            font-size: 1.8em;
            margin-bottom: 10px;
        }

        header .date {
            color: var(--text-secondary);
            font-size: 1.1em;
        }

        section {
            margin-bottom: 30px;
        }

        section h2 {
            font-size: 1.4em;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid var(--border-color);
        }

        .zone-block {
            margin-bottom: 25px;
        }

        .buy-zone { color: var(--accent-green); }
        .watch-zone { color: var(--accent-yellow); }
        .sell-zone { color: var(--accent-red); }

        .stock-item {
            background: var(--card-bg);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            border: 1px solid var(--border-color);
        }

        .stock-info {
            font-size: 0.95em;
            line-height: 1.8;
        }

        .stock-index {
            font-weight: bold;
            color: var(--text-color);
        }

        .separator {
            color: var(--text-secondary);
        }

        .emoji-green { color: var(--accent-green); }
        .emoji-yellow { color: var(--accent-yellow); }
        .emoji-red { color: var(--accent-red); }

        .chart-container {
            margin-top: 15px;
            text-align: center;
        }

        .chart-container img {
            max-width: 100%;
            height: auto;
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }

        .news-section ul {
            list-style: none;
            background: var(--card-bg);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }

        .news-section li {
            padding: 10px 0;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.95em;
        }

        .news-section li:last-child {
            border-bottom: none;
        }

        .news-link {
            color: var(--accent-yellow);
            text-decoration: none;
            font-size: 1.1em;
        }

        .news-link:hover {
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
            padding: 30px 0;
            border-top: 1px solid var(--border-color);
            margin-top: 30px;
            color: var(--text-secondary);
            font-size: 0.9em;
        }

        footer p {
            margin: 5px 0;
        }

        a {
            color: #58a6ff;
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        @media (max-width: 768px) {
            .container {
                padding: 15px;
            }

            header h1 {
                font-size: 1.4em;
            }
        }
    """


if __name__ == "__main__":
    # 测试用例
    test_report = """📊 A股每日分析报告 — 2026-06-14

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟢 买入区（综合评分 ≥ 70）

【1】贵州茅台 (600519) — 综合评分：80分
├ 技术信号：MA5/10金叉，MACD金叉
└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/600519/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟡 观望区（综合评分 30~70）

【1】比亚迪 (002594) — 综合评分：55分
├ 技术信号：无明显信号
└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/002594/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 卖出区（综合评分 < 30）

【1】浦发银行 (600000) — 综合评分：25分
├ 风险信号：MA5/10死叉
└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/600000/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📰 今日政策要闻

1. 央行宣布降准0.5个百分点 → 利好银行 [详情](https://example.com/news1)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。"""

    output = generate_html_report(test_report, chart_dir="charts", output_dir="public")
    print(f"生成完成: {output}")
