import logging
from enum import StrEnum
from pathlib import Path

import polars as pl
import streamlit as st

REPORTS_FILE = "20261017 reports concept.xlsx"
PROFILES_FILE = "20261017 timeseries_TL.parquet"
PROFILES_REPORT_PREFIXES = [
    "1.9a",
    "1.9e",
    "3.15d",
    "3.15e",
    "3.17a2",
    "3.17b2",
]

PAGE_TITLE = "Verschilmakers Energiebeelden Overijssel"
OVERIJSSEL = "Overijssel"
SCENARIOS = pl.Enum(["Huidig", "Netbeheerder", "Gemeentelijk", "Provinciaal"])


class GeoLevel(StrEnum):
    PROVINCIE = "Provincie"
    GEMEENTE = "Gemeente"
    HSMS = "HSMS"
    POCKET = "Pocket"


# suppress messages about not being able to recognize dtype (on empty columns mostly)
logging.getLogger("fastexcel.types.dtype").setLevel(logging.ERROR)


def make_sheet_name(code: str, geo_level: str) -> str:
    return f"{code}_{geo_level.lower()}"


def prepare_frame(
    data: dict[str, pl.DataFrame], sheet_code: str, geo_level: str, area: str, order_scenarios: bool = True
) -> pl.DataFrame:
    sheet_name = make_sheet_name(sheet_code, geo_level)
    filtered_data = data[sheet_name].filter(pl.col(geo_level).eq(area))
    return filtered_data.sort(pl.col("Scenario").cast(SCENARIOS)) if order_scenarios else filtered_data


@st.cache_data
def load_data() -> dict[str, pl.DataFrame]:
    path = Path(__file__).parent.parent.parent / "data" / REPORTS_FILE
    return pl.read_excel(path, sheet_id=0)  # load all sheets as dict of frames


@st.cache_data
def load_profiles() -> pl.DataFrame:
    path = Path(__file__).parent.parent.parent / "data" / PROFILES_FILE
    return (
        pl.scan_parquet(path)
        .filter(pl.col("report_id").str.split("_").list.first().is_in(PROFILES_REPORT_PREFIXES))
        .collect()
    )


data = load_data()
profiles = load_profiles()

st.set_page_config(
    page_title=PAGE_TITLE,
    layout="wide",
)


## HEADER ROW

st.title(PAGE_TITLE)
st.badge("Dit is een prototype gebouwd in Streamlit (Python)", color="blue")

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

if st.checkbox("Toon 'reports' data per indicator label voor geselecteerd gebied"):
    unique_labels = sorted({x.split("_")[0] for x in data})
    selected_label = st.selectbox(
        "Indicator label",
        unique_labels,
    )

    try:
        raw_frame = prepare_frame(data, selected_label, selected_geo_level, selected_area, False)
        st.write(raw_frame)
    except Exception as e:
        st.badge(f"Fout: {e}", color="red")

tab_cw, tab_em = st.tabs(["Collectieve warmte", "Energiemix"], on_change="rerun")

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

        benutting_warmte_frame = prepare_frame(data, "1.5", selected_geo_level, selected_area)

        # st.write(benutting_warmte_frame)
        if "Huidig" in benutting_warmte_frame.get_column("Scenario"):
            warmte_potentie = (
                benutting_warmte_frame.filter(pl.col("Scenario").eq("Huidig")).select("waarde_3").item() or 0
            )
        else:
            warmte_potentie = 0

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

    with col4:
        st.subheader("Profiel koude week")
        st.badge("TODO", color="yellow")

        profile_cold1 = profiles.filter(
            pl.col("report_id").eq(make_sheet_name("1.9a", selected_geo_level)),
            pl.col(selected_geo_level).eq(selected_area),
        )

        profile_cold2 = profiles.filter(
            pl.col("report_id").eq(make_sheet_name("1.9e", selected_geo_level)),
            pl.col(selected_geo_level).eq(selected_area),
        )

        profile_cold = pl.concat([profile_cold1, profile_cold2])

        # st.write(profile_cold)

        st.line_chart(
            profile_cold.with_columns(
                pl.col("Timestamp").str.to_datetime(),
            ),
            x="Timestamp",
            x_label="",
            y="Value",
            y_label="Vermogen [MW]",  # TODO wat is de eenheid? lijkt niet te kloppen met piekvermogen
            color="report_name",
            height="stretch",
        )


with tab_em:
    ### FIRST ROW
    col1, col2, col3 = st.columns([1, 1, 2], gap="medium", border=True)

    with col1:
        st.subheader("Opwek in ontwikkeling")
        st.badge("TODO huidig als extra blok onder plannen en potentie", color="yellow")

        # 'plannen' (3.14b) not available for HSMS and Pocket levels
        if selected_geo_level in [GeoLevel.PROVINCIE, GeoLevel.GEMEENTE]:
            opwek_sheets = ["3.14a2", "3.14b", "3.14c2"]
        else:
            opwek_sheets = ["3.14a2", "3.14c2"]

        opwek_data = pl.concat(
            [
                prepare_frame(data, sheet, selected_geo_level, selected_area, order_scenarios=False).cast(
                    {"waarde_1": pl.Float64}
                )
                for sheet in opwek_sheets
            ]
        )

        st.bar_chart(
            opwek_data,
            x="Scenario",
            x_label="",
            y="waarde_1",
            y_label="",
            color="Verbijzondering",
            horizontal=True,
            height="stretch",
        )

        st.badge("TODO vraag in grafiek als lijn?", color="yellow")

        yearly_demand = prepare_frame(data, "3.14d", selected_geo_level, selected_area).select("waarde_1").item()
        st.metric("Jaarlijkse elektriciteitsvraag [TJ]", yearly_demand)

    with col2:
        st.subheader("Keuze e-mix")
        st.markdown(
            """
            De basis voor ons toekomstige energiesysteem zal bestaan uit elektriciteit. Door opwek en vraag 
            slim af te stemmen op beschikbare ruimte en lokale potenties, kunnen we netcongestie beperken, 
            maatschappelijke kosten verlagen en het energiesysteem betrouwbaarder maken. 
            Zonder keuzes moeten netten worden uitgebreid, met grotere ruimtelijke impact en hogere kosten als gevolg.
            """
        )

    with col3:
        st.subheader("Benuttingsgraad")

        benutting_frame = (
            prepare_frame(data, "3.15h", selected_geo_level, selected_area, order_scenarios=False)
            .pivot(
                on="SupplyStrategy",
                index="DemandScenario",
                values="waarde_1",
            )
            .with_columns(pl.selectors.numeric().round(1))
            .select(pl.lit("Benuttingsgraad [%]").alias("Aspect"), "Zon", "Wind", "Kern", "DemandScenario")
        )
        # TODO concat other frames for 'import' and 'curtailment', are they available?

        benutting_scenario = st.segmented_control(
            "Scenario",
            ["Netbeheerder", "Gemeentelijk", "Provinciaal"],
            default="Netbeheerder",
            required=True,
        )

        st.write(benutting_frame.filter(pl.col("DemandScenario").eq(benutting_scenario)))

        st.badge("TODO aanvullen met andere aspecten", color="yellow")

    ### SECOND ROW
    col1, col2 = st.columns([3, 1], gap="medium", border=True)

    with col1:
        st.subheader("Weekprofielen vraag en opwek")

        weekprofielen_scenario = st.segmented_control(
            "Scenario",
            ["Netbeheerder", "Gemeentelijk", "Provinciaal"],
            default="Netbeheerder",
            required=True,
            key="weekprofielen_scenario",
        )

        # winter
        st.markdown("**Winter**")
        profile_supply_winter = profiles.filter(
            pl.col("report_id").eq(make_sheet_name("3.15d", selected_geo_level)),
            pl.col(selected_geo_level).eq(selected_area),
            pl.col("DemandScenario").eq(weekprofielen_scenario),
        )

        profile_demand_winter = profiles.filter(
            pl.col("report_id").eq(make_sheet_name("3.15e", selected_geo_level)),
            pl.col(selected_geo_level).eq(selected_area),
            pl.col("Scenario").eq(weekprofielen_scenario),
        ).with_columns(pl.lit("Vraag").alias("SupplyStrategy"))

        profile_winter = (
            pl.concat(
                [
                    profile_supply_winter,
                    profile_demand_winter,
                ]
            )
            .pivot(
                on="SupplyStrategy",
                index="Timestamp",
                values="Value",
            )
            .with_columns(pl.col("Timestamp").str.to_datetime())
        )

        # st.write(profile_supply)

        # TODO plot 'Vraag' as area instead of line
        st.line_chart(
            profile_winter,
            x="Timestamp",
            y_label="Vermogen [MW]",
            height="stretch",
        )

        # summer
        st.markdown("**Zomer**")
        profile_supply_summer = profiles.filter(
            pl.col("report_id").eq(make_sheet_name("3.17a2", selected_geo_level)),
            pl.col(selected_geo_level).eq(selected_area),
            pl.col("DemandScenario").eq(weekprofielen_scenario),
        )

        profile_demand_summer = profiles.filter(
            pl.col("report_id").eq(make_sheet_name("3.17b2", selected_geo_level)),
            pl.col(selected_geo_level).eq(selected_area),
            pl.col("Scenario").eq(weekprofielen_scenario),
        ).with_columns(pl.lit("Vraag").alias("SupplyStrategy"))

        profile_summer = (
            pl.concat(
                [
                    profile_supply_summer,
                    profile_demand_summer,
                ]
            )
            .pivot(
                on="SupplyStrategy",
                index="Timestamp",
                values="Value",
            )
            .with_columns(pl.col("Timestamp").str.to_datetime())
        )

        # st.write(profile_supply)

        # TODO plot 'Vraag' as area instead of line
        st.line_chart(
            profile_summer,
            x="Timestamp",
            y_label="Vermogen [MW]",
            height="stretch",
        )

    with col2:
        st.subheader("Relatie verschilmakers")
        st.markdown(
            """
            **Collectieve warmte**
            
            Betere benutting van lokale warmtebronnen vermindert de vraag naar elektriciteit.
            
            **Waterstof backbone**
            
            Inzet van waterstof vermindert de vraag naar elektriciteit.
            
            **Sturen in tijd**
            
            Door elektriciteitsvraag te verplaatsen van piek- naar dalmomenten neemt de benuttingsgraad toe.
            """
        )
