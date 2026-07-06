"""股票池筛选模块 — 从A股全市场中筛选符合条件的股票。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from config import FilterConfig
from utils import random_delay, retry

logger = logging.getLogger("thousand-times")


def _fetch_stock_spot_ashare() -> pd.DataFrame:
    """使用 Ashare 获取全市场股票实时行情。

    Returns:
        包含股票实时行情的 DataFrame。
    """
    try:
        from ashare import get_price

        # 获取主要指数成分股
        # 这里简化处理，实际应该获取全市场股票
        # 由于 Ashare 主要用于获取单只股票数据，我们使用 AKShare 的备用方案
        raise NotImplementedError("Ashare 不支持批量获取全市场行情")

    except Exception as e:
        logger.warning(f"Ashare 获取全市场行情失败: {e}")
        raise


@retry(max_attempts=3, backoff_factor=2.0)
def _fetch_stock_spot() -> pd.DataFrame:
    """获取全市场股票实时行情（带重试）。

    Returns:
        包含股票实时行情的 DataFrame。
    """
    # 优先使用远程 API
    try:
        from remote_data import is_remote_available, get_stock_spot_remote
        if is_remote_available():
            logger.info("使用远程 API 获取股票数据")
            return get_stock_spot_remote()
    except Exception as e:
        logger.warning(f"远程 API 不可用: {e}")

    # 回退到 AKShare
    try:
        import akshare as ak  # type: ignore[import-untyped]
        logger.info("使用 AKShare 获取股票数据")
        result: pd.DataFrame = ak.stock_zh_a_spot_em()
        return result
    except Exception as e:
        logger.warning(f"AKShare 获取股票数据失败: {e}")
        raise


def _fetch_stock_data_baostock(max_retries: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """使用 BaoStock 获取全市场股票数据（代码+上市日期+行业）。

    带重试机制，一次登录获取所有数据，避免多次登录/登出导致的连接问题。

    Args:
        max_retries: 最大重试次数，默认3次。

    Returns:
        (spot_df, info_df) 元组：
        - spot_df: 包含 code, name, industry 列的股票代码 DataFrame
        - info_df: 包含 代码, 名称, 上市日期 列的股票信息 DataFrame
    """
    import time
    import baostock as bs

    last_error = None
    for attempt in range(max_retries):
        try:
            # 登录
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"BaoStock 登录失败: {lg.error_msg}")
                raise RuntimeError(f"BaoStock 登录失败: {lg.error_msg}")

            try:
                # 获取所有股票代码
                rs = bs.query_stock_basic()
                if rs.error_code != '0':
                    logger.error(f"BaoStock 获取股票列表失败: {rs.error_msg}")
                    raise RuntimeError(f"BaoStock 获取股票列表失败: {rs.error_msg}")

                stock_list = []
                while (rs.error_code == '0') & rs.next():
                    row = rs.get_row_data()
                    stock_list.append(row)

                if not stock_list:
                    logger.warning("BaoStock 返回空股票列表")
                    return pd.DataFrame(), pd.DataFrame()

                # 转换为 DataFrame（防御性检查：字段数与数据列数必须一致）
                fields = rs.fields
                if not fields or len(fields) != len(stock_list[0]):
                    logger.error(
                        f"BaoStock 字段数({len(fields)})与数据列数"
                        f"({len(stock_list[0])})不匹配，跳过"
                    )
                    return pd.DataFrame(), pd.DataFrame()

                stock_df = pd.DataFrame(stock_list, columns=fields)

                # 只保留 A 股（sh.6, sz.0, sz.3 开头）
                a_stock_mask = (
                    stock_df['code'].str.startswith('sh.6') |
                    stock_df['code'].str.startswith('sz.0') |
                    stock_df['code'].str.startswith('sz.3')
                )
                stock_df = stock_df[a_stock_mask]

                # 获取行业信息
                industry_dict = {}
                try:
                    rs_industry = bs.query_stock_industry()
                    if rs_industry.error_code == '0':
                        while (rs_industry.error_code == '0') & rs_industry.next():
                            row = rs_industry.get_row_data()
                            if len(row) >= 4:
                                code = row[1].replace('sh.', '').replace('sz.', '')
                                industry = row[3] if row[3] else ''
                                industry_dict[code] = industry
                        logger.info(f"获取到 {len(industry_dict)} 只股票的行业信息")
                except Exception as e:
                    logger.warning(f"获取行业信息失败: {e}")

                # 构建 spot DataFrame（包含 code, name, industry）
                spot_list = []
                for _, row in stock_df.iterrows():
                    code = row['code'].replace('sh.', '').replace('sz.', '')
                    name = row.get('code_name', '')
                    industry = industry_dict.get(code, '')
                    spot_list.append({
                        'code': code,
                        'name': name,
                        'industry': industry,
                    })

                # 构建 info DataFrame（包含代码、名称、上市日期）
                info_list = []
                for _, row in stock_df.iterrows():
                    code = row['code'].replace('sh.', '').replace('sz.', '')
                    name = row.get('code_name', '')
                    ipo_date = row.get('ipoDate', '')
                    info_list.append({
                        '代码': code,
                        '名称': name,
                        '上市日期': ipo_date,
                    })

                spot_df = pd.DataFrame(spot_list) if spot_list else pd.DataFrame()
                info_df = pd.DataFrame(info_list) if info_list else pd.DataFrame()

                logger.info(f"BaoStock 获取 {len(spot_df)} 只股票代码")
                return spot_df, info_df

            finally:
                bs.logout()

        except Exception as e:
            last_error = e
            # 编码错误、网络错误、BaoStock内部错误可重试
            retryable = isinstance(e, (UnicodeDecodeError, ConnectionError, OSError, RuntimeError))
            if attempt < max_retries - 1 and retryable:
                wait_time = 2 ** attempt
                logger.warning(f"BaoStock 获取失败，{wait_time}秒后重试 ({attempt + 1}/{max_retries}): {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"BaoStock 获取全市场数据失败: {e}")
                break

    raise last_error  # type: ignore[misc]


def get_stock_pool(config: FilterConfig) -> pd.DataFrame:
    """获取筛选后的股票池。

    筛选流程：
    1. 获取全市场股票实时行情
    2. 过滤：市值 >= 20亿
    3. 过滤：名称不含 "ST"
    4. 过滤：PE-TTM > 0
    5. 过滤：上市 >= 3个月
    6. 按市值降序排序
    7. 取前 pool_size 条

    Args:
        config: 股票池筛选配置。

    Returns:
        DataFrame，包含列：code, name, market_cap, pe_ttm, pb, listing_date, industry
        按 market_cap 降序，取前 config.pool_size 条。

    Raises:
        RuntimeError: 所有数据源获取失败。
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    logger.info("开始获取股票池...")

    # 获取全市场实时行情
    df = None
    stock_info = None

    # 优先使用 AKShare（CI 环境更稳定，带超时保护）
    try:
        import akshare as ak  # type: ignore[import-untyped]
        logger.info("使用 AKShare 获取股票数据")

        def _fetch_akshare():
            return ak.stock_zh_a_spot_em()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch_akshare)
            df = future.result(timeout=90)  # 90秒超时（海外 CI 网络慢）
    except FuturesTimeoutError:
        logger.warning("AKShare 获取股票数据超时 (90秒)")
    except Exception as e:
        logger.warning(f"AKShare 获取股票数据失败: {e}")

    # 回退到远程 API
    if df is None or df.empty:
        try:
            from remote_data import is_remote_available, get_stock_spot_remote
            if is_remote_available():
                logger.info("使用远程 API 获取股票数据")
                df = get_stock_spot_remote()
        except Exception as e:
            logger.warning(f"远程 API 不可用: {e}")

    # 最后回退到 BaoStock（带重试机制）
    if df is None or df.empty:
        logger.info("使用 BaoStock 获取股票数据")
        df, stock_info = _fetch_stock_data_baostock()

    if df is None or df.empty:
        raise RuntimeError("所有数据源都获取股票数据失败")

    random_delay()

    # 重命名列（AKShare 返回的列名可能是中文）
    column_mapping = {
        "代码": "code",
        "名称": "name",
        "总市值": "market_cap",
        "市盈率-动态": "pe_ttm",
        "市净率": "pb",
        "最新价": "close",
        "涨跌幅": "change_pct",
    }

    # 只保留存在的列
    existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_columns)

    # 确保必要的列存在
    required_columns = ["code", "name"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"数据源返回数据缺少必要列: {col}")

    # 过滤：市值 >= 20亿（如果市值数据可用）
    if "market_cap" in df.columns:
        df = df[df["market_cap"] >= config.min_market_cap]
    else:
        logger.warning("市值数据不可用，跳过市值过滤")

    # 过滤：名称不含 "ST"
    df = df[~df["name"].str.contains("ST", case=False, na=False)]

    # 过滤：PE-TTM > 0（如果PE数据可用）
    if "pe_ttm" in df.columns:
        df = df[df["pe_ttm"] > 0]
    else:
        logger.warning("PE数据不可用，跳过PE过滤")

    # 获取上市日期信息（如果 BaoStock 没有提供，则尝试 AKShare）
    if stock_info is not None and not stock_info.empty:
        try:
            random_delay()

            # 重命名列
            if "上市日期" in stock_info.columns:
                stock_info = stock_info.rename(columns={"代码": "code", "上市日期": "listing_date"})
                # 合并上市日期
                df = df.merge(stock_info[["code", "listing_date"]], on="code", how="left")

                # 过滤：上市 >= 3个月
                cutoff_date = datetime.now() - timedelta(days=config.min_listing_months * 30)
                if "listing_date" in df.columns:
                    df["listing_date"] = pd.to_datetime(df["listing_date"], errors="coerce")
                    df = df[df["listing_date"].isna() | (df["listing_date"] <= cutoff_date)]
        except Exception as e:
            logger.warning(f"处理上市日期信息失败: {e}")
    else:
        # 尝试从 AKShare 获取上市日期
        try:
            import akshare as ak  # type: ignore[import-untyped]
            stock_info = ak.stock_info_a_code_name()
            random_delay()

            # 重命名列
            if "上市日期" in stock_info.columns:
                stock_info = stock_info.rename(columns={"代码": "code", "上市日期": "listing_date"})
                # 合并上市日期
                df = df.merge(stock_info[["code", "listing_date"]], on="code", how="left")

                # 过滤：上市 >= 3个月
                cutoff_date = datetime.now() - timedelta(days=config.min_listing_months * 30)
                if "listing_date" in df.columns:
                    df["listing_date"] = pd.to_datetime(df["listing_date"], errors="coerce")
                    df = df[df["listing_date"].isna() | (df["listing_date"] <= cutoff_date)]
        except Exception as e:
            logger.warning(f"获取上市日期信息失败，跳过上市时间过滤: {e}")

    # 按市值降序排序（如果市值数据可用）
    if "market_cap" in df.columns:
        df = df.sort_values("market_cap", ascending=False)
    else:
        logger.warning("市值数据不可用，跳过市值排序")

    # 取前 pool_size 条
    df = df.head(config.pool_size)

    # 确保返回的列存在
    result_columns = ["code", "name", "market_cap", "pe_ttm"]
    if "pb" in df.columns:
        result_columns.append("pb")
    if "listing_date" in df.columns:
        result_columns.append("listing_date")
    if "industry" in df.columns:
        result_columns.append("industry")

    # 只保留存在的列
    result_columns = [col for col in result_columns if col in df.columns]
    result_df: pd.DataFrame = df[result_columns].reset_index(drop=True)

    logger.info(f"股票池筛选完成，共 {len(result_df)} 只股票")
    return result_df
