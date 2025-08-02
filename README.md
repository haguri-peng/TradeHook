# TradeHook

TradingView에서 등록한 얼러트(Alert) 조건을 만족하면 `웹훅(WebHook)`을 발송하는데, 이 알림 메시지를 받아 업비트(UPbit)와 연동하여 자동 매매합니다.

## TradingView

### Alert Message

메시지는 텍스트 형태로 받을 수 있으나 다음과 같이 `JSON` 형태로 세팅하여 받습니다.  
원하는 메시지를 설정하여 각 메시지에 알맞게 매매할 수 있게 설정하면 됩니다.

- Buy

```json
{
  "ticker": "{{ticker}}",
  "value": "longMACD"
}
```

- Sell

```json
{
  "ticker": "{{ticker}}",
  "value": "shortMACD"
}
```

### 웹훅 URL

알림이 트리거 되면 지정된 URL로 설정한 메시지를 POST 요청으로 보낼 수 있습니다.  
(e.g. `http://123.45.67.89/webhook`)

### 매매 전략

다음 전략을 통해 자동 매매를 진행하며, 이 매매 전략의 <u>디폴트는 1시간이나 저는 **10분**으로 설정</u>하였습니다.  
[Trend Follow with 8/34 EMA and Stoch RSI for 1 Hour SPX](https://kr.tradingview.com/script/583nFVCB-Trend-Follow-with-8-34-EMA-and-Stoch-RSI-for-1-Hour-SPX/)

- 실전에서의 문제
    1. 하락장(e.g. 50EMA < 200EMA 혹은 200EMA 기울기가 음수)에선 이 전략으로 이기기 힘듦
    2. 실제 거래기록도 그렇고, 이 전략으로 보여지는 차트에선 하락장에서 벌기 쉽지 않음을 확인

- 대처
    1. <u>50EMA가 200EMA를 상승 돌파</u>(50EMA > 200EMA)하기 전까진 매수 거래를 하지 않음
    2. 단, 매도 거래는 허용
    3. 기존에는 UPbit에서 직접 조회해서 결과값을 계산하여 처리하였으나 TradinvView의 [EMA크로스](https://kr.tradingview.com/script/zX2A1vBN/)를 사용하여
       웹훅에서 알림 메시지를 받게 처리
    4. 단, 서버를 기동할 때 최초에는 EMA 크로스 상태를 알 수 없기에 UPbit에서 정보를 확인하여 세팅합니다.

```json
{
  "ticker": "{{ticker}}",
  "value": "EMA_cross_up"
}
```

```json
{
  "ticker": "{{ticker}}",
  "value": "EMA_cross_down"
}
```

## Web Server

`/webhook`에 POST 요청이 들어왔을 때에만 동작합니다.

### SECRET_KEY

TradingView에서 HTTP 요청 시, Header에 별도의 SECRET_KEY를 설정할 수 없기에 Alert Message에 별도의 키값을 추가하여 검증하면 된다.
다만, 굳이 검증할 필요는 없다고 판단하여 이 프로젝트에서는 검증하는 로직은 제외하였습니다.

### 시그널

메시지의 값(value)이 `long`으로 시작하면 buy, `short`으로 시작하면 sell로 판단합니다.
이 부분은 각자 원하는 대로 설정하여 사용하면 됩니다.

### 중복 체크

웹훅이 같은 값으로 <u>한 번만 오는 게 아니라 여러(3-4) 번 정도 5초(?) 간격</u>으로 오기 때문에 최초에 수신된 건에 대해서만 매매를 수행합니다.  
(**30초** 이내에 동일한 메시지인지 필터링)

### logs

로그는 `/logs/app.log`에 기본적으로 기록되며, 하루 간격으로 파일이 로테이션됩니다.

## UPbit

### .env

Key(`ACCESS_KEY`, `SECRET_KEY`)와 이메일 정보를 세팅합니다.

### account

내 계좌 정보를 확인합니다.

### trading

매매와 관련된 기능을 수행합니다.

- 매수(Buy)
- 매도(Sell)
- 체결 대기주문 확인(Open Order)

## Etc

### utils

매매 시, [.env](.env) 에 세팅한 이메일 정보를 통해 메일을 전송합니다.

## Tree

```shell
.
├── .env
├── .gitignore
├── account
│   └── my_account.py
├── logs
│   ├── app.log
├── README.md
├── requirements.txt
├── trading
│   └── trade.py
├── upbit_data
│   └── candle.py
├── utils
│   ├── convert_utils.py
│   └── email_utils.py
└── webserver.py

6 directories, 11 files
```

## 참조

- [UPbitAutoTrading](https://github.com/haguri-peng/UPbitAutoTrading)
