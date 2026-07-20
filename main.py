import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="글로벌 주식 대시보드", layout="wide")

# ----------------------------
# 종목 리스트 (지수 + 주요 개별주)
# ----------------------------
TICKERS = {
    "S&P 500 (미국)": "^GSPC",
    "다우존스 (미국)": "^DJI",
    "나스닥 (미국)": "^IXIC",
    "코스피 (한국)": "^KS11",
    "코스닥 (한국)": "^KQ11",
    "니케이225 (일본)": "^N225",
    "항셍 (홍콩)": "^HSI",
    "DAX (독일)": "^GDAXI",
    "FTSE100 (영국)": "^FTSE",
    "상하이종합 (중국)": "000001.SS",
    "애플 (AAPL)": "AAPL",
    "마이크로소프트 (MSFT)": "MSFT",
    "엔비디아 (NVDA)": "NVDA",
    "테슬라 (TSLA)": "TSLA",
    "삼성전자 (005930)": "005930.KS",
}

# ----------------------------
# 사이드바 설정
# ----------------------------
st.sidebar.title("설정")

selected_names = st.sidebar.multiselect(
    "종목 선택 (복수 선택 가능)",
    options=list(TICKERS.keys()),
    default=["S&P 500 (미국)", "코스피 (한국)", "나스닥 (미국)"]
)

period_options = {
    "1개월": "1mo",
    "3개월": "3mo",
    "6개월": "6mo",
    "1년": "1y",
    "2년": "2y",
    "5년": "5y",
}
selected_period_label = st.sidebar.selectbox("조회 기간", list(period_options.keys()), index=2)
period = period_options[selected_period_label]

chart_type = st.sidebar.radio("차트 유형", ["라인 차트", "캔들스틱"])

st.sidebar.markdown("---")
st.sidebar.caption("데이터 출처: Yahoo Finance (yfinance)")

# ----------------------------
# 메인 타이틀
# ----------------------------
st.title("🌍 글로벌 주요 주식 대시보드")
st.caption(f"업데이트 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if not selected_names:
    st.warning("사이드바에서 하나 이상의 종목을 선택해주세요.")
    st.stop()

# ----------------------------
# 데이터 가져오기 (캐시 적용)
# ----------------------------
@st.cache_data(ttl=600)
def get_stock_data(ticker, period):
    df = yf.Ticker(ticker).history(period=period)
    return df

@st.cache_data(ttl=600)
def get_stock_info(ticker):
    try:
        info = yf.Ticker(ticker).fast_info
        return info
    except Exception:
        return None

# ----------------------------
# 요약 지표 카드
# ----------------------------
st.subheader("📊 현재가 요약")
cols = st.columns(len(selected_names))

summary_data = {}

for i, name in enumerate(selected_names):
    ticker = TICKERS[name]
    df = get_stock_data(ticker, period)

    if df.empty:
        cols[i].metric(label=name, value="데이터 없음")
        continue

    summary_data[name] = df

    last_close = df["Close"].iloc[-1]
    prev_close = df["Close"].iloc[-2] if len(df) > 1 else last_close
    change = last_close - prev_close
    pct_change = (change / prev_close) * 100 if prev_close != 0 else 0

    cols[i].metric(
        label=name,
        value=f"{last_close:,.2f}",
        delta=f"{change:,.2f} ({pct_change:+.2f}%)"
    )

st.markdown("---")

# ----------------------------
# 개별 차트
# ----------------------------
st.subheader("📈 종목별 차트")

for name in selected_names:
    if name not in summary_data:
        continue

    df = summary_data[name]
    ticker = TICKERS[name]

    with st.expander(f"{name} ({ticker})", expanded=True):
        fig = go.Figure()

        if chart_type == "캔들스틱":
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name=name
            ))
        else:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df["Close"],
                mode="lines",
                name=name,
                line=dict(width=2)
            ))

        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title="날짜",
            yaxis_title="가격",
            xaxis_rangeslider_visible=False,
            template="plotly_white"
        )

        st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# 종목 비교 차트 (정규화된 수익률)
# ----------------------------
if len(summary_data) > 1:
    st.markdown("---")
    st.subheader("🔄 수익률 비교 (기준일=100)")

    fig_compare = go.Figure()

    for name, df in summary_data.items():
        normalized = (df["Close"] / df["Close"].iloc[0]) * 100
        fig_compare.add_trace(go.Scatter(
            x=df.index,
            y=normalized,
            mode="lines",
            name=name,
            line=dict(width=2)
        ))

    fig_compare.update_layout(
        height=450,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="날짜",
        yaxis_title="정규화된 수익률 (기준일=100)",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig_compare, use_container_width=True)

st.markdown("---")
st.caption("⚠️ 본 대시보드는 정보 제공 목적이며 투자 권유가 아닙니다.")
