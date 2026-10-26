import logging
from enum import StrEnum
from pathlib import Path

import polars as pl
import streamlit as st

REPORTS_FILE = "20261017 reports concept.xlsx"

PAGE_TITLE = "Verschilmakers West-Overijssel"
OVERIJSSEL = "Overijssel"
SCENARIOS = pl.Enum(["Huidig", "Netbeheerder", "Gemeentelijk", "Provinciaal"])


class GeoLevel(StrEnum):
    PROVINCIE = "Provincie"
    GEMEENTE = "Gemeente"
    HSMS = "HSMS"
    POCKET = "Pocket"


logging.getLogger("fastexcel.types.dtype").setLevel(logging.ERROR)


def make_sheet_name(code: str, geo_level: str) -> str:
    return f"{code}_{geo_level.lower()}"


def prepare_frame(data: dict[str, pl.DataFrame], sheet_code: str, geo_level: str, area: str) -> pl.DataFrame:
    sheet_name = make_sheet_name(sheet_code, geo_level)
    return data[sheet_name].filter(pl.col(geo_level).eq(area)).sort(pl.col("Scenario").cast(SCENARIOS))


@st.cache_data
def load_data() -> dict[str, pl.DataFrame]:
    path = Path(__file__).parent.parent.parent / "data" / REPORTS_FILE
    return pl.read_excel(path, sheet_id=0)  # load all sheets as dict of frames


data = load_data()

st.set_page_config(
    page_title=PAGE_TITLE,
    layout="wide",
)


## HEADER ROW

st.title(PAGE_TITLE)

if st.checkbox("Toon beschikbare indicator labels"):
    unique_labels = sorted({x.split("_")[0] for x in data})
    st.write(" - ".join(unique_labels))

selected_geo_level: str = st.segmented_control(
    "Geografische indeling",
    tuple(GeoLevel),
    default=GeoLevel.PROVINCIE,
    selection_mode="single",
    required=True,
)

if selected_geo_level != GeoLevel.PROVINCIE:
    # take any sheet to get the geo select options from
    first_sheet = make_sheet_name("1.1a", selected_geo_level)
    first_frame = data[first_sheet]
    area_options = first_frame[selected_geo_level].unique().sort()
    selected_area: str = st.pills(
        selected_geo_level,
        area_options,
        selection_mode="single",
        required=True,
        default=area_options[0],
    )
else:
    selected_area = OVERIJSSEL

tab_cw, tab_em, tab_else = st.tabs(["Collectieve warmte", "Energiemix", "Later meer..."])

## TAB COLLECTIEVE WARMTE

with tab_cw:
    #### FIRST ROW

    col1, col2, col3, col4 = st.columns([2, 1, 1, 1], gap="medium", border=True)

    with col1:
        st.subheader("Energievraag gebouwde omgeving")
        energie_go_sheet = make_sheet_name("1.8a", selected_geo_level)
        energie_go_frame = data[energie_go_sheet]
        # st.write(energie_go_frame)

        energie_go_pivoted = (
            energie_go_frame.filter(pl.col(selected_geo_level).eq(selected_area))
            .pivot(
                selected_geo_level,
                index=["Scenario", "energy_carrier"],
                values="waarde_1",
            )
            .sort(
                pl.col("Scenario").cast(SCENARIOS)  # this correctly sorts to the ordered enum
            )
        )

        # st.write(energie_go_pivoted)

        st.bar_chart(
            energie_go_pivoted,
            x="Scenario",
            y=selected_area,
            y_label="Jaarlijkse energievraag [TJ]",
            color="energy_carrier",
            horizontal=True,
            height="stretch",
            sort=False,
        )

    with col2:
        st.subheader("Waarom collectieve warmte?")
        st.markdown(
            """
            Collectieve warmtenetten zijn essentieel voor een robuust energiesysteem in 2050. 
            Ze benutten lokale warmtebronnen zoals aardwarmte, restwarmte en aquathermie, 
            verminderen de afhankelijkheid van elektriciteit voor verwarming 
            en beperken de noodzaak voor kostbare netuitbreidingen. 
            Zo dragen warmtenetten bij aan een gebalanceerde energiemix, 
            lagere maatschappelijke kosten en een betrouwbare, toekomstbestendige energievoorziening.
            """
        )

    with col3:
        st.subheader("Benutting warmte")
        st.badge("TODO potentie in grafiek als lijn?", color="yellow")
        # st.text("Mockup is niet uit de data te maken!")

        benutting_warmte_frame = prepare_frame(data, "1.5", selected_geo_level, selected_area)

        # st.write(benutting_warmte_frame)

        warmte_potentie = benutting_warmte_frame.filter(pl.col("Scenario").eq("Huidig")).select("waarde_3").item() or 0

        st.metric("Potentie warmte [TJ]", warmte_potentie)

        st.bar_chart(
            benutting_warmte_frame,
            x="Scenario",
            y="waarde_2",
            x_label="",
            y_label="Warmtevraag [TJ]",
            color="red",
            horizontal=True,
            height="stretch",
            sort=False,
        )

    with col4:
        st.subheader("Bronnen")
        st.markdown(
            """
            In Overijssel zijn relatief weinig warmtebronnen. Benutting van restwarmte van 
            de afvalverbrandings-installatie van Twence is de grootste. Daarnaast is er lokaal potentie 
            voor geothermie, net als aquathermie. Deze laatste vereist echter een forse elektriciteitsvraag. 

            Het is de vraag in hoeverre de potentie kosteneffectief kan worden benut.
            """
        )

    #### SECOND ROW

    col1, col2, col3, col4 = st.columns([1, 1, 1, 2], gap="medium", border=True)

    with col1:
        st.subheader("Relatie verschilmakers")
        st.markdown(
            """
            **Opwek elektriciteit**
            
            Betere benutting collectieve warmte zorgt voor lagere elektriciteitsvraag 
            en minder lokale opwek van zon- en windenergie.
            
            **Groen gas**
            
            Betere warmtebenutting leidt tot minder vraag naar schaars groen gas. 
            
            **Sturen in tijd en ruimte**
            
            Betere warmtebenutting reduceert lokaal electriciteitsvraag en biedt mogelijk ruimte voor andere sectoren.
            """
        )

    with col2:
        st.subheader("Piekvermogen elektriciteit")
        st.text("NB: optelling van individuele pieken")
        warmte_piek_sheet = make_sheet_name("1.1a", selected_geo_level)
        warmte_piek_frame = data[warmte_piek_sheet]

        warmte_piek_pivoted = (
            warmte_piek_frame.filter(pl.col(selected_geo_level).eq(selected_area))
            .pivot(
                on=selected_geo_level,
                index="Scenario",
                values="waarde_2",
            )
            .sort(pl.col("Scenario").cast(SCENARIOS))
        )

        st.bar_chart(
            warmte_piek_pivoted,
            x="Scenario",
            y=selected_area,
            y_label="Piekvermogen elektriciteit [MW]",
            sort=False,
        )

        # st.write(warmte_piek_pivoted)

        warmte_piek_metric = (
            warmte_piek_pivoted.filter(pl.col("Scenario").eq("Provinciaal")).select(selected_area).item()
            / warmte_piek_pivoted.filter(pl.col("Scenario").eq("Netbeheerder")).select(selected_area).item()
        )

    with col3:
        st.subheader("Piekverlaging provinciaal scenario")
        st.metric(
            "Piekverlaging in provinciaal scenario",
            round(1 - warmte_piek_metric, 2),
            format="percent",
            label_visibility="collapsed",
        )

        st.subheader("Vermeden windturbines")
        wind_sheet = make_sheet_name("1.3a", selected_geo_level)
        wind_frame = data[wind_sheet]

        vermeden_windturbines_prov = (
            wind_frame.filter(pl.col(selected_geo_level).eq(selected_area), pl.col("Scenario").eq("Provinciaal"))
            .select("waarde_1")
            .item()
        )

        st.metric(
            "Vermeden windturbines",
            round(vermeden_windturbines_prov),
            label_visibility="collapsed",
            # height="stretch",
        )

        # st.text("In provinciaal scenario")

    with col4:
        st.subheader("Profiel koude week")
        st.badge("TODO", color="yellow")
        # st.write("Data nog niet beschikbaar.")
