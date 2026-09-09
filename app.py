import streamlit as st
import asyncio
from pathlib import Path
import tempfile
import zipfile
import os
import io

# 確保在 Streamlit Cloud 環境中自動安裝 Playwright 瀏覽器引擎
os.system("playwright install chromium")

from screenshot import MARKET_GROUPS, PERIODS, run_screenshots

st.set_page_config(page_title="玩股網自動截圖", page_icon="📈", layout="wide")

st.title("📈 玩股網 國際指數自動截圖")
st.markdown("這個工具可以自動開啟玩股網，並截取指定國家指數的技術線圖。")

# --- 狀態初始化 ---
if "select_all_markets" not in st.session_state:
    st.session_state.select_all_markets = True

if "select_all_periods" not in st.session_state:
    st.session_state.select_all_periods = True

for group, markets in MARKET_GROUPS.items():
    for m in markets:
        market_id = m[0]
        if f"market_{market_id}" not in st.session_state:
            st.session_state[f"market_{market_id}"] = True

for p in PERIODS:
    suffix = p[0]
    if f"period_{suffix}" not in st.session_state:
        st.session_state[f"period_{suffix}"] = True

def toggle_all_markets():
    val = st.session_state.select_all_markets
    for group, markets in MARKET_GROUPS.items():
        for m in markets:
            st.session_state[f"market_{m[0]}"] = val

def toggle_all_periods():
    val = st.session_state.select_all_periods
    for p in PERIODS:
        st.session_state[f"period_{p[0]}"] = val

# 側邊欄配置
with st.sidebar:
    st.header("⚙️ 參數設定")
    
    st.subheader("1. 選擇指數")
    st.checkbox("✅ 全選所有指數", key="select_all_markets", on_change=toggle_all_markets)
    st.divider()
    
    selected_markets = []
    
    for group, markets in MARKET_GROUPS.items():
        st.markdown(f"**{group}**")
        for m in markets:
            market_id, market_name, url = m
            if st.checkbox(market_name, key=f"market_{market_id}"):
                selected_markets.append(m)
        st.write("") # 增加一點間距

    st.subheader("2. 選擇週期")
    st.checkbox("✅ 全選所有週期", key="select_all_periods", on_change=toggle_all_periods)
    st.divider()
    
    selected_periods = []
    for p in PERIODS:
        suffix, period_text = p
        if st.checkbox(period_text, key=f"period_{suffix}"):
            selected_periods.append(p)

# 主畫面操作
if not selected_markets or not selected_periods:
    st.warning("請至少選擇一個指數與一個週期。")
else:
    if st.button("🚀 開始執行截圖", type="primary", use_container_width=True):
        
        # 建立暫存資料夾來存放截圖
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # 用來顯示狀態的容器
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            # 自訂的狀態回呼函數
            def update_status(msg):
                status_placeholder.info(msg)
                
            with st.spinner("正在啟動無頭瀏覽器與截圖引擎..."):
                try:
                    # Streamlit 是同步環境，我們需要透過 asyncio.run 來執行非同步的截圖函數
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None

                    if loop and loop.is_running():
                        import nest_asyncio
                        nest_asyncio.apply()
                        generated_files = asyncio.run(run_screenshots(selected_markets, selected_periods, tmp_path, update_status))
                    else:
                        generated_files = asyncio.run(run_screenshots(selected_markets, selected_periods, tmp_path, update_status))
                    
                    status_placeholder.success(f"✅ 截圖完成！共產生 {len(generated_files)} 張圖片。")
                    progress_bar.progress(100)
                    
                    if generated_files:
                        st.subheader("🖼️ 截圖結果")
                        
                        # 打包成 ZIP
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                            for file_path in generated_files:
                                zip_file.write(file_path, arcname=file_path.name)
                                
                        st.download_button(
                            label="📦 下載全部截圖 (ZIP)",
                            data=zip_buffer.getvalue(),
                            file_name="screenshots.zip",
                            mime="application/zip",
                            type="primary",
                            use_container_width=True
                        )
                        
                        st.divider()
                        
                        # 顯示圖片 Gallery，分為幾列顯示
                        cols = st.columns(3)
                        for idx, file_path in enumerate(generated_files):
                            with cols[idx % 3]:
                                st.image(str(file_path), caption=file_path.name, use_container_width=True)
                                
                                # 單張下載
                                with open(file_path, "rb") as f:
                                    st.download_button(
                                        label="下載",
                                        data=f,
                                        file_name=file_path.name,
                                        mime="image/png",
                                        key=f"dl_{file_path.name}"
                                    )
                                    
                except Exception as e:
                    st.error(f"執行時發生錯誤: {str(e)}")
                    st.exception(e)
