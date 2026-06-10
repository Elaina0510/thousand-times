"""BaoStock 数据源模块 — 使用 BaoStock 获取 A 股数据。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Generator
from contextlib import contextmanager

import pandas as pd

logger = logging.getLogger("thousand-times")


def _convert_code(code: str) -> str:
    """将股票代码转换为 BaoStock 格式。

    Args:
        code: 股票代码，如 '600519', '000001', '512480'

    Returns:
        BaoStock 格式代码，如 'sh.600519', 'sz.000001'
    """
    code = code.strip()

    # 如果已经是 sh./sz. 格式，直接返回
    if code.startswith('sh.') or code.startswith('sz.'):
        return code

    # 根据代码判断交易所
    # 上海：6开头的股票，5开头的ETF，000001（上证指数）
    # 深圳：0/3开头的股票，1开头的ETF
    if code.startswith('6') or code.startswith('5'):
        return f'sh.{code}'
    elif code.startswith('0') or code.startswith('3') or code.startswith('1'):
        return f'sz.{code}'
    else:
        # 默认尝试上海
        return f'sh.{code}'


@contextmanager
def baostock_session() -> Generator:
    """BaoStock 会话上下文管理器。

    使用方式:
        with baostock_session() as bs:
            rs = bs.query_history_k_data_plus(...)
    """
    import baostock as bs

    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"BaoStock 登录失败: {lg.error_msg}")

    try:
        yield bs
    finally:
        bs.logout()


def get_stock_hist_baostock(code: str, days: int = 60) -> pd.DataFrame:
    """使用 BaoStock 获取个股历史行情。

    Args:
        code: 股票代码
        days: 获取天数

    Returns:
        DataFrame，包含 open, close, high, low, volume 列
    """
    try:
        with baostock_session() as bs:
            # 计算日期范围
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

            # 转换代码格式
            bs_code = _convert_code(code)

            # 获取日线数据
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2"  # 前复权
            )

            if rs.error_code != '0':
                logger.error(f"BaoStock 获取 {code} 失败: {rs.error_msg}")
                return pd.DataFrame()

            # 解析数据
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                logger.warning(f"BaoStock 返回空数据: {code}")
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)

            # 转换数据类型
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 重命名列以匹配 AKShare 格式
            df = df.rename(columns={
                'date': '日期',
                'open': '开盘',
                'close': '收盘',
                'high': '最高',
                'low': '最低',
                'volume': '成交量',
            })

            logger.info(f"BaoStock 获取 {code} 成功，共 {len(df)} 条数据")
            return df

    except Exception as e:
        logger.error(f"BaoStock 获取 {code} 失败: {e}")
        return pd.DataFrame()


def get_stock_hist_batch_baostock(codes: list[str], days: int = 60) -> dict[str, pd.DataFrame]:
    """批量获取多只股票的历史行情（共享一个 BaoStock 会话）。

    Args:
        codes: 股票代码列表
        days: 获取天数

    Returns:
        字典，键为股票代码，值为对应的 DataFrame
    """
    result = {}

    try:
        with baostock_session() as bs:
            # 计算日期范围
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

            for code in codes:
                try:
                    # 转换代码格式
                    bs_code = _convert_code(code)

                    # 获取日线数据
                    rs = bs.query_history_k_data_plus(
                        bs_code,
                        "date,open,high,low,close,volume",
                        start_date=start_date,
                        end_date=end_date,
                        frequency="d",
                        adjustflag="2"  # 前复权
                    )

                    if rs.error_code != '0':
                        logger.warning(f"BaoStock 获取 {code} 失败: {rs.error_msg}")
                        result[code] = pd.DataFrame()
                        continue

                    # 解析数据
                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())

                    if not data_list:
                        logger.warning(f"BaoStock 返回空数据: {code}")
                        result[code] = pd.DataFrame()
                        continue

                    df = pd.DataFrame(data_list, columns=rs.fields)

                    # 转换数据类型
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                    # 重命名列以匹配 AKShare 格式
                    df = df.rename(columns={
                        'date': '日期',
                        'open': '开盘',
                        'close': '收盘',
                        'high': '最高',
                        'low': '最低',
                        'volume': '成交量',
                    })

                    result[code] = df

                except Exception as e:
                    logger.warning(f"BaoStock 获取 {code} 失败: {e}")
                    result[code] = pd.DataFrame()

    except Exception as e:
        logger.error(f"BaoStock 批量获取失败: {e}")

    return result


def get_etf_hist_baostock(code: str, days: int = 60) -> pd.DataFrame:
    """使用 BaoStock 获取 ETF 历史行情。

    Args:
        code: ETF 代码
        days: 获取天数

    Returns:
        DataFrame，包含 open, close, high, low, volume 列
    """
    # ETF 和股票使用相同的接口
    return get_stock_hist_baostock(code, days)


def get_index_hist_baostock(code: str, days: int = 60) -> pd.DataFrame:
    """使用 BaoStock 获取指数历史行情。

    Args:
        code: 指数代码，如 '000001'（上证指数）
        days: 获取天数

    Returns:
        DataFrame，包含 open, close, high, low, volume 列
    """
    try:
        with baostock_session() as bs:
            # 计算日期范围
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

            # 指数代码格式
            if code == '000001':
                bs_code = 'sh.000001'
            elif code == '399006':
                bs_code = 'sz.399006'
            elif code == '399001':
                bs_code = 'sz.399001'
            else:
                bs_code = _convert_code(code)

            # 获取日线数据
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d"
            )

            if rs.error_code != '0':
                logger.error(f"BaoStock 获取指数 {code} 失败: {rs.error_msg}")
                return pd.DataFrame()

            # 解析数据
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                logger.warning(f"BaoStock 返回空数据: {code}")
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)

            # 转换数据类型
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 重命名列
            df = df.rename(columns={
                'date': '日期',
                'open': '开盘',
                'close': '收盘',
                'high': '最高',
                'low': '最低',
                'volume': '成交量',
            })

            return df

    except Exception as e:
        logger.error(f"BaoStock 获取指数 {code} 失败: {e}")
        return pd.DataFrame()


def get_stock_spot_baostock() -> pd.DataFrame:
    """使用 BaoStock 获取全市场股票实时行情。

    注意：BaoStock 不支持实时行情，这里返回空 DataFrame。
    需要配合其他数据源使用。

    Returns:
        空 DataFrame
    """
    logger.warning("BaoStock 不支持实时行情，请使用其他数据源")
    return pd.DataFrame()


def test_baostock() -> bool:
    """测试 BaoStock 是否可用。

    Returns:
        是否可用
    """
    try:
        with baostock_session() as bs:
            # 测试获取上证指数
            rs = bs.query_history_k_data_plus(
                "sh.000001",
                "date,open,high,low,close,volume",
                start_date=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d'),
                frequency="d"
            )

            if rs.error_code != '0':
                logger.error(f"BaoStock 测试失败: {rs.error_msg}")
                return False

            # 检查是否有数据
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())

            if data_list:
                logger.info("BaoStock 测试成功")
                return True
            else:
                logger.warning("BaoStock 测试失败：返回空数据")
                return False

    except Exception as e:
        logger.warning(f"BaoStock 测试失败: {e}")
        return False


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    print("测试 BaoStock 数据源...")
    if test_baostock():
        print("[OK] BaoStock 可用")

        # 测试获取贵州茅台
        df = get_stock_hist_baostock('600519', days=10)
        print(f"\n贵州茅台最近10天数据:")
        print(df)
    else:
        print("[ERROR] BaoStock 不可用")
