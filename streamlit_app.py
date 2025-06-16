import streamlit as st
import graphviz
import re
import tempfile
import pdfkit
from collections import defaultdict

# === Konstante Styles ===
PRIMARY_COLOR = "#d22332"
FONT_FAMILY = "Tahoma, sans-serif"

# === Streamlit-Page-Config und CSS ===
st.set_page_config(page_title="Wegzugssteuer KI-Tool", layout="wide")

st.markdown(f"""
    <style>
    html, body, [class*="css"] {{
        font-family: {FONT_FAMILY}, sans-serif;
        font-size: 11pt !important;
    }}
    h1, h2, h3, h4, h5, h6 {{
        font-size: 11pt !important;
    }}
    .red-text {{
        color: {PRIMARY_COLOR};
        font-style: italic;
    }}
    </style>
""", unsafe_allow_html=True)

# === Hilfsfunktionen ===
@st.cache_data
def parse_beteiligungen(text):
    dot = graphviz.Digraph()
    dot.attr(rankdir='TB', size='3,3', dpi='72', nodesep='0.1', ranksep='0.1', splines='ortho', bgcolor='white')
    node_width = "1.2"
    node_height = "0.6"
    nodes = {}
    children = defaultdict(list)

    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r"(?P<von>.+?) an (?P<an>.+?)\s*(\((?P<sitz>.*?)\))?\s*(?P<proz>\d+)%?", line)
        if match:
            von = match.group('von').strip()
            an = match.group('an').strip()
            sitz = match.group('sitz').strip() if match.group('sitz') else None
            proz = match.group('proz').strip()
            for node in [von, an]:
                if node not in nodes:
                    is_company = "GmbH" in node or "KG" in node
                    shape = "ellipse" if "KG" in node else "box" if "GmbH" in node else "none"
                    label = f"👤\n{node}" if not is_company else f"{node}\n({sitz})" if sitz else node
                    style = "filled" if is_company else ""
                    fillcolor = PRIMARY_COLOR if is_company else ""
                    color = PRIMARY_COLOR if is_company else ""
                    fontcolor = "white" if is_company else "black"
                    dot.node(
                        node,
                        label=label,
                        shape=shape,
                        style=style,
                        fillcolor=fillcolor,
                        color=color,
                        fontcolor=fontcolor,
                        width=node_width,
                        height=node_height,
                        fixedsize="true",
                    )
                    nodes[node] = True
            children[von].append((an, proz))
    for parent, kids in children.items():
        if len(kids) == 1:
            an, proz = kids[0]
            dot.edge(parent, an, label=f"{proz}%", dir="none", minlen='1')
        else:
            junction = f"junction_{parent}"
            dot.node(junction, label='', shape='point', width='0.01', height='0.01', fixedsize='true', style='invis')
            dot.edge(parent, junction, dir="none", minlen='1')
            for an, proz in kids:
                dot.edge(junction, an, label=f"{proz}%", dir="none", minlen='1')
    return dot


def generate_fliestext(text):
    participations = defaultdict(list)
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r"(?P<von>.+?) an (?P<an>.+?)\s*(\((?P<sitz>.*?)\))?\s*(?P<proz>\d+)%?", line)
        if match:
            von = match.group('von').strip()
            an = match.group('an').strip()
            sitz = match.group('sitz').strip() if match.group('sitz') else None
            proz = match.group('proz').strip()
            sitz_info = f" mit Sitz in {sitz}" if sitz else ""
            if proz == "100":
                baustein = f"hält sämtliche Anteile an der {an}{sitz_info}"
            else:
                baustein = f"ist zu {proz}% an der {an}{sitz_info} beteiligt"
            participations[von].append(baustein)
    sentences = []
    for von, liste in participations.items():
        if len(liste) == 1:
            sentences.append(f"{von} {liste[0]}.")
        elif len(liste) == 2:
            sentences.append(f"{von} {liste[0]} sowie {liste[1]}.")
        else:
            last = liste.pop()
            sentences.append(f"{von} {', '.join(liste)} sowie {last}.")
    return " ".join(sentences)


def generate_persverh_text(text):
    lines = text.strip().split('\n')
    stichpunkte = [line.lstrip('- ').strip() for line in lines if line.strip()]
    if not stichpunkte:
        return "Keine persönlichen Verhältnisse angegeben."
    elif len(stichpunkte) == 1:
        return f"Der Mandant ist {stichpunkte[0]}."
    else:
        return f"Der Mandant ist {', '.join(stichpunkte[:-1])} sowie {stichpunkte[-1]}."


# === Titel und Beschreibung ===
st.title("📍 KI-Tool zur Vermeidung der Wegzugs- und Entstrickungsbesteuerung")
st.markdown(
    "Dieses Tool analysiert auf Basis Ihrer Eingaben steuerliche Risiken eines Wegzugs und zeigt rechtssichere Gestaltungsoptionen auf – inklusive Strukturdiagramm, Sperrfristen und Unternehmensstruktur."
)

# === Sidebar ===
st.sidebar.header("Mandanteninfos")
name = st.sidebar.text_input("Vor- und Nachname")
initialen = "".join([teil[0].upper() for teil in name.strip().split() if teil]) if name else "Mandant"

st.sidebar.header("Persönliche Verhältnisse")
pers_verh_text = st.sidebar.text_area(
    "Persönliche Verhältnisse (Stichpunkte)",
    value="- Verheiratet\n- 2 Kinder\n- Steuerpflicht in Deutschland",
    height=150,
)

st.sidebar.header("Unternehmensvermögen")
default_beteiligungen = """A an B GmbH (Deutschland) 100%
B GmbH an C GmbH (Schweiz) 5%
B GmbH an D KG (Liechtenstein) 99%"""
beteiligungstext = st.sidebar.text_area(
    "Unternehmensstruktur (Stichpunkte)",
    value=default_beteiligungen.strip(),
    height=200,
)

st.sidebar.header("Mandantensachverhalt")
dba_status = st.sidebar.radio(
    "Zielland des Wegzugs", ["DBA-Staat(en)", "Nicht-DBA-Staat", "offen"]
)

dba_staaten = [
    "Ägypten",
    "Albanien",
    "Algerien",
    "Andorra",
    "Argentinien",
    "Armenien",
    "Aserbaidschan",
    "Australien",
    "Bangladesch",
    "Belarus",
    "Belgien",
    "Bolivien",
    "Bosnien und Herzegowina",
    "Brasilien",
    "Bulgarien",
    "China",
    "Costa Rica",
    "Dänemark",
    "Ecuador",
    "Elfenbeinküste",
    "Estland",
    "Finnland",
    "Frankreich",
    "Georgien",
    "Ghana",
    "Griechenland",
    "Großbritannien",
    "Hongkong",
    "Indien",
    "Indonesien",
    "Iran",
    "Irland",
    "Island",
    "Israel",
    "Italien",
    "Jamaika",
    "Japan",
    "Jersey",
    "Kanada",
    "Kasachstan",
    "Kenia",
    "Kirgisistan",
    "Kolumbien",
    "Korea, Republik",
    "Kosovo",
    "Kroatien",
    "Kuwait",
    "Lettland",
    "Liberia",
    "Liechtenstein",
    "Litauen",
    "Luxemburg",
    "Malaysia",
    "Malta",
    "Marokko",
    "Mauritius",
    "Mexiko",
    "Moldau",
    "Mongolei",
    "Montenegro",
    "Namibia",
    "Neuseeland",
    "Niederlande",
    "Norwegen",
    "Österreich",
    "Pakistan",
    "Philippinen",
    "Polen",
    "Portugal",
    "Rumänien",
    "Russland",
    "Sambia",
    "Saudi-Arabien",
    "Schweden",
    "Schweiz",
    "Serbien",
    "Singapur",
    "Slowakei",
    "Slowenien",
    "Spanien",
    "Sri Lanka",
    "Südafrika",
    "Südkorea",
    "Taiwan",
    "Tadschikistan",
    "Thailand",
    "Trinidad und Tobago",
    "Tschechien",
    "Tunesien",
    "Türkei",
    "Turkmenistan",
    "Ukraine",
    "Ungarn",
    "Uruguay",
    "Usbekistan",
    "Venezuela",
    "Vereinigte Arabische Emirate",
    "Vereinigte Staaten",
    "Vietnam",
    "Zypern",
]
ziellaender = (
    st.sidebar.multiselect(
        "Zielland/Zielländer (Mehrfachauswahl möglich)", options=dba_staaten
    )
    if dba_status == "DBA-Staat(en)"
    else [dba_status]
)

st.sidebar.header("Darzustellende Lösungsansätze")
struktur_auswahl = []
loesung_options = [
    '"Flucht" ins Betriebsvermögen',
    "die deutsche Familienstiftung",
    "die liechtensteinische Familienstiftung",
    'der "Nicht-DBA-Umzug"',
]
for option in loesung_options:
    if st.sidebar.checkbox(option):
        struktur_auswahl.append(option)

st.sidebar.header("Darstellungsoptionen")
darstellungsoption = st.sidebar.radio(
    "Bitte wählen Sie eine Darstellungsoption:",
    (
        "Nur Grafiken",
        "Grafiken mit kurzer Beschreibung, ohne (steuer-)rechtliche Hinweise",
        "Gesamtes Papier, inkl. aller rechtlichen Ausführungen",
    ),
)

# === Hauptansicht ===
if st.button("🔍 Analyse starten"):
    st.markdown("### 1. Sachverhalt")
    if darstellungsoption in [
        "Grafiken mit kurzer Beschreibung, ohne (steuer-)rechtliche Hinweise",
        "Gesamtes Papier, inkl. aller rechtlichen Ausführungen",
    ]:
        st.markdown("#### 1.1. Status quo")
        st.markdown(
            f"<span class='red-text'>Persönliche Situation / Familienverhältnisse</span>",
            unsafe_allow_html=True,
        )
        st.markdown(generate_persverh_text(pers_verh_text))
        st.markdown(
            f"<span class='red-text'>Gesellschaftsrechtliche Verhältnisse / Unternehmensvermögen</span>",
            unsafe_allow_html=True,
        )
        st.markdown(generate_fliestext(beteiligungstext))

    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        st.graphviz_chart(
            parse_beteiligungen(beteiligungstext), use_container_width=True
        )

    if darstellungsoption == "Gesamtes Papier, inkl. aller rechtlichen Ausführungen":
        st.markdown("#### 1.2. Planung")
        st.markdown(
            "- Der Mandant plant einen Wegzug ins Ausland, um die Wegzugsbesteuerung zu vermeiden oder zu reduzieren.\n- Derzeit ist der Mandant in Deutschland unbeschränkt steuerpflichtig."
        )
        st.markdown("### 2. Fragestellung")
        st.markdown(
            "- Wie kann eine Wegzugsbesteuerung vermieden oder aufgeschoben werden?\n- Welche rechtssicheren Gestaltungsoptionen gibt es?"
        )
        st.markdown("### 3. Zusammenfassung")
        st.markdown(
            "Das Tool analysiert die steuerlichen Risiken eines Wegzugs ins Ausland und stellt rechtssichere Gestaltungsoptionen dar. Im Fokus stehen steuerliche Folgen und Empfehlungen für verschiedene Gestaltungswege."
        )
        st.markdown("### 4. Steuerliche Implikationen eines Wegzugs")
        st.markdown(
            "- Wegzugsbesteuerung nach § 6 AStG bei Anteilen an Kapitalgesellschaften."
        )
        st.markdown(
            "- Entstrickungsbesteuerung bei Mitunternehmeranteilen (§ 4 Abs. 1 Satz 3 EStG)."
        )
        st.markdown(
            "- Sofortbesteuerung bei Wegzug in Nicht-DBA-Staaten ohne Stundungsmöglichkeiten."
        )

    if st.button("📥 Export als PDF"):
        html_content = (
            f"""<html><head><meta charset=\"UTF-8\"><style>body {{font-family: {FONT_FAMILY}; font-size: 11pt; color: black;}} h1, h2, h3 {{color: {PRIMARY_COLOR};}}</style></head><body><h1>Analysebericht</h1><h2>1. Sachverhalt</h2>"""
        )
        if darstellungsoption in [
            "Grafiken mit kurzer Beschreibung, ohne (steuer-)rechtliche Hinweise",
            "Gesamtes Papier, inkl. aller rechtlichen Ausführungen",
        ]:
            html_content += f"<h3>1.1. Status quo</h3><strong>Persönliche Situation / Familienverhältnisse:</strong><p>{generate_persverh_text(pers_verh_text)}</p><strong>Gesellschaftsrechtliche Verhältnisse / Unternehmensvermögen:</strong><p>{generate_fliestext(beteiligungstext)}</p>"
        if darstellungsoption == "Gesamtes Papier, inkl. aller rechtlichen Ausführungen":
            html_content += (
                "<h3>1.2. Planung</h3><p>Der Mandant plant einen Wegzug ins Ausland, um die Wegzugsbesteuerung zu vermeiden oder zu reduzieren. Derzeit ist der Mandant in Deutschland unbeschränkt steuerpflichtig.</p><h2>2. Fragestellung</h2><p>Wie kann eine Wegzugsbesteuerung vermieden oder aufgeschoben werden? Welche rechtssicheren Gestaltungsoptionen gibt es?</p><h2>3. Zusammenfassung</h2><p>Das Tool analysiert die steuerlichen Risiken eines Wegzugs ins Ausland und stellt rechtssichere Gestaltungsoptionen dar. Im Fokus stehen steuerliche Folgen und Empfehlungen für verschiedene Gestaltungswege.</p><h2>4. Steuerliche Implikationen eines Wegzugs</h2><ul><li>Wegzugsbesteuerung nach § 6 AStG bei Anteilen an Kapitalgesellschaften.</li><li>Entstrickungsbesteuerung bei Mitunternehmeranteilen (§ 4 Abs. 1 Satz 3 EStG).</li><li>Sofortbesteuerung bei Wegzug in Nicht-DBA-Staaten ohne Stundungsmöglichkeiten.</li></ul>"
            )
        html_content += "</body></html>"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
            pdfkit.from_string(html_content, tmpfile.name)
            with open(tmpfile.name, "rb") as f:
                st.download_button(
                    label="PDF herunterladen",
                    data=f,
                    file_name=f"{initialen}_Analyse.pdf",
                    mime="application/pdf",
                )
