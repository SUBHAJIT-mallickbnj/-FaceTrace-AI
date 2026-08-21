import streamlit as st

from pages.helper.utils import render_dataframe

from pages.helper import db_queries
from pages.helper.map_utils import (
    resolve_case_map_coordinate,
    separate_overlapping_coordinate,
)

st.set_page_config(page_title="Cases Map")

if "login_status" not in st.session_state:
    st.write("You don't have access to this page")

elif st.session_state["login_status"]:
    st.title("Cases by City — India Map")

    try:
        import folium
        from streamlit_folium import st_folium
    except ImportError:
        st.error(
            "❌ Map dependencies not installed. Run: `pip install folium streamlit-folium`"
        )
        st.stop()

    cases = db_queries.get_cases_for_map()

    if not cases:
        st.info(
            "No cases registered yet. Add a location when registering a case."
        )
        st.stop()

    # Build map centered on India
    m = folium.Map(location=[20.5937, 78.9629], zoom_start=5, tiles="CartoDB positron")
    seen_coordinates = {}

    for case_id, name, status, city, last_seen, address, latitude, longitude in cases:
        location_text = " / ".join(
            value.strip() for value in (last_seen, address) if value
        ) or city or "Unknown"
        coords = resolve_case_map_coordinate(
            city, last_seen, address, latitude, longitude
        )
        marker_coords = separate_overlapping_coordinate(coords, seen_coordinates)
        color = "#27ae60" if status == "F" else "#e74c3c"
        status_text = "Found" if status == "F" else "Not Found"
        tooltip = (
            f"<b>{name}</b><br>"
            f"Status: {status_text}<br>"
            f"Location: {location_text}"
        )
        folium.CircleMarker(
            location=marker_coords,
            radius=10,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6,
            tooltip=folium.Tooltip(tooltip),
        ).add_to(m)

    st_folium(m, width=900, height=550)

    # Legend
    st.markdown(
        """
        <div style="font-size:0.85rem; color:#555; margin-top:8px;">
        <span style="color:#e74c3c;">●</span> Not Found &nbsp;&nbsp;
        <span style="color:#27ae60;">●</span> Found &nbsp;&nbsp;
        Each marker represents one case
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Live case summary table
    st.write("---")
    st.subheader("Case Location Summary")
    rows = [
        {
            "Case": name,
            "Status": "Found" if status == "F" else "Not Found",
            "Location": " / ".join(value.strip() for value in (last_seen, address) if value),
        }
        for _case_id, name, status, _city, last_seen, address, _latitude, _longitude in cases
    ]
    import pandas as pd

    df = pd.DataFrame(rows).sort_values("Case").reset_index(drop=True)
    render_dataframe(df, width="stretch")

else:
    st.write("You don't have access to this page")
