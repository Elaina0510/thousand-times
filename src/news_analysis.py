"""政策新闻分析模块 — 抓取新闻、LLM分析政策影响。"""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import requests

logger = logging.getLogger("thousand-times")


@dataclass
class NewsItem:
    """单条新闻。"""

    title: str
    source: str  # 来源（新浪财经/东方财富/同花顺）
    url: str
    publish_time: datetime
    content: str


@dataclass
class PolicyImpact:
    """政策影响分析结果。"""

    news_title: str
    news_url: str = ""  # 新闻链接
    affected_industries: list[str] = None  # type: ignore[assignment]
    impact_direction: str = "neutral"  # "positive" / "negative" / "neutral"
    impact_degree: str = "indirect"  # "direct" / "indirect"
    impact_score: float = 5.0  # -20 ~ +20
    summary: str = ""

    def __post_init__(self) -> None:
        if self.affected_industries is None:
            self.affected_industries = []


# 可信来源白名单
CREDIBLE_SOURCES: set[str] = {
    "新浪财经",
    "东方财富",
    "同花顺",
    "证券时报",
    "上海证券报",
    "中国证券报",
    "央视财经",
    "人民日报",
    "新华社",
}


def fetch_news() -> list[NewsItem]:
    """从AKShare获取当日财经新闻。

    Returns:
        新闻列表，按时间倒序。
    """
    try:
        # 优先使用远程 API
        try:
            from remote_data import is_remote_available, get_news_remote
            if is_remote_available():
                logger.info("使用远程 API 获取新闻数据")
                df = get_news_remote()
            else:
                import akshare as ak  # type: ignore[import-untyped]
                df = ak.stock_news_em(symbol="财经")
        except Exception as e:
            logger.warning(f"远程 API 调用失败，回退到 AKShare: {e}")
            import akshare as ak  # type: ignore[import-untyped]
            df = ak.stock_news_em(symbol="财经")

        if df.empty:
            logger.warning("获取新闻数据为空")
            return []

        # 重命名列
        column_mapping = {
            "新闻标题": "title",
            "新闻内容": "content",
            "发布时间": "publish_time",
            "文章来源": "source",
            "新闻链接": "url",
        }
        existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=existing_columns)

        news_list: list[NewsItem] = []
        for _, row in df.iterrows():
            title = str(row.get("title", ""))
            content = str(row.get("content", ""))
            source = str(row.get("source", ""))
            url = str(row.get("url", ""))

            # 解析发布时间
            publish_time = datetime.now()
            if "publish_time" in row and pd.notna(row["publish_time"]):
                with contextlib.suppress(Exception):
                    publish_time = pd.to_datetime(row["publish_time"])

            if title:
                news_list.append(
                    NewsItem(
                        title=title,
                        source=source,
                        url=url,
                        publish_time=publish_time,
                        content=content,
                    )
                )

        logger.info(f"获取新闻 {len(news_list)} 条")
        return news_list

    except Exception as e:
        logger.warning(f"获取新闻失败: {e}")
        return []


def filter_by_credibility(news: list[NewsItem]) -> list[NewsItem]:
    """按可信度过滤新闻。

    可信度分级：
    - 高可信：政府官方发布（国务院、央行、证监会等）、三大证券报
    - 中可信：主流财经媒体（东方财富、同花顺、新浪财经）
    - 低可信：自媒体、论坛传闻 → 不纳入分析，直接过滤

    Args:
        news: 新闻列表。

    Returns:
        过滤后的新闻列表。
    """
    filtered: list[NewsItem] = []
    for item in news:
        # 检查来源是否在白名单中
        if any(source in item.source for source in CREDIBLE_SOURCES):
            filtered.append(item)
        elif not item.source:
            # 来源为空时保留（可能是AKShare数据源的问题）
            filtered.append(item)
        else:
            logger.debug(f"过滤低可信来源新闻: {item.source} - {item.title}")

    logger.info(f"可信度过滤后剩余 {len(filtered)} 条新闻")
    return filtered


def analyze_policy_impact(
    news: list[NewsItem],
    llm_config: dict[str, str],
) -> list[PolicyImpact]:
    """使用LLM分析新闻的政策影响。

    Args:
        news: 新闻列表。
        llm_config: LLM配置（api_url, api_key）。

    Returns:
        政策影响分析结果列表。
    """
    if not news:
        return []

    if not llm_config.get("api_url") or not llm_config.get("api_key"):
        logger.warning("LLM API 配置缺失，返回默认中性评分")
        return [
            PolicyImpact(
                news_title=item.title,
                news_url=item.url,
                affected_industries=["整体市场"],
                impact_direction="neutral",
                impact_degree="indirect",
                impact_score=5.0,
                summary="无法分析政策影响（LLM配置缺失）",
            )
            for item in news[:5]  # 只取前5条
        ]

    # 构建新闻列表文本
    news_text = "\n".join(
        [f"{i+1}. {item.title}（来源：{item.source}）" for i, item in enumerate(news[:10])]
    )

    prompt = f"""你是一位专业的A股市场政策分析师。请分析以下财经新闻对A股各行业的影响。

新闻列表：
{news_text}

请对每条新闻返回以下JSON格式：
{{
  "news_title": "新闻标题",
  "affected_industries": ["行业1", "行业2"],
  "impact_direction": "positive/negative/neutral",
  "impact_degree": "direct/indirect",
  "impact_score": -20到20的数值,
  "summary": "一句话影响摘要"
}}

评分参考：
- 直接利好该行业：+15~20
- 间接利好：+8~14
- 中性：+5
- 间接利空：-5~0
- 直接利空：-10~-5

请只返回JSON数组，不要其他内容。"""

    try:
        response = requests.post(
            llm_config["api_url"],
            headers={
                "Authorization": f"Bearer {llm_config['api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=120,  # LLM API 需要更长超时时间
        )

        if response.status_code != 200:
            logger.warning(f"LLM API 返回错误: {response.status_code}")
            return _default_impacts(news)

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # 解析JSON，并关联URL
        impacts = _parse_llm_response(content, news[:10])
        if impacts:
            return impacts

        logger.warning("LLM 返回格式解析失败")
        return _default_impacts(news)

    except Exception as e:
        logger.warning(f"LLM 调用失败: {e}")
        return _default_impacts(news)


def _parse_llm_response(content: str, news: list[NewsItem] | None = None) -> list[PolicyImpact]:
    """解析LLM返回的JSON响应。

    Args:
        content: LLM返回的内容。
        news: 原始新闻列表（用于关联URL）。

    Returns:
        政策影响列表，解析失败返回空列表。
    """
    try:
        # 尝试提取JSON数组
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            json_str = content[start:end]
            data = json.loads(json_str)

            impacts: list[PolicyImpact] = []
            for i, item in enumerate(data):
                # 从原始新闻列表中获取URL
                news_url = ""
                if news and i < len(news):
                    news_url = news[i].url

                impacts.append(
                    PolicyImpact(
                        news_title=item.get("news_title", ""),
                        news_url=news_url,
                        affected_industries=item.get("affected_industries", []),
                        impact_direction=item.get("impact_direction", "neutral"),
                        impact_degree=item.get("impact_degree", "indirect"),
                        impact_score=float(item.get("impact_score", 5.0)),
                        summary=item.get("summary", ""),
                    )
                )
            return impacts

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"JSON 解析失败: {e}")

    return []


def _default_impacts(news: list[NewsItem]) -> list[PolicyImpact]:
    """生成默认的中性影响。

    Args:
        news: 新闻列表。

    Returns:
        默认中性影响列表。
    """
    return [
        PolicyImpact(
            news_title=item.title,
            news_url=item.url,
            affected_industries=["整体市场"],
            impact_direction="neutral",
            impact_degree="indirect",
            impact_score=5.0,
            summary="政策影响分析不可用",
        )
        for item in news[:5]
    ]


def _extract_industry_keyword(industry: str) -> str:
    """提取行业关键词（去除后缀）。

    Args:
        industry: 行业名称。

    Returns:
        关键词。
    """
    for suffix in ['业', '服务', '制造', '加工', '开采', '销售', '管理', '供应']:
        industry = industry.replace(suffix, '')
    return industry


def _match_industry(clean_industry: str, affected: str) -> bool:
    """判断两个行业名称是否匹配。

    Args:
        clean_industry: 清理后的行业名称。
        affected: 受影响的行业名称。

    Returns:
        是否匹配。
    """
    # 精确匹配
    if clean_industry == affected:
        return True

    # 模糊匹配（双向包含）
    if clean_industry in affected or affected in clean_industry:
        return True

    # 关键词匹配
    kw1 = _extract_industry_keyword(clean_industry)
    kw2 = _extract_industry_keyword(affected)
    if kw1 and kw2 and (kw1 in kw2 or kw2 in kw1):
        return True

    return False


def get_industry_impact_score(
    industry: str,
    impacts: list[PolicyImpact],
) -> float:
    """获取某行业的政策影响综合评分。

    Args:
        industry: 行业名称（支持 BaoStock 格式如 "J66货币金融服务"）。
        impacts: 所有政策影响分析结果。

    Returns:
        评分（-20 ~ +20）。
    """
    if not impacts:
        return 5.0  # 默认中性

    # 清理行业名称（去除 BaoStock 格式前缀）
    clean_industry = industry
    if len(industry) > 3 and industry[0].isalpha() and industry[1:3].isdigit():
        clean_industry = industry[3:]

    total_score = 0.0
    count = 0

    for impact in impacts:
        # 检查行业是否在受影响行业中
        matched = False
        for affected in impact.affected_industries:
            if _match_industry(clean_industry, affected):
                matched = True
                break

        if matched or "整体市场" in impact.affected_industries:
            total_score += impact.impact_score
            count += 1

    if count == 0:
        return 5.0  # 默认中性

    # 返回平均分，限制在 [-20, 20] 范围内
    avg_score = total_score / count
    return max(-20.0, min(20.0, avg_score))
