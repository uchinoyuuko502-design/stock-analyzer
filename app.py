import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# ==========================================
# ページ設定
# ==========================================
st.set_page_config(page_title="株式分析ツール", layout="wide")

st.title("📈 株式分析ツール")

# ==========================================
# 1. 証券コードの入力
# ==========================================
st.sidebar.header("設定")
ticker_symbol = st.sidebar.text_input(
    "証券コードを入力してください (例: 7203.T, 9984.T, AAPL)", 
    value="7203.T"
)

# ==========================================
# メイン処理
# ==========================================
try:
    # 2. yfinanceで直近60日分の株価データを取得
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(period="60d")

    if df.empty:
        st.error(f"証券コード '{ticker_symbol}' のデータが取得できませんでした。コードが正しいか確認してください。")
    else:
        # 4. 移動平均線の計算 (MA5, MA25)
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA25'] = df['Close'].rolling(window=25).mean()

        # 6. RSI（14日）を計算
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # レイアウト作成
        col_main, col_side = st.columns([3, 1])

        with col_main:
            # 3, 5. ローソク足チャート + 出来高バーチャート
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.1, 
                row_heights=[0.7, 0.3],
                subplot_titles=("株価チャート (MA5, MA25)", "出来高")
            )

            # ローソク足 (陽線: 緑, 陰線: 赤)
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name="ローソク足",
                increasing_line_color='green',
                decreasing_line_color='red'
            ), row=1, col=1)

            # 移動平均線 MA5
            fig.add_trace(go.Scatter(
                x=df.index, y=df['MA5'], 
                name="MA5", 
                line=dict(color='blue', width=1.5)
            ), row=1, col=1)

            # 移動平均線 MA25
            fig.add_trace(go.Scatter(
                x=df.index, y=df['MA25'], 
                name="MA25", 
                line=dict(color='orange', width=1.5)
            ), row=1, col=1)

            # 出来高
            fig.add_trace(go.Bar(
                x=df.index, y=df['Volume'], 
                name="出来高", 
                marker_color='rgba(128, 128, 128, 0.5)'
            ), row=2, col=1)

            fig.update_layout(
                height=600, 
                xaxis_rangeslider_visible=False,
                showlegend=True,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

            # RSIグラフ
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(
                x=df.index, y=df['RSI'], 
                name="RSI", 
                line=dict(color='purple')
            ))
            # 境界線 (70, 30)
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="70 (買われすぎ)")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="30 (売られすぎ)")
            
            fig_rsi.update_layout(
                title="RSI (14日)", 
                height=300, 
                yaxis=dict(range=[0, 100]),
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_rsi, use_container_width=True)

        with col_side:
            st.subheader("📊 テクニカル判定")
            
            # 7. 移動平均線の判定
            last_ma5 = df['MA5'].iloc[-1]
            last_ma25 = df['MA25'].iloc[-1]
            if pd.isna(last_ma5) or pd.isna(last_ma25):
                st.info("トレンド判定: データ不足")
            elif last_ma5 > last_ma25:
                st.success("📈 上昇トレンド\n(MA5 > MA25)")
            else:
                st.error("📉 下降トレンド\n(MA5 < MA25)")

            # 6. RSIの判定
            last_rsi = df['RSI'].iloc[-1]
            if pd.isna(last_rsi):
                st.info("RSI判定: データ不足")
            elif last_rsi >= 70:
                st.markdown(f"RSI: <span style='color:red; font-weight:bold;'>{last_rsi:.2f} (買われすぎ)</span>", unsafe_allow_html=True)
            elif last_rsi <= 30:
                st.markdown(f"RSI: <span style='color:green; font-weight:bold;'>{last_rsi:.2f} (売られすぎ)</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"RSI: <span style='color:blue; font-weight:bold;'>{last_rsi:.2f} (中立)</span>", unsafe_allow_html=True)

            st.divider()
            
            # 8, 9. ファンダメンタル指標
            st.subheader("💎 ファンダメンタル")
            info = ticker.info
            
            def display_metric(label, value, thresholds):
                """指標を表示し、判定コメントを色付きで追加する"""
                if value == "データなし" or value is None:
                    st.write(f"{label}: データなし")
                    return

                comment = thresholds['normal']['text']
                color = thresholds['normal']['color']

                if 'low' in thresholds and value <= thresholds['low']['val']:
                    comment = thresholds['low']['text']
                    color = thresholds['low']['color']
                elif 'high' in thresholds and value >= thresholds['high']['val']:
                    comment = thresholds['high']['text']
                    color = thresholds['high']['color']
                
                # 特殊な判定ロジック (ROEなど)
                if label == "ROE":
                    val_pct = value * 100
                    if val_pct >= 15: comment, color = "優良", "green"
                    elif val_pct < 8: comment, color = "低水準", "red"
                    else: comment, color = "標準", "black"
                    st.markdown(f"{label}: **{val_pct:.2f}%** (<span style='color:{color};'>{comment}</span>)", unsafe_allow_html=True)
                else:
                    st.markdown(f"{label}: **{value:.2f}** (<span style='color:{color};'>{comment}</span>)", unsafe_allow_html=True)

            # PER
            display_metric("PER", info.get('trailingPE'), {
                'low': {'val': 15, 'text': '割安', 'color': 'green'},
                'high': {'val': 25, 'text': '割高', 'color': 'red'},
                'normal': {'text': '適正', 'color': 'black'}
            })

            # PBR
            display_metric("PBR", info.get('priceToBook'), {
                'low': {'val': 1, 'text': '割安', 'color': 'green'},
                'high': {'val': 3, 'text': '割高', 'color': 'red'},
                'normal': {'text': '適正', 'color': 'black'}
            })

            # ROE
            display_metric("ROE", info.get('returnOnEquity'), {
                'normal': {'text': '標準', 'color': 'black'}
            })

            # 自己資本比率
            try:
                # バランスシートから計算
                bs = ticker.balance_sheet
                if not bs.empty:
                    total_assets = bs.loc['Total Assets'].iloc[0]
                    total_equity = bs.loc['Stockholders Equity'].iloc[0]
                    equity_ratio = (total_equity / total_assets) * 100
                    
                    if equity_ratio >= 40: comment, color = "健全", "green"
                    else: comment, color = "要確認", "orange"
                    
                    st.markdown(f"自己資本比率: **{equity_ratio:.2f}%** (<span style='color:{color};'>{comment}</span>)", unsafe_allow_html=True)
                else:
                    st.write("自己資本比率: データなし")
            except:
                st.write("自己資本比率: データなし")

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
    st.info("証券コードが正しいか、またはネットワーク接続を確認してください。")

# ==========================================
# Streamlit設定 (末尾に必ず追加)
# ==========================================
if __name__ == "__main__":
    # AI Studio環境ではポート3000を使用する必要がありますが、
    # ローカル実行時は 8501 等お好みのポートに変更可能です。
    os.system("streamlit run app.py --server.port=3000 --server.address=0.0.0.0")
