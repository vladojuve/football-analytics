import io
import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title='Football Analytics & Scouting', page_icon='⚽', layout='wide')
st.title('⚽ Football Analytics & Scouting')
st.caption('2026/27 • Open Matchday + StatsBomb Open Data • Podaci se učitavaju sa javnih izvora')
ROOT = 'https://raw.githubusercontent.com/oladeeayo/open-matchday/master'
SB = 'https://raw.githubusercontent.com/hudl/open-data/master/data'

@st.cache_data(ttl=3600, show_spinner=False)
def get_text(url):
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    return r.text

@st.cache_data(ttl=3600, show_spinner=False)
def get_csv(url):
    try:
        return pd.read_csv(io.StringIO(get_text(url)))
    except (requests.RequestException, pd.errors.EmptyDataError):
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def get_json(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600)
def league_index():
    text = get_text(ROOT + '/LEAGUE_INDEX.md')
    rows = []
    for line in text.splitlines():
        if not line.startswith('| `'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) >= 3:
            rows.append({'folder': cells[0].strip('`'), 'league': cells[1], 'country': cells[2]})
    return pd.DataFrame(rows)

def load_matches(folder, kind):
    return get_csv(f'{ROOT}/data/{folder}/{kind}_2627.csv')

def played_table(df):
    teams = sorted(set(df['home'].dropna()) | set(df['away'].dropna()))
    rows = []
    for team in teams:
        home = df[df.home == team]
        away = df[df.away == team]
        w = int((home.ft_home > home.ft_away).sum() + (away.ft_away > away.ft_home).sum())
        d = int((home.ft_home == home.ft_away).sum() + (away.ft_away == away.ft_home).sum())
        l = len(home) + len(away) - w - d
        gf = int(home.ft_home.sum() + away.ft_away.sum())
        ga = int(home.ft_away.sum() + away.ft_home.sum())
        rows.append({'Tim':team,'U':len(home)+len(away),'P':w,'N':d,'I':l,'DG':gf,'PG':ga,'GR':gf-ga,'Bodovi':3*w+d})
    return pd.DataFrame(rows).sort_values(['Bodovi','GR','DG'],ascending=False).reset_index(drop=True)

def team_games(df, team):
    x = df[(df.home == team) | (df.away == team)].copy()
    x['Postignuti'] = x.apply(lambda r: r.ft_home if r.home == team else r.ft_away, axis=1)
    x['Primljeni'] = x.apply(lambda r: r.ft_away if r.home == team else r.ft_home, axis=1)
    x['Ishod'] = x.apply(lambda r: 'P' if r.Postignuti > r.Primljeni else ('N' if r.Postignuti == r.Primljeni else 'I'), axis=1)
    return x.sort_values('date')

try:
    leagues = league_index()
except Exception as e:
    st.error('Ne mogu da učitam indeks liga. Pokušaj ponovo kasnije.')
    st.exception(e)
    st.stop()

section = st.sidebar.radio('Izvor i analiza', ['🌍 Aktuelne lige 2026/27','🔬 StatsBomb – scouting'])
if section == '🌍 Aktuelne lige 2026/27':
    country = st.sidebar.selectbox('Država', sorted(leagues.country.unique()), index=(sorted(leagues.country.unique()).index('Austria') if 'Austria' in leagues.country.values else 0))
    available = leagues[leagues.country == country]
    chosen = st.sidebar.selectbox('Liga', available.league.tolist())
    folder = available.loc[available.league == chosen, 'folder'].iloc[0]
    st.subheader(f'{country} · {chosen} · 2026/27')
    with st.spinner('Učitavam podatke...'):
        results = load_matches(folder, 'results')
        fixtures = load_matches(folder, 'fixtures')
    if results.empty and fixtures.empty:
        st.warning('Za ovu ligu trenutno nema dostupnih redova. Probaj drugu ligu.')
        st.stop()
    if not results.empty:
        for col in ['ft_home','ft_away']:
            results[col] = pd.to_numeric(results[col], errors='coerce')
        results = results.dropna(subset=['home','away','ft_home','ft_away'])
        results = results.sort_values('date', ascending=False)
    a,b,c = st.columns(3)
    a.metric('Odigrane utakmice',len(results))
    b.metric('Zakazane utakmice',len(fixtures))
    c.metric('Timovi',len(set(results.home) | set(results.away)) if not results.empty else len(set(fixtures.home) | set(fixtures.away)))
    tabs = st.tabs(['🏆 Tabela','📅 Rezultati i raspored','📈 Analiza tima','⚔️ Poređenje timova','🎯 Statistika meča'])
    with tabs[0]:
        if not results.empty:
            st.caption('Tabela je izračunata iz dostupnih rezultata. Kod kupova i liga sa plej-ofom ne predstavlja nužno zvanični plasman.')
            st.dataframe(played_table(results), use_container_width=True, hide_index=True)
        else:
            st.info('Još nema odigranih utakmica.')
    with tabs[1]:
        if not results.empty:
            st.markdown('**Rezultati**')
            show = results[['date','gw','home','ft_home','ft_away','away']].copy()
            show.columns = ['Datum','Kolo','Domaćin','Golovi D','Golovi G','Gost']
            st.dataframe(show, use_container_width=True, hide_index=True)
        if not fixtures.empty:
            st.markdown('**Raspored**')
            cols = [x for x in ['date','time','gw','home','away'] if x in fixtures.columns]
            st.dataframe(fixtures[cols].sort_values('date'), use_container_width=True, hide_index=True)
            st.caption('Vreme početka, ako je dostupno, koristi konvenciju UTC+1 i leti može odstupati od lokalnog vremena.')
    with tabs[2]:
        if results.empty:
            st.info('Nema rezultata za analizu.')
        else:
            team = st.selectbox('Izaberi klub', sorted(set(results.home) | set(results.away)))
            tg = team_games(results,team)
            x,y,z = st.columns(3)
            x.metric('Utakmice',len(tg))
            y.metric('Golovi po utakmici',f'{tg.Postignuti.mean():.2f}')
            z.metric('Primljeni po utakmici',f'{tg.Primljeni.mean():.2f}')
            st.markdown('**Forma – poslednjih 5:** ' + '  ·  '.join(tg.tail(5).Ishod.tolist()))
            chart = tg[['date','Postignuti','Primljeni']].melt('date',var_name='Tip',value_name='Golovi')
            st.plotly_chart(px.line(chart,x='date',y='Golovi',color='Tip',markers=True,title='Golovi po utakmici'),use_container_width=True)
            st.dataframe(tg[['date','home','ft_home','ft_away','away','Ishod']].sort_values('date',ascending=False),use_container_width=True,hide_index=True)
    with tabs[3]:
        if results.empty or len(set(results.home) | set(results.away)) < 2:
            st.info('Potrebne su bar dve ekipe sa odigranim utakmicama.')
        else:
            teams = sorted(set(results.home) | set(results.away))
            t1,t2 = st.columns(2)
            first = t1.selectbox('Prvi tim',teams,index=0)
            second = t2.selectbox('Drugi tim',teams,index=1)
            compare = []
            for team in [first,second]:
                games = team_games(results,team)
                compare.append({'Tim':team,'Utakmice':len(games),'Pobede':int((games.Ishod=='P').sum()),'Bodovi':int((games.Ishod=='P').sum()*3+(games.Ishod=='N').sum()),'Golovi / meč':round(games.Postignuti.mean(),2),'Primljeni / meč':round(games.Primljeni.mean(),2)})
            st.dataframe(pd.DataFrame(compare),use_container_width=True,hide_index=True)
            st.plotly_chart(px.bar(pd.DataFrame(compare),x='Tim',y=['Golovi / meč','Primljeni / meč'],barmode='group'),use_container_width=True)
    with tabs[4]:
        if results.empty:
            st.info('Nema utakmica.')
        else:
            match_options = results.reset_index(drop=True)
            ix = st.selectbox('Utakmica',list(range(len(match_options))),format_func=lambda i: f"{match_options.iloc[i]['date']} · {match_options.iloc[i]['home']} {int(match_options.iloc[i]['ft_home'])}:{int(match_options.iloc[i]['ft_away'])} {match_options.iloc[i]['away']}")
            m = match_options.iloc[ix]
            st.markdown(f"### {m['home']} {int(m['ft_home'])} : {int(m['ft_away'])} {m['away']}")
            labels = [('Šutevi','home_shots','away_shots'),('U okvir','home_target','away_target'),('Korneri','home_corners','away_corners'),('Faulovi','home_fouls','away_fouls'),('Žuti kartoni','home_yellow','away_yellow'),('Crveni kartoni','home_red','away_red')]
            stats = []
            for name,h,a in labels:
                hv = pd.to_numeric(m.get(h),errors='coerce')
                av = pd.to_numeric(m.get(a),errors='coerce')
                if pd.notna(hv) and pd.notna(av):
                    stats.append({'Statistika':name,str(m['home']):int(hv),str(m['away']):int(av)})
            if stats:
                st.dataframe(pd.DataFrame(stats),use_container_width=True,hide_index=True)
            else:
                st.info('Za ovu utakmicu detaljna statistika nije dostupna. Prazna polja nisu nule.')
            if pd.notna(m.get('goal_minutes')) and str(m.get('goal_minutes')).strip():
                st.write('Minuti golova:',m['goal_minutes'])
    st.caption('Izvor: open-matchday (GitHub). Osvežavanje prikaza: do 1 sat. Podaci zavise od pokrivenosti i ažuriranja izvora; proveri zvanične rezultate za važne odluke.')
else:
    st.subheader('🔬 StatsBomb – detaljna analiza događaja')
    st.info('StatsBomb Open Data sadrži izabrane sezone i takmičenja, ne sve aktuelne lige 2026/27.')
    try:
        comps = pd.DataFrame(get_json(SB+'/competitions.json'))
        comps['label'] = comps['country_name'].astype(str)+' · '+comps['competition_name'].astype(str)+' · '+comps['season_name'].astype(str)
        selected = st.selectbox('Takmičenje i sezona',comps.index.tolist(),format_func=lambda i:comps.loc[i,'label'])
        cid = int(comps.loc[selected,'competition_id'])
        sid = int(comps.loc[selected,'season_id'])
        matches = pd.DataFrame(get_json(f'{SB}/matches/{cid}/{sid}.json'))
        if matches.empty:
            st.warning('Nema utakmica.')
        else:
            names = matches.apply(lambda r: f"{r['match_date']} · {r['home_team']['home_team_name']} – {r['away_team']['away_team_name']}",axis=1)
            ix = st.selectbox('Utakmica',matches.index.tolist(),format_func=lambda i:names.loc[i])
            match_id = int(matches.loc[ix,'match_id'])
            if st.button('Učitaj analizu igrača'):
                with st.spinner('Učitavam događaje...'):
                    events = get_json(f'{SB}/events/{match_id}.json')
                shot_rows = []
                for e in events:
                    if e.get('type',{}).get('name') == 'Shot':
                        shot_rows.append({'Igrač':e.get('player',{}).get('name','Nepoznato'),'Tim':e.get('team',{}).get('name',''),'xG':e.get('shot',{}).get('statsbomb_xg',0),'Ishod':e.get('shot',{}).get('outcome',{}).get('name','')})
                if shot_rows:
                    shots = pd.DataFrame(shot_rows)
                    summary = shots.groupby(['Tim','Igrač'],as_index=False).agg(Šutevi=('xG','size'),xG=('xG','sum'))
                    summary['xG'] = summary['xG'].round(3)
                    st.dataframe(summary.sort_values('xG',ascending=False),use_container_width=True,hide_index=True)
                    st.plotly_chart(px.bar(summary.sort_values('xG',ascending=False).head(20),x='Igrač',y='xG',color='Tim',title='xG po igraču'),use_container_width=True)
                else:
                    st.info('Nema dostupnih šuteva u ovom meču.')
    except Exception as e:
        st.error('StatsBomb podaci trenutno nisu dostupni za ovaj izbor.')
        st.caption(str(e))

st.sidebar.divider()
st.sidebar.caption('Izvori: open-matchday · hudl/open-data. Koristiti uz uslove i atribuciju originalnih izvora; open-matchday je namenjen nekomercijalnoj upotrebi.')
