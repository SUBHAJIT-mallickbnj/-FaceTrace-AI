import yaml
import base64
import streamlit as st
from yaml import SafeLoader
import streamlit_authenticator as stauth

from pages.helper import db_queries
from pages.helper.map_utils import (
    resolve_case_map_coordinate,
    separate_overlapping_coordinate,
)
from pages.helper.utils import get_login_config_path

st.set_page_config(
    page_title="FaceTrace AI | Missing Person Response",
    page_icon=":material/radar:",
    layout="wide",
)

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

if st.session_state.get("authentication_status") is False:
    st.session_state["login_status"] = False
    st.session_state.pop("user", None)
    st.session_state.pop("role", None)

def render_landing_page():
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stAppViewContainer"] > .main { padding-top: 0; }
        .landing-wrap { max-width: 1180px; margin: 0 auto; padding: 1.5rem 0 2rem; }
        .landing-page-title { margin: 0 auto 2rem; text-align: center; color: #f7f8fa; font-size: clamp(2rem, 5vw, 4.2rem); line-height: 1; font-weight: 900; white-space: nowrap; }
        .landing-nav { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: .5rem 0 2.5rem; }
        .brand-lockup { display: flex; align-items: center; gap: .75rem; }
        .brand-mark { display: grid; place-items: center; width: 2.75rem; height: 2.75rem; border-radius: 14px; color: white; background: linear-gradient(135deg, #f05d4e, #d43b69); box-shadow: 0 10px 24px rgba(212,59,105,.25); font-size: 1.35rem; }
        .brand-name { font-weight: 800; font-size: 1.1rem; letter-spacing: .02em; }
        .brand-subtitle, .hero-text, .landing-stat small, .feature-card p, .section-kicker, .landing-footer { color: #7f8b9b; }
        .brand-subtitle { font-size: .78rem; margin-top: .15rem; }
        .nav-pill { color: #d43b69; border: 1px solid rgba(212,59,105,.3); border-radius: 999px; padding: .45rem .9rem; font-size: .78rem; font-weight: 700; }
        .eyebrow { color: #d43b69; font-size: .78rem; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
        .hero-title { max-width: 720px; margin: .8rem 0 1rem; font-size: clamp(2.8rem, 6vw, 5.4rem); line-height: .98; letter-spacing: -.04em; font-weight: 850; }
        .hero-title span { color: #d43b69; }
        .hero-text { max-width: 620px; font-size: 1.08rem; line-height: 1.7; }
        .landing-stat-row { display: flex; flex-wrap: wrap; gap: .7rem; margin-top: 1.6rem; }
        .landing-stat { min-width: 130px; padding: .85rem 1rem; border: 1px solid rgba(127,139,155,.22); border-radius: 12px; background: rgba(127,139,155,.06); }
        .landing-stat strong { display: block; font-size: 1.15rem; }
        .preview-frame { position: relative; overflow: hidden; padding: .65rem; border: 1px solid rgba(127,139,155,.26); border-radius: 18px; background: rgba(127,139,155,.08); box-shadow: 0 24px 70px rgba(0,0,0,.18); }
        .preview-frame img { border-radius: 12px; }
        .preview-tag { position: absolute; right: 1.2rem; bottom: 1.2rem; padding: .55rem .75rem; border-radius: 10px; color: white; background: #1d9b68; font-size: .76rem; font-weight: 800; }
        .section-kicker { margin: 2.5rem 0 1rem; font-size: .86rem; }
        .feature-card { min-height: 150px; padding: 1.2rem; border: 1px solid rgba(127,139,155,.2); border-radius: 14px; background: rgba(127,139,155,.055); }
        .feature-icon { color: #d43b69; font-size: 1.35rem; }
        .feature-card h3 { margin: .75rem 0 .45rem; font-size: 1rem; }
        .feature-card p { font-size: .88rem; line-height: 1.55; }
        .landing-footer { font-size: .8rem; padding-top: 2.5rem; }
        @media (prefers-color-scheme: light) { .brand-subtitle, .hero-text, .landing-stat small, .feature-card p, .section-kicker, .landing-footer { color: #5d6875; } .landing-stat, .feature-card { background: rgba(30,41,59,.035); } }
                @media (max-width: 520px) { .landing-page-title { font-size: 2rem; } }
        </style>
        <div class="landing-wrap">
                    <div class="landing-page-title">FaceTrace AI</div>
          <div class="landing-nav">
            <div class="brand-lockup"><div class="brand-mark">+</div><div><div class="brand-name">FaceTrace AI</div><div class="brand-subtitle">Missing person response network</div></div></div>
            <div class="nav-pill">SECURE OPERATIONS PORTAL</div>
          </div>
          <div class="eyebrow">Identify faster. Coordinate better.</div>
          <div class="hero-title">A clearer path from <span>missing</span> to found.</div>
          <div class="hero-text">FaceTrace AI helps officers and communities register cases, analyze sightings, and coordinate resolutions from one focused workspace.</div>
          <div class="landing-stat-row"><div class="landing-stat"><strong>468-point</strong><small>face landmark analysis</small></div><div class="landing-stat"><strong>Live map</strong><small>case locations and status</small></div><div class="landing-stat"><strong>Role-based</strong><small>secure officer access</small></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    preview_col, copy_col = st.columns([1.15, 0.85], gap="large")
    with preview_col:
        st.markdown('<div class="preview-frame">', unsafe_allow_html=True)
        st.image("assets/screenshots/register_new_case.png", width="stretch")
        st.markdown('<div class="preview-tag">LIVE CASE INTELLIGENCE</div></div>', unsafe_allow_html=True)
    with copy_col:
        st.markdown('<div class="section-kicker">BUILT FOR THE MOMENT THAT MATTERS</div>', unsafe_allow_html=True)
        st.markdown("### One workspace. Every response.")
        st.write("Register a missing-person case, receive public sightings, compare face embeddings, and keep teams aligned with live case status and location markers.")
        if st.button("Open secure dashboard", type="primary", use_container_width=True):
            st.session_state["show_login"] = True
            st.rerun()
        st.caption("Authorized officers and administrators only")

    st.markdown('<div class="section-kicker">THE RESPONSE TOOLKIT</div>', unsafe_allow_html=True)
    feature_cols = st.columns(3, gap="medium")
    features = [("01", "Register cases", "Capture identity details, photos, locations, and complainant information in one structured record."), ("02", "Match sightings", "Compare public submissions against unresolved cases with confidence-aware face analysis."), ("03", "Track resolution", "Follow red unresolved markers to green confirmed outcomes on the live map.")]
    for column, (number, title, description) in zip(feature_cols, features):
        with column:
            st.markdown(f'<div class="feature-card"><div class="feature-icon">{number}</div><h3>{title}</h3><p>{description}</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="landing-footer">FaceTrace AI &middot; Secure case coordination for faster, more informed action.</div>', unsafe_allow_html=True)

# ── Public landing page and secure login ──────────────────────────────────────
if not st.session_state.get("authentication_status") and not st.session_state.get("show_login"):
    render_landing_page()
elif not st.session_state.get("authentication_status"):
    # ── Custom login page styling ─────────────────────────────────────────────
    login_banner = st.empty()
    login_banner.markdown(
        """
        <style>
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] { display: none; }

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
    if st.session_state.get("authentication_status"):
        login_banner.empty()

# ── Post-login dashboard ──────────────────────────────────────────────────────
if st.session_state.get("authentication_status"):
    st.session_state["show_login"] = False
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
            seen_coordinates = {}

            for case_id, name, status, city, last_seen, address, latitude, longitude in cases:
                location_text = last_seen.strip() if last_seen else "Unknown"
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
