
import streamlit as st
import pandas as pd
import requests
import plotly.express as px

BASE = "https://raw.githubusercontent.com/hudl/open-data/master/data"
API = "https://api.github.com/repos/hudl/open-data/contents/data"

st.set_page_config(
    page_title="Football Analytics",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Football Analytics & Scouting")
st.caption("Powered by StatsBomb Open Data")

@st.cache_data(ttl=3600)
def get_json(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=3600)
def get_competitions():
    return get_json(f"{BASE}/competitions.json")

@st.cache_data(ttl=3600)
def get_matches(comp_id, season_id):
    url = f"{BASE}/matches/{comp_id}/{season_id}.json"
    return get_json(url)

@st.cache_data(ttl=3600)
def get_events(match_id):
    return get_json(f"{BASE}/events/{match_id}.json")

try:
    competitions = pd.DataFrame(get_competitions())

    st.sidebar.header("Izbor takmičenja")

    countries = sorted(
        competitions["country_name"].dropna().unique()
    )

    country = st.sidebar.selectbox("Država", countries)

    comp_data = competitions[
        competitions["country_name"] == country
    ]

    comp_names = sorted(
        comp_data["competition_name"].dropna().unique()
    )

    comp_name = st.sidebar.selectbox(
        "Takmičenje", comp_names
    )

    selected_comp = comp_data[
        comp_data["competition_name"] == comp_name
    ]

    seasons = selected_comp[
        ["season_id", "season_name"]
    ].drop_duplicates()

    seasons["season_name"] = seasons["season_name"].astype(str)

    season_name = st.sidebar.selectbox(
        "Sezona",
        sorted(seasons["season_name"].unique(), reverse=True)
    )

    season_id = int(
        seasons[seasons["season_name"] == season_name]
        .iloc[0]["season_id"]
    )

    comp_id = int(selected_comp.iloc[0]["competition_id"])

    st.subheader(f"{comp_name} — {season_name}")

    with st.spinner("Učitavam utakmice..."):
        matches = get_matches(comp_id, season_id)

    df = pd.DataFrame(matches)

    if df.empty:
        st.warning("Nema dostupnih utakmica za ovaj izbor.")
    else:
        home = df["home_team"].apply(
            lambda x: x.get("home_team_name", "")
        )
        away = df["away_team"].apply(
            lambda x: x.get("away_team_name", "")
        )

        home_score = df["home_score"].fillna("-")
        away_score = df["away_score"].fillna("-")

        df["Utakmica"] = (
            home + " " + home_score.astype(str)
            + " : " + away_score.astype(str) + " " + away
        )

        if "match_date" in df:
            df = df.sort_values("match_date", ascending=False)

        st.metric("Broj dostupnih utakmica", len(df))

        st.subheader("Rezultati i utakmice")
        st.dataframe(
            df[["match_date", "Utakmica"]],
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Analiza utakmice")

        selected_match = st.selectbox(
            "Izaberi utakmicu",
            df["Utakmica"].tolist()
        )

        match_id = int(
            df.loc[df["Utakmica"] == selected_match, "match_id"].iloc[0]
        )

        with st.spinner("Učitavam događaje utakmice..."):
            events = pd.DataFrame(get_events(match_id))

        if not events.empty and "type" in events.columns:
            shots = events[
                events["type"].apply(
                    lambda x: isinstance(x, dict)
                    and x.get("name") == "Shot"
                )
            ].copy()

            if not shots.empty:
                shots["xG"] = shots["shot"].apply(
                    lambda x: x.get("statsbomb_xg")
                    if isinstance(x, dict) else None
                )

                shots["Igrač"] = shots["player"].apply(
                    lambda x: x.get("name", "")
                    if isinstance(x, dict) else ""
                )

                shots["Tim"] = shots["team"].apply(
                    lambda x: x.get("name", "")
                    if isinstance(x, dict) else ""
                )

                col1, col2 = st.columns(2)
                col1.metric("Broj šuteva", len(shots))
                col2.metric(
                    "Ukupni xG",
                    f"{shots['xG'].sum():.2f}"
                )

                st.subheader("Šutevi i xG")
                st.dataframe(
                    shots[["minute", "Igrač", "Tim", "xG"]],
                    use_container_width=True,
                    hide_index=True
                )

                st.subheader("xG po igračima")
                player_xg = (
                    shots.groupby("Igrač")["xG"]
                    .sum()
                    .sort_values(ascending=False)
                    .reset_index()
                )

                fig = px.bar(
                    player_xg,
                    x="Igrač",
                    y="xG",
                    title="Ukupni xG po igračima"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Za ovu utakmicu nema dostupnih podataka o šutevima.")
        else:
            st.warning("Događaji utakmice nisu dostupni.")

except Exception as error:
    st.error("Greška pri učitavanju podataka.")
    st.caption(str(error))
    st.info("Proveri vezu sa internetom i pokušaj ponovo.")
