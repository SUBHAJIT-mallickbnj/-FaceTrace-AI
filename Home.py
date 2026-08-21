import yaml
import base64
import streamlit as st
from yaml import SafeLoader
import streamlit_authenticator as stauth

from pages.helper import db_queries
from pages.helper.map_utils import get_case_map_location, geocode_location
from pages.helper.utils import get_login_config_path

# Initialise DB once at startup
db_queries.create_db()

if "login_status" not in st.session_state:
    st.session_state["login_status"] = False

config_path = get_login_config_path()
if not config_path.exists():
    default_config = {
        "credentials": {
            "usernames": {
                "gagan": {
                    "email": "gaganmanku96@gmail.com",
                    "name": "SUBHAJIT MALLICK",
                    "city": "West Bengal",
                    "area": "Rupnarayanpur",
                    "role": "Admin",
                    "password": "$2b$12$ByZbwxrcvCXVLQO4zjI95OteXToaBiwWDqujsHiKfeGzionz0VqAG",
                }
            }
        },
        "cookie": {
            "expiry_days": 1,
            "key": "a8f3d2e1b9c7f4a0e5d6c3b2a1f8e7d4c9b0a3f2e1d8c7b6a5f4e3d2c1b0a9",
            "name": "random_cookie_name",
        },
        "preauthorized": {"emails": ["gaganmanku96@gmail.com"]},
    }
    config_path.write_text(yaml.safe_dump(default_config, sort_keys=False), encoding="utf-8")

try:
    with open(config_path) as file:
        config = yaml.load(file, Loader=SafeLoader)
except Exception as exc:
    st.error(f"Unable to read login configuration: {exc}")
    st.stop()

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

# ── Custom login page styling ─────────────────────────────────────────────────
if not st.session_state.get("authentication_status"):
    st.markdown(
        """
        <style>
        /* Hide default Streamlit header on login page */
        [data-testid="stHeader"] { background: transparent; }

        /* Login card wrapper */
        .login-card {
            max-width: 420px;
            margin: 0 auto;
            padding: 2.5rem 2rem;
        div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
        div[data-testid="stForm"] button[type="submit"]:hover {
            background-color: #0d47a1 !important;
        }
        </style>

        <div class="login-banner">
            <h1>Missing Person Identification System</h1>
            <p class="tagline">Officer &amp; Admin Portal — Secure Login</p>
            <span class="badge">AI-Powered Facial Recognition</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Perform login — updates session state authentication_status
authenticator.login(location="main")

# ── Post-login dashboard ──────────────────────────────────────────────────────
if st.session_state.get("authentication_status"):
    authenticator.logout("Logout", "sidebar")

    st.session_state["login_status"] = True
    user_info = config["credentials"]["usernames"][st.session_state["username"]]
    st.session_state["user"] = st.session_state["username"]

    role = user_info.get("role", "Officer")
    st.session_state["role"] = role

    role_colour = "#e74c3c" if role.lower() == "admin" else "#27ae60"
    role_badge = (
        f'<span style="background:{role_colour}; color:white; padding:3px 10px; '
        f'border-radius:12px; font-size:13px; font-weight:600">{role}</span>'
    )

    st.write(
        f'<p style="color:grey; text-align:left; font-size:45px">{user_info["name"]}</p>',
        unsafe_allow_html=True,
    )

    st.write(
        f'<p style="color:grey; text-align:left; font-size:20px">'
        f'{user_info["area"]}, {user_info["city"]}&nbsp;&nbsp;{role_badge}</p>',
        unsafe_allow_html=True,
    )

    st.write("---")

    found_cases = db_queries.get_registered_cases_count(st.session_state["user"], "F")
    non_found_cases = db_queries.get_registered_cases_count(st.session_state["user"], "NF")

    found_col, not_found_col = st.columns(2)
    found_col.metric("Found Cases Count", value=len(found_cases))
    not_found_col.metric("Not Found Cases Count", value=len(non_found_cases))

    st.write("---")

    # ── Cases map ─────────────────────────────────────────────────────────────
    st.subheader("Cases by City")

    try:
        import folium
        from streamlit_folium import st_folium

        CITY_COORDS = {
            "Delhi": (28.6139, 77.2090),
            "New Delhi": (28.6139, 77.2090),
            "Mumbai": (19.0760, 72.8777),
            "Bengaluru": (12.9716, 77.5946),
            "Bangalore": (12.9716, 77.5946),
            "Hyderabad": (17.3850, 78.4867),
            "Chennai": (13.0827, 80.2707),
            "Kolkata": (22.5726, 88.3639),
            "Pune": (18.5204, 73.8567),
            "Ahmedabad": (23.0225, 72.5714),
            "Jaipur": (26.9124, 75.7873),
            "Lucknow": (26.8467, 80.9462),
            "Kanpur": (26.4499, 80.3319),
            "Nagpur": (21.1458, 79.0882),
            "Indore": (22.7196, 75.8577),
            "Bhopal": (23.2599, 77.4126),
            "Visakhapatnam": (17.6868, 83.2185),
            "Patna": (25.5941, 85.1376),
            "Vadodara": (22.3072, 73.1812),
            "Surat": (21.1702, 72.8311),
            "Noida": (28.5355, 77.3910),
            "Gurgaon": (28.4595, 77.0266),
            "Gurugram": (28.4595, 77.0266),
            "Chandigarh": (30.7333, 76.7794),
            "Coimbatore": (11.0168, 76.9558),
            "Kochi": (9.9312, 76.2673),
            "Agra": (27.1767, 78.0081),
            "Varanasi": (25.3176, 82.9739),
            "Meerut": (28.9845, 77.7064),
            "Raipur": (21.2514, 81.6296),
            "Ranchi": (23.3441, 85.3096),
            "Guwahati": (26.1445, 91.7362),
            "Jodhpur": (26.2389, 73.0243),
            "Amritsar": (31.6340, 74.8723),
            "Faridabad": (28.4089, 77.3178),
            "Allahabad": (25.4358, 81.8463),
            "Prayagraj": (25.4358, 81.8463),
            "Mathura": (27.4924, 77.6737),
            "Bareilly": (28.3670, 79.4304),
            "Aligarh": (27.8974, 78.0880),
            "Moradabad": (28.8386, 78.7733),
            "Saharanpur": (29.9680, 77.5460),
            "Gorakhpur": (26.7606, 83.3732),
            "Firozabad": (27.1591, 78.3957),
            "Jhansi": (25.4484, 78.5685),
            "Ghaziabad": (28.6692, 77.4538),
            "Ludhiana": (30.9010, 75.8573),
            "Jalandhar": (31.3260, 75.5762),
            "Dehradun": (30.3165, 78.0322),
            "Haridwar": (29.9457, 78.1642),
            "Rishikesh": (30.0869, 78.2676),
            "Shimla": (31.1048, 77.1734),
            "Bathinda": (30.2110, 74.9455),
            "Unknown": (20.5937, 78.9629),
        }

        cases = db_queries.get_cases_for_map()

        if not cases:
            st.info("No cases registered yet. Add a location when registering a case.")
        else:
            m = folium.Map(
                location=[20.5937, 78.9629], zoom_start=5, tiles="CartoDB positron"
            )

            for case_id, name, status, city, last_seen, address, latitude, longitude in cases:
                coords, location_text = get_case_map_location(
                    city, last_seen, address, latitude, longitude
                )
                if latitude is None or longitude is None:
                    coords = geocode_location(city, last_seen, address)
                color = "#27ae60" if status == "F" else "#e74c3c"
                status_text = "Found" if status == "F" else "Not Found"
                tooltip = (
                    f"<b>{name}</b><br>"
                    f"Status: {status_text}<br>"
                    f"Location: {location_text}"
                )
                folium.CircleMarker(
                    location=coords,
                    radius=10,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.6,
                    tooltip=folium.Tooltip(tooltip),
                ).add_to(m)

            st_folium(m, width="100%", height=420, returned_objects=[])

            st.markdown(
                '<span style="color:#e74c3c;">●</span> Has unresolved cases &nbsp;&nbsp;'
                '<span style="color:#27ae60;">●</span> All resolved &nbsp;&nbsp;'
                "Circle size = number of cases",
                unsafe_allow_html=True,
            )

    except ImportError:
        st.info("Install `folium` and `streamlit-folium` to enable the map.")

elif st.session_state.get("authentication_status") == False:
    st.error("❌ Username or password is incorrect. Please try again.")
elif st.session_state.get("authentication_status") is None:
    st.session_state["login_status"] = False
