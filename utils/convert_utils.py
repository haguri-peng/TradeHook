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
