from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="서울시 전동킥보드 견인 현황", layout="wide")

DATA_PATH = Path(__file__).parent / "towing.csv"
BAR_COLOR = "#2a6fdb"


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, encoding="cp949")
    df["신고일시"] = pd.to_datetime(df["신고일시"])
    # 조치일에 "1900-01-00" 같은 잘못된 값이 있어 NaT로 처리
    df["조치일"] = pd.to_datetime(df["조치일"], errors="coerce")
    # 구정보 컬럼은 깨져 있어 주소에서 재추출
    df["구"] = df["주소"].str.extract(r"서울특별시\s+(\S+구)")
    # 유형: 2024년 라벨 개편으로 같은 장소가 다른 이름으로 기록되어 있어 키워드로 통합
    # 우선순위가 낮은 것부터 덮어써서, 마지막에 쓴 것이 우선한다 (예: '횡단보도'는 '보도'보다 우선)
    df["유형정리"] = "기타"
    df.loc[df["유형"].str.contains("교통섬", na=False), "유형정리"] = "교통섬"
    df.loc[df["유형"].str.contains("건물, 상가", na=False), "유형정리"] = "건물·상가 진출입"
    df.loc[df["유형"].str.contains("보도", na=False), "유형정리"] = "보도"
    df.loc[df["유형"].str.contains("차도", na=False), "유형정리"] = "차도"
    df.loc[df["유형"].str.contains("자전거", na=False), "유형정리"] = "자전거도로"
    df.loc[df["유형"].str.contains("보호구역", na=False), "유형정리"] = "보호구역"
    df.loc[df["유형"].str.contains("보호 구역", na=False), "유형정리"] = "보호구역"
    df.loc[df["유형"].str.contains("교통약자", na=False), "유형정리"] = "점자블록·교통약자"
    df.loc[df["유형"].str.contains("점자", na=False), "유형정리"] = "점자블록·교통약자"
    df.loc[df["유형"].str.contains("지하철", na=False), "유형정리"] = "지하철역"
    df.loc[df["유형"].str.contains("택시", na=False), "유형정리"] = "버스·택시"
    df.loc[df["유형"].str.contains("버스", na=False), "유형정리"] = "버스·택시"
    df.loc[df["유형"].str.contains("횡단보도", na=False), "유형정리"] = "횡단보도"
    df["연도"] = df["신고일시"].dt.year
    df["월번호"] = df["신고일시"].dt.month
    df["처리기간"] = (df["조치일"] - df["신고일시"]).dt.days
    return df


df = load_data()

# ---------------- 사이드바 ----------------
st.sidebar.header("필터")
y_min, y_max = int(df["연도"].min()), int(df["연도"].max())
year_range = st.sidebar.slider("기간(연도)", y_min, y_max, (y_min, y_max))

gu_all = sorted(df["구"].dropna().unique())
gu_sel = st.sidebar.multiselect("자치구", gu_all, default=gu_all)

type_order = df["유형정리"].value_counts().index.tolist()
type_order = [t for t in type_order if t != "기타"] + (["기타"] if "기타" in type_order else [])
type_sel = st.sidebar.multiselect("견인유형", type_order, default=type_order)

# ---------------- 필터 적용 ----------------
f = df[
    df["연도"].between(*year_range)
    & df["구"].isin(gu_sel)
    & df["유형정리"].isin(type_sel)
]

# ---------------- 제목 + KPI ----------------
st.title("서울시 전동킥보드 견인 현황")

if f.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다. 필터를 조정해 주세요.")
else:
    by_gu = f["구"].value_counts()
    c1, c2, c3 = st.columns(3)
    c1.metric("총 견인 건수", f"{len(f):,}건")
    c2.metric("평균 처리기간", f"{f['처리기간'].mean():.2f}일")
    c3.metric("견인 1위 자치구", f"{by_gu.index[0]} ({by_gu.iloc[0]:,}건)")

    def kr(n):
        """숫자를 한국어 단위로: 43024 -> '4만 3,024' """
        n = int(n)
        return f"{n // 10000}만 {n % 10000:,}" if n >= 10000 else f"{n:,}"

    def kr_axis(fig, series):
        """y축 눈금을 '2만', '4만'처럼 한국어 단위로"""
        top = series.max()
        step = max(1, int(top / 5))
        mag = 10 ** (len(str(step)) - 1)
        step = max(mag, round(step / mag) * mag)
        vals = list(range(0, int(top * 1.1) + step, step))
        fig.update_yaxes(
            tickvals=vals,
            ticktext=[f"{v / 10000:g}만" if v >= 10000 else f"{v:,}" for v in vals],
        )

    def style(fig, xtitle, ytitle):
        fig.update_layout(
            template="plotly_white",
            font=dict(family="Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, sans-serif"),
            xaxis_title=xtitle,
            yaxis_title=ytitle,
            margin=dict(t=50, b=40),
        )
        return fig

    # ① 연도별 + 전년 대비 증감률
    yr = f.groupby("연도").size().reset_index(name="건수")
    yr["증감률"] = yr["건수"].pct_change() * 100
    yr["라벨"] = [
        f"{kr(n)}건" if pd.isna(p) else f"{kr(n)}건<br>{p:+.0f}%"
        for n, p in zip(yr["건수"], yr["증감률"])
    ]
    fig6 = px.bar(yr, x="연도", y="건수", text="라벨", title="① 연도별 견인 건수와 전년 대비 증감률")
    fig6.update_traces(marker_color=BAR_COLOR, textposition="outside", cliponaxis=False,
                       customdata=yr["건수"].map(kr), hovertemplate="%{x}년<br>건수=%{customdata}건<extra></extra>")
    fig6.update_xaxes(type="category")
    kr_axis(fig6, yr["건수"] * 1.15)
    st.plotly_chart(style(fig6, "연도", "견인 건수"), width="stretch")
    st.caption("2021년은 7월 15일부터의 반년치라, 2022년 증감률은 과대하게 보일 수 있습니다. 선택한 첫 해는 비교 대상이 없어 증감률을 표시하지 않습니다.")

    # ② 연도별 겹쳐 그린 월별 선 (계절성·연도 간 비교)
    ym = f.groupby(["연도", "월번호"]).size().reset_index(name="건수")
    ym["연도"] = ym["연도"].astype(str)
    year_colors = {"2021": "#8fa3ad", "2022": "#e0a030", "2023": "#2a9d8f", "2024": "#2a6fdb", "2025": "#d1495b"}
    fig4 = px.line(
        ym, x="월번호", y="건수", color="연도", markers=True,
        color_discrete_map=year_colors,
        title="② 연도별 월별 견인 비교 (같은 달끼리 겹쳐 보기)",
    )
    fig4.update_traces(
        line_width=2,
        customdata=ym["건수"].map(kr),
        hovertemplate="%{fullData.name}년 %{x}월<br>건수=%{customdata}건<extra></extra>",
    )
    fig4.update_xaxes(tickmode="array", tickvals=list(range(1, 13)), ticktext=[f"{m}월" for m in range(1, 13)])
    kr_axis(fig4, ym["건수"])
    st.plotly_chart(style(fig4, "신고월", "견인 건수"), width="stretch")
    st.caption("2021년은 7월 15일부터 집계되어 7월은 반달치, 1~6월은 없습니다.")

    # ③ 자치구별
    gu_cnt = f.groupby("구", as_index=False).size().sort_values("size", ascending=False)
    fig2 = px.bar(gu_cnt, x="구", y="size", title="③ 자치구별 견인 건수")
    fig2.update_traces(
        marker_color=BAR_COLOR,
        customdata=gu_cnt["size"].map(kr), hovertemplate="%{x}<br>건수=%{customdata}건<extra></extra>",
    )
    kr_axis(fig2, gu_cnt["size"])
    st.plotly_chart(style(fig2, "자치구", "견인 건수"), width="stretch")

    # ④ 유형별
    t_cnt = f.groupby("유형정리", as_index=False).size().sort_values("size", ascending=False)
    fig3 = px.bar(t_cnt, x="유형정리", y="size", title="④ 견인유형별 건수")
    # 기타에 마우스를 올리면 무엇이 들어 있는지 괄호로 설명
    t_cnt["설명"] = t_cnt["유형정리"].map({"기타": " (원본의 '그 외 지역'·'기타', 자유서술 민원 문구 등)"}).fillna("")
    t_cnt["건수글자"] = t_cnt["size"].map(kr)
    fig3.update_traces(
        marker_color=BAR_COLOR,
        customdata=t_cnt[["건수글자", "설명"]],
        hovertemplate="%{x}%{customdata[1]}<br>건수=%{customdata[0]}건<extra></extra>",
    )
    kr_axis(fig3, t_cnt["size"])
    st.plotly_chart(style(fig3, "견인유형", "견인 건수"), width="stretch")

# ---------------- 각주 ----------------
st.divider()
st.caption(
    "**출처**: 서울 열린데이터광장 '서울시 전동킥보드 견인현황' · "
    "**집계기준**: 견인 1건 = 1행, 신고일 기준 · "
    "**견인유형**: 원본 1,477종을 키워드로 11개 묶음(기타 포함)으로 통합"
)
