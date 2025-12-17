from flask import Flask, request, jsonify  # , abort
import logging
from logging.handlers import TimedRotatingFileHandler
import os, sys, math, time
from collections import defaultdict  # 캐시를 위한 defaultdict 추가
import pandas as pd

# 현재 스크립트의 디렉토리 경로를 얻습니다.
current_dir = os.path.dirname(os.path.abspath(__file__))

# account, upbit_data, trading, utils 디렉토리의 경로를 생성
account_dir = os.path.join(current_dir, 'account')
trading_dir = os.path.join(current_dir, 'trading')
utils_dir = os.path.join(current_dir, 'utils')
upbit_data_dir = os.path.join(current_dir, 'upbit_data')

# sys.path에 디렉토리를 추가
sys.path.append(account_dir)
sys.path.append(trading_dir)
sys.path.append(utils_dir)
sys.path.append(upbit_data_dir)

# import
from account.my_account import get_my_exchange_account
from trading.trade import buy_market, sell_market, get_open_order
from utils.email_utils import send_email
from utils.convert_utils import convert_trade_ticker, convert_simple_ticker, get_trade_price, \
    calculate_min_quantity_precise
from upbit_data.candle import get_min_candle_data

# Flask
app = Flask(__name__)

# logs 폴더 생성 (없으면 자동 생성)
os.makedirs('logs', exist_ok=True)

# TimedRotatingFileHandler 설정: 일자별 로테이션
handler = TimedRotatingFileHandler(
    filename='logs/app.log',  # 기본 파일명 (로테이션 시 변경됨)
    when='midnight',  # 자정에 로테이션
    interval=1,  # 1일 간격
    backupCount=30,  # 최대 30일치 백업 파일 유지 (필요 시 조정)
    encoding='utf-8'  # UTF-8 인코딩
)
handler.suffix = '%Y-%m-%d.log'  # 로테이션 파일명: app.log.YYYY-MM-DD
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))  # 로그 형식

# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# TradingView에서 설정한 시크릿 키
SECRET_KEY = 'tradingview_haguri_peng_secret_key'

# 중복 검사 캐시: 키 = "ticker_value_signal", 값 = 마지막 처리 timestamp
signal_cache = defaultdict(float)  # 기본값 0.0 (float)

# 중복 검사 시간 창: 30초
DUPLICATE_WINDOW = 30

# EMA 크로스
EMA_cross = ''


# 캔들 조회
def get_candle_data(ticker: str, minute: int):
    return get_min_candle_data(ticker, minute)


# EMA 계산
def calc_ema(df: pd.DataFrame):
    # DataFrame 필수 데이터 검증
    required_columns = ['close', 'date', 'time', 'volume']
    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"DataFrame은 {required_columns} 컬럼을 포함해야 합니다.")

    # 최소 200개 데이터 필요 (MA200 계산을 위해)
    if len(df) < 200:
        print('데이터가 부족합니다 (최소 200개 필요).')
        raise ValueError(f"데이터가 부족(최소 200개는 필요)합니다.")

    # EMA
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()

    # 50EMA와 200EMA 비교)
    return df['EMA50'].iloc[-1] > df['EMA200'].iloc[-1]


# Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    global EMA_cross

    # # 인증 검증
    # signature = request.headers.get('X-Signature')
    # if signature != SECRET_KEY:
    #     logger.error("Invalid signature.")
    #     abort(403)

    try:
        data = request.get_json()
        if not data:
            raise ValueError("No JSON data.")

        logger.info(f"Received: {data}")

        ticker: str = data.get('ticker')
        value: str = data.get('value')
        if not all([ticker, value]):
            raise ValueError("Missing fields.")

        # EMA 크로스 값 세팅
        if value.startswith('EMA'):
            EMA_cross = value

        # signal = ''
        # if value.startswith('long'):
        #     # 50EMA > 200EMA인 경우에만 매수 시그널
        #     if EMA_cross == 'EMA_cross_up':
        #         signal = 'buy'
        # elif value.startswith('short'):
        #     signal = 'sell'
        signal = value.lower()

        logger.info(f"signal: {signal}")
        if not signal:
            raise ValueError("signal is empty.")

        # 중복 검사 키 생성
        cache_key = f"{ticker}_{value}_{signal}"

        current_time = time.time()
        last_processed = signal_cache[cache_key]

        if last_processed > 0 and (current_time - last_processed) < DUPLICATE_WINDOW:
            logger.info(f"Duplicate signal ignored: {data}")
            return jsonify({"status": "duplicate_ignored"}), 200

        # 중복 아니면 바로 캐시 업데이트 (처리 시작 마킹)
        signal_cache[cache_key] = current_time

        # 매매 로직 호출
        process_trade(ticker, signal, value)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


def get_account_info(ticker: str):
    logger.info("========== get_account_info ==========")

    # Get my account infomation
    my_account = get_my_exchange_account()

    # ticker 기준으로 확인
    is_ticker_in_account = False
    ticker_balance = '0'
    ticker_avg_buy_price = 0.0

    if 'currency' not in my_account.columns:
        raise ValueError("[currency] 컬럼이 존재하지 않습니다.")

    if ticker in my_account['currency'].values:
        is_ticker_in_account = True
        ticker_balance = my_account[my_account['currency'] == ticker]['balance'].values[0]
        ticker_avg_buy_price = float(my_account[my_account['currency'] == ticker]['avg_buy_price'].values[0])

    logger.info(f"is_ticker_in_account : {is_ticker_in_account}")
    logger.info(f"ticker_balance : {ticker_balance}")
    logger.info(f"ticker_avg_buy_price : {ticker_avg_buy_price}")

    # 원화 잔고 확인
    krw_amount = 0.0
    krw_ticker = 'KRW'
    if krw_ticker in my_account['currency'].values:
        my_account['balance'] = my_account['balance'].astype(float)
        krw_amount = my_account[my_account['currency'] == krw_ticker]['balance'].values[0]

    logger.info(f"krw_amount : {krw_amount}")

    # 투자 가능한 원화 계산
    # 거래 수수료는 원화(KRW) 마켓에서는 0.05%이나 실제 매수 시 전체 금액에서 0.1%를 제한 금액으로 투자를 진행
    krw_invest_amount = 0
    if krw_amount > 0:
        krw_invest_amount = math.floor(krw_amount * 0.999)

    logger.info(f"krw_invest_amount : {krw_invest_amount}")

    return {
        'is_ticker': is_ticker_in_account,
        'ticker_balance': ticker_balance,
        'ticker_buy_price': ticker_avg_buy_price,
        'krw_balance': krw_amount,
        'krw_available': krw_invest_amount
    }


def process_trade(ticker: str, signal: str, value: str):
    # 기존 매매 로직 (비동기 가능하게)
    logger.info(f"Process trading {signal} {ticker}")

    # 매매 시 사용하는 티커로 변경 (e.g. DOGEKRW -> KRW-DOGE)
    trade_ticker = convert_trade_ticker(ticker)
    simple_ticker = convert_simple_ticker(ticker)  # DOGE

    logger.info(f"trade_ticker : {trade_ticker}")
    logger.info(f"simple_ticker : {simple_ticker}")

    # trade_price 추출
    ticker_trade_price = get_trade_price(trade_ticker)

    logger.info(f"[{trade_ticker}] ticker_trade_price : {ticker_trade_price}")

    # 계좌정보 확인
    account_info = get_account_info(simple_ticker)

    # 매수
    if signal == 'buy':
        # 현재 계좌의 잔고(KRW)에서 투자 가능한 금액 확인
        krw_available = math.floor(account_info['krw_available'])

        logger.info(f"krw_available : {krw_available}")

        # 5,000원(최소 거래금액) 이상일 때 진행
        # 5,000 -> 50,000 KRW
        # if krw_available >= 5000:
        if krw_available >= 50000:
            buy_krw_amount = 50000

            # 매수 거래
            # buy_result = buy_market(trade_ticker, krw_available)
            buy_result = buy_market(trade_ticker, buy_krw_amount)

            if buy_result['uuid'].notnull()[0]:
                # 시장가로 주문하기 때문에 uuid 값이 있으면 정상적으로 처리됐다고 가정한다.
                # logger.info(f"[{trade_ticker}] {krw_available}원 매수 하였습니다.")
                logger.info(f"[{trade_ticker}] {buy_krw_amount}원 매수 하였습니다.")
                # send_email(f'[{trade_ticker}] 시장가 매수', f'TrendFollow - {value}')
                send_email(f'[{trade_ticker}] 시장가 매수', f'[{trade_ticker}] {buy_krw_amount}원 매수 하였습니다.')
            else:
                send_email('매수 중 에러 발생', '매수 중 에러가 발생하였습니다. 확인해주세요.')
                raise RuntimeError("매수가 정상적으로 처리되지 않았습니다.")

    # 매도
    elif signal == 'sell':
        ticker_balance = account_info['ticker_balance']
        if not ticker_balance or ticker_balance == '0':
            raise ValueError("매도할 대상이 없습니다.")

        if ticker_trade_price is None:
            raise ValueError(f"[{ticker}] trade_price 가 없습니다.")

        # 매도할 balance를 50,000 KRW에 맞게 환산
        sell_amount = calculate_min_quantity_precise(ticker_trade_price, 8)

        # sell_amount > ticker_balance
        if sell_amount > ticker_balance:
            sell_amount = ticker_balance

        logger.info(f"ticker_balance : {ticker_balance}")
        logger.info(f"sell_amount : {sell_amount}")

        sell_result = sell_market(trade_ticker, str(sell_amount))
        if sell_result['uuid'].notnull()[0]:
            while True:
                open_order_df = get_open_order(trade_ticker, 'wait')

                time.sleep(5)  # 5초 대기

                # wait 중인 거래가 없으면 반복 중단
                if len(open_order_df) == 0:
                    break

            logger.info(f"[{trade_ticker}] {sell_amount} 매도 하였습니다.")
            send_email(f'[{trade_ticker}] 시장가 매도',
                       f'{sell_amount} 매도 하였습니다.')
        else:
            send_email('매도 중 에러 발생', '매도 중 에러가 발생하였습니다. 확인해주세요.')
            raise RuntimeError("매도가 정상적으로 처리되지 않았습니다.")


if __name__ == '__main__':
    logger.info("TradeHook Web Server starts..")

    # 도지코인(KRW-DOGE) 10분봉 가져오기
    doge_10min_data = get_candle_data('KRW-DOGE', 10)

    is_EMA_cross_up = calc_ema(doge_10min_data)
    EMA_cross = 'EMA_cross_up' if is_EMA_cross_up else 'EMA_cross_down'

    logger.info(f"EMA_cross : {EMA_cross}")

    app.run(host='0.0.0.0', port=5555, debug=False)
