import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import time
from datetime import datetime

st.set_page_config(page_title="AI 반도체 분석", layout="wide")

# ----------------------------
# AI 반도체 관련 종목 리스트
# ----------------------------
TICKERS = {
    "엔비디아 (NVDA)": "NVDA",
    "AMD (AMD)": "AMD",
    "인텔 (INTC)": "INTC",
    "TSMC (TSM)": "TSM",
    "ASML (ASML)": "ASML",
    "브로드컴 (AVGO)": "AVGO",
    "마이크론 (MU)": "MU",
    "퀄컴 (QCOM)": "QCOM",
    "ARM 홀딩스 (ARM)": "ARM",
    "삼성전자 (005930)": "005930.KS",
    "SK하이닉스 (000660)": "000660.KS",
}

BENCHMARK_TICKER = "SOXX"   # 필라델피아 반도체 ETF (섹터 벤치마크)
BENCHMARK_NAME = "SOXX (반도체 ETF)"

# ----------------------------
# 사이드바 설정
# ----------------------------
st.sidebar.title("설정")

selected_names = st.sidebar.multiselect(
    "분석할 AI 반도체 종목",
    options=list(TICKERS.keys()),
    default=["엔비디아 (NVDA)", "AMD (AMD)", "TSMC (TSM)", "브로드컴 (AVGO)"]
)

period_options = {
    "3개월": "3mo",
    "6개월": "6mo",
    "1년": "1y",
    "2년": "2y",
}
selected_period_label = st.sidebar.selectbox("조회 기간", list(period_options.keys()), index=2)
period = period_options[selected_period_label]

show_benchmark = st.sidebar.checkbox(f"벤치마크({BENCHMARK_NAME}) 비교 포함", value=True)

st.sidebar.markdown("---")
st.sidebar.info("데이터는 30분 캐시됩니다. (Yahoo Finance 요청 제한 방지)")

# ----------------------------
# 메인 타이틀
# ----------------------------
st.title("🤖 AI 반도체 전문 분석 대시보드")
st.caption(f"업데이트 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if not selected_names:
    st.warning("사이드바에서 하나 이상의 종목을 선택해주세요.")
    st.stop()

selected_tickers = [TICKERS[name] for name in selected_names]
fetch_tickers = list(selected_tickers)
if show_benchmark:
    fetch_tickers.append(BENCHMARK_TICKER)

# ----------------------------
# 배치 다운로드 + 재시도 + 캐시
# ----------------------------
@st.cache_data(ttl=1800, show_spinner="반도체 주가 데이터를 불러오는 중입니다...")
def get_all_stock_data(tickers, period):
    for attempt in range(3):
        try:
            data = yf.download(
                tickers=tickers,
                period=period,
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
            return data
        except Exception as e:
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise e

@st.cache_data(ttl=1800, show_spinner=False)
def get_fundamentals(ticker):
    """PER, 시가총액 등 펀더멘털 정보 (실패해도 앱이 죽지 않도록 처리)"""
    try:
        info = yf.Ticker(ticker).get_info()
        return {
            "marketCap": info.get("marketCap"),
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector"),
        }
    except Exception:
        return {}

try:
    raw_data = get_all_stock_data(tuple(fetch_tickers), period)
except Exception:
    st.error(
        "⚠️ Yahoo Finance 요청이 일시적으로 제한되었습니다 (Rate Limit).\n\n"
        "1~2분 후 새로고침 해주세요."
    )
    st.stop()

is_single = len(fetch_tickers) == 1

def extract_df(raw_data, ticker, is_single):
    if is_single:
        df = raw_data
    else:
        if ticker not in raw_data.columns.get_level_values(0):
            return pd.DataFrame()
        df = raw_data[ticker]
    return df.dropna(how="all")

# ----------------------------
# 기술적 지표 계산 함수
# ----------------------------
def add_technical_indicators(df):
    df = df.copy()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()

    # RSI (14일)
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    return df

stock_data = {}
for name in selected_names:
    ticker = TICKERS[name]
    df = extract_df(raw_data, ticker, is_single)
    if not df.empty:
        stock_data[name] = add_technical_indicators(df)

benchmark_df = None
if show_benchmark:
    bdf = extract_df(raw_data, BENCHMARK_TICKER, is_single)
    if not bdf.empty:
        benchmark_df = bdf

if not stock_data:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
    st.stop()

# ----------------------------
# 1. 요약 지표 카드 (가격 + 펀더멘털)
# ----------------------------
st.subheader("📊 종목 요약")

cols = st.columns(len(stock_data))
for i, (name, df) in enumerate(stock_data.items()):
    ticker = TICKERS[name]
    last_close = df["Close"].iloc[-1]
    prev_close = df["Close"].iloc[-2] if len(df) > 1 else last_close
    change = last_close - prev_close
    pct_change = (change / prev_close) * 100 if prev_close != 0 else 0

    fund = get_fundamentals(ticker)
    pe = fund.get("trailingPE")
    pe_str = f"{pe:.1f}" if pe else "N/A"

    with cols[i]:
        st.metric(
            label=name,
            value=f"{last_close:,.2f}",
            delta=f"{change:,.2f} ({pct_change:+.2f}%)"
        )
        st.caption(f"PER: {pe_str}")

st.markdown("---")

# ----------------------------
# 2. 개별 종목 상세 분석 (가격+이평선, 거래량, RSI)
# ----------------------------
st.subheader("📈 종목별 상세 분석")

for name, df in stock_data.items():
    ticker = TICKERS[name]
    fund = get_fundamentals(ticker)

    with st.expander(f"{name} ({ticker}) 상세 분석", expanded=True):

        # 펀더멘털 정보
        fcols = st.columns(4)
        market_cap = fund.get("marketCap")
        mc_str = f"${market_cap/1e9:,.1f}B" if market_cap else "N/A"
        fcols[0].metric("시가총액", mc_str)
        fcols[1].metric("PER (실적)", f"{fund.get('trailingPE'):.1f}" if fund.get("trailingPE") else "N/A")
        fcols[2].metric("PER (예상)", f"{fund.get('forwardPE'):.1f}" if fund.get("forwardPE") else "N/A")
        high52 = fund.get("fiftyTwoWeekHigh")
        low52 = fund.get("fiftyTwoWeekLow")
        fcols[3].metric("52주 최고/최저", f"{high52:,.1f} / {low52:,.1f}" if high52 and low52 else "N/A")

        # 가격 + 이동평균선 + 거래량 + RSI (서브플롯)
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            row_heights=[0.55, 0.2, 0.25],
            vertical_spacing=0.03,
            subplot_titles=("가격 & 이동평균선", "거래량", "RSI (14일)")
        )

        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="가격"
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df.index, y=df["MA20"], name="20일선",
            line=dict(width=1.3, color="orange")
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df.index, y=df["MA60"], name="60일선",
            line=dict(width=1.3, color="blue")
        ), row=1, col=1)

        colors = ["red" if row["Close"] >= row["Open"] else "blue" for _, row in df.iterrows()]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"], name="거래량",
            marker_color=colors, showlegend=False
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=df.index, y=df["RSI"], name="RSI",
            line=dict(width=1.5, color="purple")
        ), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

        fig.update_layout(
            height=650,
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis_rangeslider_visible=False,
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)

        # RSI 해석 문구
        last_rsi = df["RSI"].iloc[-1]
        if pd.notna(last_rsi):
            if last_rsi >= 70:
                st.warning(f"현재 RSI {last_rsi:.1f} → 과매수 구간입니다.")
            elif last_rsi <= 30:
                st.info(f"현재 RSI {last_rsi:.1f} → 과매도 구간입니다.")
            else:
                st.caption(f"현재 RSI {last_rsi:.1f} → 중립 구간입니다.")

st.markdown("---")

# ----------------------------
# 3. 종목 간 수익률 비교 (+ 벤치마크)
# ----------------------------
st.subheader("🔄 수익률 비교 (기준일=100)")

fig_compare = go.Figure()
for name, df in stock_data.items():
    normalized = (df["Close"] / df["Close"].iloc[0]) * 100
    fig_compare.add_trace(go.Scatter(
        x=df.index, y=normalized, mode="lines", name=name, line=dict(width=2)
    ))

if benchmark_df is not None:
    b_normalized = (benchmark_df["Close"] / benchmark_df["Close"].iloc[0]) * 100
    fig_compare.add_trace(go.Scatter(
        x=benchmark_df.index, y=b_normalized, mode="lines",
        name=BENCHMARK_NAME, line=dict(width=3, color="black", dash="dash")
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

# ----------------------------
# 4. 종목 간 상관관계 히트맵
# ----------------------------
if len(stock_data) > 1:
    st.subheader("🧩 종목 간 상관관계 (일별 수익률 기준)")

    returns_df = pd.DataFrame({
        name: df["Close"].pct_change() for name, df in stock_data.items()
    }).dropna()

    corr = returns_df.corr()

    fig_corr = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.columns,
        colorscale="RdBu",
        zmid=0,
        text=corr.round(2).values,
        texttemplate="%{text}",
        colorbar=dict(title="상관계수")
    ))
    fig_corr.update_layout(
        height=450,
        margin=dict(l=20, r=20, t=30, b=20),
        template="plotly_white"
    )
    st.plotly_chart(fig_corr, use_container_width=True)
    st.caption("1에 가까울수록 함께 움직이고, -1에 가까울수록 반대로 움직입니다.")

st.markdown("---")
st.caption("⚠️ 본 대시보드는 정보 제공 목적이며 투자 권유가 아닙니다. PER/시가총액 등 펀더멘털 데이터는 Yahoo Finance 기준이며 실제와 오차가 있을 수 있습니다.")
