import streamlit as st

from pages.helper import db_queries, match_algo, train_model
from pages.helper import emailer
from pages.helper.utils import get_case_image_path, render_image, get_resources_dir

# SFace cosine-distance threshold used in match_algo — keep in sync.
DISTANCE_THRESHOLD = 0.363


def confidence_from_distance(distance: float) -> float:
    """Convert a KNN distance to a 0–100 confidence percentage."""
    return max(0.0, min(100.0, (1.0 - distance / DISTANCE_THRESHOLD) * 100))


def case_viewer(
    registered_case_id: str,
    public_case_id: str,
    confidence: float = None,
    mark_found: bool = True,
):
    try:
        case_details = db_queries.get_registered_case_detail(registered_case_id)[0]
        data_col, image_col = st.columns(2)

        # case_details: (name, complainant_mobile, complainant_email, age, last_seen, birth_marks)
        labels = ["Name", "Mobile", "Age", "Last Seen", "Birth Marks"]
        display_values = [
            case_details[0],  # name
            case_details[1],  # complainant_mobile
            case_details[3],  # age
            case_details[4],  # last_seen
            case_details[5],  # birth_marks
        ]
        for text, value in zip(labels, display_values):
            data_col.write(f"**{text}:** {value}")

        if confidence is not None:
            data_col.write("")
            data_col.markdown("**Match Confidence**")
            data_col.progress(
                confidence / 100,
                text=f"{confidence:.0f}% confidence",
            )

        public_details = db_queries.get_public_case_detail(public_case_id)
        if public_details:
            location, submitted_by, mobile, birth_marks = public_details[0]
            data_col.write(f"**Sighting Location:** {location}")
            data_col.write(f"**Reported By:** {submitted_by}")
            data_col.write(f"**Reporter Mobile:** {mobile}")
            data_col.write(f"**Reporter Birth Marks:** {birth_marks or 'Not provided'}")

        if mark_found:
            db_queries.update_found_status(registered_case_id, public_case_id)
            st.success("✅ Status updated. Case is now marked as Found.")
        else:
            st.info("✅ Confirmed match from the public portal. Case is already Found.")

        registered_image = get_case_image_path(registered_case_id)
        if registered_image:
            image_col.image(str(registered_image), width=160)

        public_image = get_case_image_path(public_case_id)
        if public_image:
            image_col.image(str(public_image), width=160)

        # Send email to complainant
        sent = mark_found and emailer.send_match_notification(
            registered_case_id, case_details
        )
        if sent:
            st.info(f"📧 Notification sent to {case_details[2]}")

    except Exception as e:
        import traceback

        traceback.print_exc()
        st.error(f"❌ Something went wrong: {str(e)}. Please check logs.")


if "login_status" not in st.session_state:
    st.write("You don't have access to this page")

elif st.session_state["login_status"]:
    user = st.session_state.user

    is_admin = st.session_state.get("role", "").lower() == "admin"

    st.title("Check for Match")

    if not is_admin:
        st.info("🔒 Only Admins can trigger the matching process.")
    else:
        col1, col2 = st.columns(2)
        refresh_bt = col1.button("🔄 Refresh")
        st.write("---")
        newly_confirmed = set()

        if refresh_bt:
            with st.spinner("Fetching data and training model..."):
                result = train_model.train(user)
                matched_ids = match_algo.match()

                if matched_ids["status"]:
                    if not matched_ids["result"]:
                        st.info("No matches found.")
                        diagnostics = matched_ids.get("diagnostics", [])
                        if diagnostics:
                            best = min(diagnostics, key=lambda item: item["distance"])
                            st.caption(
                                "Closest candidate was not confirmed: "
                                f"distance {best['distance']:.3f}; "
                                f"required <= {best['threshold']:.3f}."
                            )
                    else:
                        for matched_id, submitted_cases in matched_ids[
                            "result"
                        ].items():
                            for submitted_case in submitted_cases:
                                if isinstance(submitted_case, tuple):
                                    submitted_case_id, distance = submitted_case
                                    conf = confidence_from_distance(distance)
                                else:
                                    submitted_case_id = submitted_case
                                    conf = None

                                newly_confirmed.add((matched_id, submitted_case_id))
                                case_viewer(matched_id, submitted_case_id, conf)
                                st.write("---")
                else:
                    st.info("No new unresolved matches found.")

        confirmed_matches = db_queries.get_confirmed_matches(user)
        if confirmed_matches:
            st.subheader("Confirmed matches")
            st.caption("These matches were already confirmed and saved from public responses.")
            for row in confirmed_matches:
                (
                    registered_case_id,
                    _name,
                    _age,
                    _last_seen,
                    _matched_with,
                    public_case_id,
                    _location,
                    _submitted_by,
                    _mobile,
                    _birth_marks,
                    _submitted_on,
                ) = row
                if (registered_case_id, public_case_id) in newly_confirmed:
                    continue
                case_viewer(
                    registered_case_id,
                    public_case_id,
                    confidence=None,
                    mark_found=False,
                )
                st.write("---")

else:
    st.write("You don't have access to this page")
