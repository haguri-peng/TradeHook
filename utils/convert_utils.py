from typing import Optional

import requests
from decimal import Decimal, ROUND_CEILING


def convert_trade_ticker(ticker: str):
    # 뒤 3자리를 quote로 가정
    quote = ticker[-3:]
    base = ticker[:-3]
    return f'{quote}-{base}'


def convert_simple_ticker(ticker: str):
    # 뒤 3자리를 quote로 가정
    # quote = ticker[-3:]
    base = ticker[:-3]
    return f'{base}'


def get_trade_price(ticker: str) -> Optional[float]:
    """
    ticker 데이터에서 특정 마켓의 trade_price 추출.

    Args:
        ticker (str): 마켓 이름 (예: "KRW-BTC")

    Returns:
        Optional[float]: trade_price 또는 None (마켓 없음 시)
    """
    if not ticker:
        raise ValueError("Ticker가 없습니다.")

    url = f'https://api.upbit.com/v1/ticker?markets={ticker}'
    headers = {"accept": "application/json"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # HTTP 에러(4xx/5xx) 시 예외 발생
        data = response.json()

        # data 타입 확인 및 처리 (리스트 예상)
        if not isinstance(data, list):
            print(f"예상치 못한 응답 형식: {type(data)}. 데이터: {data}")
            return None

        for item in data:
            if isinstance(item, dict) and item.get('market') == ticker:
                return item['trade_price']

        print(f"마켓 '{ticker}'을 찾을 수 없습니다.")
        return None

    except requests.RequestException as e:
        print(f"API 호출 에러: {e}")
        return None
    except ValueError as e:  # JSON 파싱 에러
        print(f"JSON 파싱 에러: {e}")
        return None


def calculate_min_quantity_precise(price: float, decimal_places: int = 8) -> Decimal:
    """
    소수점 자릿수(기본 8자리) 고려한 최소 코인 수량 계산.
    tick 단위로 올림하여 최소 50,000 KRW 가치 보장.

    Args:
        price (float): 현재 코인 가격 (KRW)
        decimal_places (int): 소수점 자릿수 (BTC:8, ETH:4 등 코인별 조정)

    Returns:
        Decimal: 최소 수량 (8자리 정밀도 적용)
    """
    if price <= 0:
        raise ValueError("가격은 0보다 커야 합니다.")

    min_amount = Decimal('50000')
    price_dec = Decimal(str(price))  # str 변환으로 부동소수점 오류 방지

    tick = Decimal('10') ** -decimal_places  # tick = 0.00000001 (8자리)
    raw_q = min_amount / price_dec  # 기본 비율

    # tick 단위로 올림: ceil(raw_q / tick) * tick
    ceiled_integral = (raw_q / tick).to_integral_value(rounding=ROUND_CEILING)
    min_quantity = ceiled_integral * tick

    actual_value = min_quantity * price_dec
    print(f"최소 수량: {min_quantity}")
    print(f"실제 가치: {actual_value:.2f} KRW (최소 {min_amount} KRW 이상)")

    return min_quantity

# btc_trade_price = get_trade_price("KRW-BTC")
# print(btc_trade_price)
#
# calc_50000 = calculate_min_quantity_precise(btc_trade_price)
# print(calc_50000)
