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


def _is_v2_report(text: str) -> bool:
    """检测是否为 V2 Markdown 报告格式."""
    return bool(re.search(r'^##\s+(?:↔️|🐂|🐻)\s*市场环境', text, re.MULTILINE))


def _build_html(report_text: str, charts: dict[str, str], report_date: str) -> str:
    """构建HTML页面（自动检测 V1/V2 格式）。"""
    if _is_v2_report(report_text):
        return _build_v2_html(report_text, charts, report_date)
    return _build_v1_html(report_text, charts, report_date)


def _build_v1_html(report_text: str, charts: dict[str, str], report_date: str) -> str:
    """构建 V1 格式 HTML 页面（旧格式兼容）。"""
    signal_blocks = _parse_signal_blocks(report_text)
    news_section = _parse_news_section(report_text)
    signals_html = _build_signals_html(signal_blocks, charts)
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


def _build_v2_html(report_text: str, charts: dict[str, str], report_date: str) -> str:
    """构建 V2 格式 HTML 页面。"""
    sections = _parse_v2_report(report_text)

    # 市场环境
    env_html = _build_market_env_html(sections.get("market_env", {}))

    # 信号区
    signals_html = _build_v2_signals_html(sections.get("signals", []), charts)

    # 排行表
    ranking_html = _build_ranking_html(sections.get("ranking", {}), charts)

    # Top 3
    top3_html = _build_top3_html(sections.get("top3", []))

    # 统计
    stats_html = _build_stats_html(sections.get("stats", {}))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A股每日分析报告 — {report_date}</title>
    <style>
        {_get_css()}
        {_get_v2_css()}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 A股每日分析报告</h1>
            <p class="date">{report_date}</p>
        </header>
        <main>
            {env_html}
            {signals_html}
            {ranking_html}
            {top3_html}
            {stats_html}
        </main>
        <footer>
            <p>⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。</p>
            <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </footer>
    </div>
</body>
</html>"""


def _parse_v2_report(text: str) -> dict:
    """解析 V2 Markdown 报告为结构化数据."""
    sections: dict = {
        "market_env": {},
        "signals": [],
        "ranking": {"top": [], "bottom": []},
        "top3": [],
        "stats": {},
    }

    lines = text.split("\n")
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()

        # 市场环境
        if re.match(r'^##\s+(?:↔️|🐂|🐻)\s*市场环境', line):
            env, i = _parse_market_env(lines, i)
            sections["market_env"] = env
            continue

        # 买入/卖出信号
        m = re.match(r'^##\s+([🟢🔴])\s+(买入信号|卖出信号)', line)
        if m:
            emoji = m.group(1)
            sig_type = "buy" if "买入" in m.group(2) else "sell"
            stocks, i = _parse_signal_stocks(lines, i, sig_type)
            sections["signals"].append({
                "type": sig_type,
                "emoji": emoji,
                "stocks": stocks,
            })
            continue

        # 因子排行表
        if line.startswith("## 📈 因子评分排行"):
            ranking, i = _parse_ranking_table(lines, i)
            sections["ranking"] = ranking
            continue

        # Top 3 详细分析
        if line.startswith("## ⭐ Top 3 详细分析"):
            top3, i = _parse_top3(lines, i)
            sections["top3"] = top3
            continue

        # 因子分布统计
        if line.startswith("## 📊 因子分布统计"):
            stats, i = _parse_stats(lines, i)
            sections["stats"] = stats
            continue

        i += 1

    return sections


def _parse_market_env(lines: list[str], start: int) -> tuple[dict, int]:
    """解析市场环境块."""
    env: dict = {"state": "unknown", "emoji": "❓", "details": []}
    i = start

    # 标题行
    m = re.match(r'^##\s+((?:↔️|🐂|🐻))\s*市场环境:\s*(.+)$', lines[i].strip())
    if m:
        env["emoji"] = m.group(1)
        env["state"] = m.group(2)

    i += 1
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("## ") or line.startswith("# "):
            break
        if line.startswith("- "):
            env["details"].append(line[2:])
        i += 1

    return env, i


def _parse_signal_stocks(lines: list[str], start: int, sig_type: str) -> tuple[list[dict], int]:
    """解析信号下的股票列表."""
    stocks: list[dict] = []
    i = start + 1

    while i < len(lines):
        line = lines[i].strip()

        # 检测下一个 section 标题
        if re.match(r'^##\s+', line) or line.startswith("# "):
            break

        # 匹配股票条目: ### 名称 (代码) — 置信度 X%
        m = re.match(r'^###\s+(.+?)\s*\((\d{6})\)\s*—\s*置信度\s*([\d.]+)%', line)
        if m:
            stock_name = m.group(1).strip()
            code = m.group(2)
            confidence = m.group(3)
            detail_lines: list[str] = []

            # 收集详情行
            i += 1
            while i < len(lines):
                detail = lines[i].strip()
                if not detail:
                    i += 1
                    continue
                if re.match(r'^###\s+', detail) or re.match(r'^##\s+', detail) or detail.startswith("# "):
                    break
                if detail.startswith("- "):
                    detail_lines.append(detail[2:])
                i += 1

            stocks.append({
                "code": code,
                "name": stock_name,
                "confidence": confidence,
                "details": detail_lines,
            })
            continue

        i += 1

    return stocks, i


def _parse_ranking_table(lines: list[str], start: int) -> tuple[dict, int]:
    """解析因子排行表（Top 10 + Bottom 5）."""
    result: dict = {"top": [], "bottom": []}
    i = start + 1
    in_bottom = False
    table_lines: list[str] = []
    bottom_lines: list[str] = []

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("## ") and "因子排行" not in line and "评分最低" not in line:
            break

        if "评分最低" in line:
            in_bottom = True
            i += 1
            continue

        if line.startswith("|") and "排名" in line:
            # 表头，跳过
            i += 1
            continue
        if line.startswith("|---"):
            i += 1
            continue

        if line.startswith("|") and re.search(r'\d+', line):
            if in_bottom:
                bottom_lines.append(line)
            else:
                table_lines.append(line)

        i += 1

    # 解析排行行
    for tline in table_lines:
        cells = [c.strip() for c in tline.split("|")[1:-1]]
        if len(cells) >= 8:
            name_code = cells[1]
            mc = re.search(r'\((\d{6})\)', name_code)
            result["top"].append({
                "rank": cells[0],
                "name": name_code.split("(")[0].strip() if "(" in name_code else name_code,
                "code": mc.group(1) if mc else "",
                "total": cells[2],
                "technical": cells[3],
                "fundamental": cells[4],
                "capital": cells[5],
                "sentiment": cells[6],
                "momentum": cells[7],
                "percentile": cells[8] if len(cells) > 8 else "",
            })

    for tline in bottom_lines:
        cells = [c.strip() for c in tline.split("|")[1:-1]]
        if len(cells) >= 7:
            name_code = cells[1]
            mc = re.search(r'\((\d{6})\)', name_code)
            result["bottom"].append({
                "rank": cells[0],
                "name": name_code.split("(")[0].strip() if "(" in name_code else name_code,
                "code": mc.group(1) if mc else "",
                "total": cells[2],
                "technical": cells[3],
                "fundamental": cells[4],
                "capital": cells[5],
                "sentiment": cells[6],
                "momentum": cells[7] if len(cells) > 7 else "",
            })

    return result, i


def _parse_top3(lines: list[str], start: int) -> tuple[list[dict], int]:
    """解析 Top 3 详细分析."""
    top3: list[dict] = []
    i = start + 1
    current: dict | None = None

    while i < len(lines):
        line = lines[i].strip()

        if re.match(r'^##\s+', line) and "Top 3" not in line:
            break

        m = re.match(r'^###\s+(\d+)\.\s*(.+?)\s*\((\d{6})\)\s*—\s*综合分\s*([\d.]+)', line)
        if m:
            if current:
                top3.append(current)
            current = {
                "rank": m.group(1),
                "name": m.group(2).strip(),
                "code": m.group(3),
                "total": m.group(4),
                "details": [],
            }
        elif current is not None and line.startswith("- "):
            current["details"].append(line[2:])

        i += 1

    if current:
        top3.append(current)

    return top3, i


def _parse_stats(lines: list[str], start: int) -> tuple[dict, int]:
    """解析因子分布统计."""
    stats: dict = {"items": [], "factor_avgs": {}}
    i = start + 1

    while i < len(lines):
        line = lines[i].strip()

        if re.match(r'^##\s+', line) or line.startswith("# "):
            break

        if line.startswith("- "):
            stats["items"].append(line[2:])
        elif line.startswith("|") and "技术面" in line:
            # 因子平均分表头
            i += 1  # 跳过分隔线
            i += 1  # 数据行
            if i < len(lines):
                cells = [c.strip() for c in lines[i].split("|")[1:-1]]
                if len(cells) >= 5:
                    stats["factor_avgs"] = {
                        "技术面": cells[0], "基本面": cells[1],
                        "资金面": cells[2], "情绪面": cells[3], "动量": cells[4],
                    }
        i += 1

    return stats, i


def _build_market_env_html(env: dict) -> str:
    """构建市场环境HTML."""
    if not env:
        return ""
    parts: list[str] = []
    emoji = env.get("emoji", "❓")
    state = env.get("state", "未知")
    parts.append('<div class="market-env">')
    parts.append(f'<h2>{emoji} 市场环境: {state}</h2>')
    for detail in env.get("details", []):
        parts.append(f'<p class="env-detail">{detail}</p>')
    parts.append('</div>')
    return "\n".join(parts)


def _build_v2_signals_html(signals: list[dict], charts: dict[str, str]) -> str:
    """构建 V2 信号 HTML."""
    if not signals:
        return '<section class="signals-section"><p class="no-data">暂无信号数据</p></section>'

    parts: list[str] = ['<section class="signals-section">']

    for sig in signals:
        sig_type = sig.get("type", "")
        emoji = sig.get("emoji", "")
        stocks = sig.get("stocks", [])
        type_label = "买入信号" if sig_type == "buy" else "卖出信号"
        css_class = "buy-zone" if sig_type == "buy" else "sell-zone"

        if not stocks:
            parts.append(f'<h2 class="{css_class}">{emoji} {type_label}: 无</h2>')
            continue

        parts.append(f'<h2 class="{css_class}">{emoji} {type_label} ({len(stocks)} 只)</h2>')

        for stock in stocks:
            code = stock.get("code", "")
            name = stock.get("name", "")
            confidence = stock.get("confidence", "")
            details = stock.get("details", [])

            parts.append('<div class="stock-item">')
            parts.append('<div class="stock-header">')
            parts.append(f'<span class="stock-name">{name}</span>')
            parts.append(f'<span class="stock-code">({code})</span>')
            parts.append(f'<span class="stock-confidence">置信度 {confidence}%</span>')
            parts.append('</div>')

            if details:
                parts.append('<div class="stock-details">')
                for d in details:
                    parts.append(f'<div class="detail-line">{_escape_html(d)}</div>')
                parts.append('</div>')

            # 图表
            if code and code in charts:
                parts.append('<div class="chart-container">')
                parts.append(f'<img src="{charts[code]}" alt="{code} K线图" loading="lazy">')
                parts.append('</div>')

            parts.append('</div>')

    parts.append('</section>')
    return "\n".join(parts)


def _build_ranking_html(ranking: dict, charts: dict[str, str]) -> str:
    """构建排行表 HTML."""
    top = ranking.get("top", [])
    bottom = ranking.get("bottom", [])

    if not top and not bottom:
        return ""

    parts: list[str] = ['<section class="ranking-section">']
    parts.append('<h2>📈 因子评分排行</h2>')

    # Top 10 表格
    if top:
        parts.append('<table class="ranking-table">')
        parts.append('<thead><tr>'
                     '<th>排名</th><th>股票</th><th>综合分</th>'
                     '<th>技术</th><th>基本面</th><th>资金</th><th>情绪</th><th>动量</th>'
                     '<th>百分位</th>'
                     '</tr></thead><tbody>')
        for row in top:
            name = row.get("name", "")
            code = row.get("code", "")
            parts.append('<tr>')
            parts.append(f'<td>{row.get("rank", "")}</td>')
            parts.append(f'<td>{name} ({code})</td>')
            parts.append(f'<td class="score-total">{row.get("total", "")}</td>')
            parts.append(f'<td>{row.get("technical", "")}</td>')
            parts.append(f'<td>{row.get("fundamental", "")}</td>')
            parts.append(f'<td>{row.get("capital", "")}</td>')
            parts.append(f'<td>{row.get("sentiment", "")}</td>')
            parts.append(f'<td>{row.get("momentum", "")}</td>')
            parts.append(f'<td>{row.get("percentile", "")}</td>')
            parts.append('</tr>')
        parts.append('</tbody></table>')

    # Bottom 5 表格
    if bottom:
        parts.append('<h3>⚠️ 评分最低的 5 只</h3>')
        parts.append('<table class="ranking-table bottom-table">')
        parts.append('<thead><tr>'
                     '<th>排名</th><th>股票</th><th>综合分</th>'
                     '<th>技术</th><th>基本面</th><th>资金</th><th>情绪</th><th>动量</th>'
                     '</tr></thead><tbody>')
        for row in bottom:
            name = row.get("name", "")
            code = row.get("code", "")
            parts.append('<tr>')
            parts.append(f'<td>{row.get("rank", "")}</td>')
            parts.append(f'<td>{name} ({code})</td>')
            parts.append(f'<td class="score-total">{row.get("total", "")}</td>')
            parts.append(f'<td>{row.get("technical", "")}</td>')
            parts.append(f'<td>{row.get("fundamental", "")}</td>')
            parts.append(f'<td>{row.get("capital", "")}</td>')
            parts.append(f'<td>{row.get("sentiment", "")}</td>')
            parts.append(f'<td>{row.get("momentum", "")}</td>')
            parts.append('</tr>')
        parts.append('</tbody></table>')

    parts.append('</section>')
    return "\n".join(parts)


def _build_top3_html(top3: list[dict]) -> str:
    """构建 Top 3 详细分析 HTML."""
    if not top3:
        return ""

    parts: list[str] = ['<section class="top3-section">']
    parts.append('<h2>⭐ Top 3 详细分析</h2>')

    for item in top3:
        name = item.get("name", "")
        code = item.get("code", "")
        total = item.get("total", "")
        rank = item.get("rank", "")
        details = item.get("details", [])

        parts.append('<div class="stock-item">')
        parts.append(f'<h3>{rank}. {name} ({code}) — 综合分 {total}</h3>')
        if details:
            parts.append('<div class="stock-details">')
            for d in details:
                parts.append(f'<div class="detail-line">{_escape_html(d)}</div>')
            parts.append('</div>')
        parts.append('</div>')

    parts.append('</section>')
    return "\n".join(parts)


def _build_stats_html(stats: dict) -> str:
    """构建统计 HTML."""
    items = stats.get("items", [])
    factor_avgs = stats.get("factor_avgs", {})

    if not items and not factor_avgs:
        return ""

    parts: list[str] = ['<section class="stats-section">']
    parts.append('<h2>📊 因子分布统计</h2>')

    if items:
        parts.append('<ul class="stats-list">')
        for item in items:
            parts.append(f'<li>{item}</li>')
        parts.append('</ul>')

    if factor_avgs:
        parts.append('<h3>各因子类别平均分</h3>')
        parts.append('<table class="stats-table">')
        parts.append('<thead><tr><th>技术面</th><th>基本面</th><th>资金面</th><th>情绪面</th><th>动量</th></tr></thead>')
        parts.append('<tbody><tr>')
        for key in ["技术面", "基本面", "资金面", "情绪面", "动量"]:
            parts.append(f'<td>{factor_avgs.get(key, "")}</td>')
        parts.append('</tr></tbody></table>')

    parts.append('</section>')
    return "\n".join(parts)


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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

        html_parts.append('<div class="zone-block">')
        html_parts.append(f'<h2 class="{zone_class}">{emoji} {zone_name}</h2>')

        # 遍历该区域下的股票
        for stock in block["stocks"]:
            code = stock["code"]
            content = stock["content"]

            # 解析股票内容
            stock_html = _format_stock_item(content)

            html_parts.append('<div class="stock-item">')
            html_parts.append(f'<div class="stock-info">{stock_html}</div>')

            # 如果有对应图表，添加图表
            if code and code in charts:
                html_parts.append('<div class="chart-container">')
                html_parts.append(f'<img src="{charts[code]}" alt="{code} K线图" loading="lazy">')
                html_parts.append('</div>')

            html_parts.append('</div>')

        html_parts.append('</div>')

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


def _get_v2_css() -> str:
    """V2 报告专用 CSS 样式。"""
    return """
        .market-env {
            background: var(--card-bg);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 25px;
            border: 1px solid var(--border-color);
        }

        .market-env h2 {
            font-size: 1.3em;
            margin-bottom: 10px;
            border-bottom: none;
        }

        .env-detail {
            color: var(--text-secondary);
            font-size: 0.9em;
            margin: 3px 0;
        }

        .stock-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }

        .stock-name {
            font-weight: bold;
            font-size: 1.05em;
        }

        .stock-code {
            color: var(--text-secondary);
            font-size: 0.9em;
        }

        .stock-confidence {
            background: var(--accent-green);
            color: #000;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
        }

        .stock-details {
            font-size: 0.9em;
            line-height: 1.7;
            color: var(--text-secondary);
        }

        .detail-line {
            padding: 1px 0;
        }

        .ranking-section h2,
        .top3-section h2,
        .stats-section h2 {
            margin-bottom: 15px;
        }

        .ranking-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            font-size: 0.9em;
        }

        .ranking-table th,
        .ranking-table td {
            padding: 8px 6px;
            text-align: center;
            border-bottom: 1px solid var(--border-color);
        }

        .ranking-table th {
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 0.85em;
        }

        .ranking-table td:first-child {
            font-weight: bold;
        }

        .score-total {
            color: var(--accent-green);
            font-weight: bold;
        }

        .bottom-table .score-total {
            color: var(--accent-red);
        }

        .bottom-table {
            margin-top: 5px;
        }

        .stats-list {
            list-style: none;
            background: var(--card-bg);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            margin-bottom: 15px;
        }

        .stats-list li {
            padding: 3px 0;
            font-size: 0.9em;
        }

        .stats-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 8px;
            font-size: 0.9em;
        }

        .stats-table th,
        .stats-table td {
            padding: 8px 10px;
            text-align: center;
            border-bottom: 1px solid var(--border-color);
        }

        .stats-table th {
            color: var(--text-secondary);
            font-weight: 600;
        }

        .top3-section .stock-item h3 {
            font-size: 1.05em;
            margin-bottom: 8px;
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
