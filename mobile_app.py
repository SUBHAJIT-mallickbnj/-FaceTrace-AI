import os
import uuid
import json
import base64
import tempfile

import streamlit as st

import pages.helper.db_queries as db_queries
from pages.helper.data_models import PublicSubmissions
from pages.helper.utils import (
    image_obj_to_numpy,
    extract_face_mesh_landmarks,
    extract_unique_faces_from_video,
    get_resources_dir,
)

st.set_page_config("FaceTrace AI", initial_sidebar_state="collapsed")
db_queries.create_db()

# ── Modern Custom CSS for Dark/Light Mode ────────────────────────────────────
st.markdown("""
    <style>
    /* Main container styling */
    .main {
        padding: 2rem 1rem;
    }
    
    /* Title styling */
    .title-container {
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .title-container h1 {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
    }
    
    .subtitle-text {
        font-size: 1.1rem;
        opacity: 0.7;
        margin-top: 0.5rem;
    }
    
    /* Upload mode selector */
    .upload-mode-container {
        display: flex;
        justify-content: center;
        gap: 1rem;
        margin-bottom: 2rem;
        flex-wrap: wrap;
    }
    
    /* Radio button custom styling */
    [role="radiogroup"] {
        display: flex;
        justify-content: center;
        gap: 1.5rem;
    }
    
    /* Card styling for upload section */
    .upload-card {
        border-radius: 15px;
        padding: 2rem;
        border: 2px dashed rgba(102, 126, 234, 0.3);
        transition: all 0.3s ease;
        background: rgba(102, 126, 234, 0.05);
    }
    
    .upload-card:hover {
        border-color: rgba(102, 126, 234, 0.6);
        background: rgba(102, 126, 234, 0.1);
        transform: translateY(-2px);
    }
    
    /* Form section styling */
    .form-card {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
        border-radius: 15px;
        padding: 2rem;
        border: 1px solid rgba(102, 126, 234, 0.2);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
        margin-top: 1rem;
    }
    
    /* Form title */
    .form-title {
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Input field styling */
    .stTextInput input {
        border-radius: 10px !important;
        padding: 0.8rem !important;
        font-size: 1rem !important;
        border: 2px solid rgba(102, 126, 234, 0.2) !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    
    /* Submit button styling */
    .stFormSubmitButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        font-weight: 600 !important;
        padding: 0.8rem 2rem !important;
        border-radius: 10px !important;
        border: none !important;
        transition: all 0.3s ease !important;
        font-size: 1rem !important;
        width: 100% !important;
    }
    
    .stFormSubmitButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 16px rgba(102, 126, 234, 0.3) !important;
    }
    
    .stFormSubmitButton button:active {
        transform: translateY(0) !important;
    }
    
    /* Error styling */
    .stError {
        background: rgba(239, 68, 68, 0.1) !important;
        border-left: 4px solid #ef4444 !important;
        border-radius: 8px !important;
        padding: 1rem !important;
    }
    
    /* Success styling */
    .stSuccess {
        background: rgba(34, 197, 94, 0.1) !important;
        border-left: 4px solid #22c55e !important;
        border-radius: 8px !important;
        padding: 1rem !important;
        font-weight: 500 !important;
    }
    
    /* Spinner styling */
    .stSpinner {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Face thumbnails */
    .face-thumbnails {
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
        margin: 1.5rem 0;
    }
    
    .face-thumb {
        border-radius: 12px;
        border: 2px solid rgba(102, 126, 234, 0.3);
        overflow: hidden;
        transition: all 0.3s ease;
    }
    
    .face-thumb:hover {
        transform: scale(1.05);
        border-color: #667eea;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
    }
    
    /* Caption text */
    .stCaption {
        font-size: 0.95rem !important;
        opacity: 0.8 !important;
        font-weight: 500 !important;
    }
    
    /* Info text */
    .info-text {
        background: rgba(59, 130, 246, 0.1);
        border-left: 4px solid #3b82f6;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    
    /* Divider styling */
    hr {
        margin: 2rem 0 !important;
        opacity: 0.2 !important;
    }
    
    @media (max-width: 768px) {
        .title-container h1 {
            font-size: 2rem;
        }
        
        .form-card, .upload-card {
            padding: 1.5rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# ── Header Section ───────────────────────────────────────────────────────────
st.markdown("""
    <div class="title-container">
        <h1>🔍 FaceTrace AI</h1>
        <p class="subtitle-text">Help us locate missing persons by reporting sightings</p>
    </div>
    """, unsafe_allow_html=True)


# ── Upload Mode Selection ────────────────────────────────────────────────────
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    upload_mode = st.radio(
        "**Select Upload Type**",
        options=["📷 Image", "🎥 Video"],
        horizontal=True,
        label_visibility="collapsed"
    )
    upload_mode = upload_mode.split()[-1]  # Extract just "Image" or "Video"

st.markdown("---")

# Initialize variables that will be used
save_flag = 0
extracted_faces = []
face_mesh = None
face_detected = False
unique_id = None
uploaded_file_path = None
image_obj = None
video_obj = None

# Create columns for layout
image_col, form_col = st.columns([1, 1], gap="large")

# ── Image upload ──────────────────────────────────────────────────────────────
if upload_mode == "Image":
    
    with image_col:
        st.markdown("<div class='upload-card'>", unsafe_allow_html=True)
        st.markdown("#### 📸 Upload Photo")
        st.markdown("Upload a clear photo of the person you saw")
        
        image_obj = st.file_uploader(
            "Upload photo", 
            type=["jpg", "jpeg", "png"], 
            key="user_submission_img",
            label_visibility="collapsed"
        )
        
        if image_obj:
            file_key = f"{image_obj.name}:{image_obj.size}"
            if st.session_state.get("public_image_key") != file_key:
                unique_id = str(uuid.uuid4())
                with st.spinner("🔍 Processing image and detecting face..."):
                    uploaded_file_path = get_resources_dir() / f"{unique_id}.jpg"
                    with open(uploaded_file_path, "wb") as f:
                        f.write(image_obj.getvalue())

                    image_numpy = image_obj_to_numpy(image_obj)
                    face_mesh = extract_face_mesh_landmarks(image_numpy)
                    if face_mesh is None:
                        uploaded_file_path.unlink(missing_ok=True)
                        uploaded_file_path = None

                st.session_state["public_image_key"] = file_key
                st.session_state["public_image_id"] = unique_id
                st.session_state["public_image_path"] = uploaded_file_path
                st.session_state["public_image_face_mesh"] = face_mesh
                st.session_state["public_image_data"] = base64.b64encode(
                    image_obj.getvalue()
                ).decode("ascii")

            unique_id = st.session_state.get("public_image_id")
            uploaded_file_path = st.session_state.get("public_image_path")
            face_mesh = st.session_state.get("public_image_face_mesh")
            image_data = st.session_state.get("public_image_data")
            image_obj.seek(0)
            st.image(image_obj, caption="📷 Uploaded Photo", width="stretch")

            if face_mesh is None:
                st.markdown("""
                    <div class="info-text">
                    ⚠️ <strong>No face detected</strong><br>
                    Please upload a clear photo showing a face
                    </div>
                    """, unsafe_allow_html=True)
            else:
                face_detected = True
                st.markdown("""
                    <div style="background: rgba(34, 197, 94, 0.1); border-left: 4px solid #22c55e;
                               padding: 1rem; border-radius: 8px; margin: 1rem 0;">
                    ✅ <strong>Face Detected!</strong><br>
                    Ready to submit your sighting
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

    if image_obj and face_detected:
        with form_col:
            st.markdown("<div class='form-card'>", unsafe_allow_html=True)
            st.markdown("<div class='form-title'>📝 Your Information</div>", unsafe_allow_html=True)
            
            with st.form(key="image_submission_form"):
                st.markdown("**Your Name** <span style='color: #ef4444;'>*</span>", unsafe_allow_html=True)
                sub_name = st.text_input("Full Name", placeholder="Enter your full name", label_visibility="collapsed")
                
                st.markdown("**Mobile Number** <span style='color: #ef4444;'>*</span>", unsafe_allow_html=True)
                mobile_number = st.text_input(
                    "Mobile", 
                    placeholder="10-digit phone number", 
                    label_visibility="collapsed"
                )
                
                st.markdown("**Email Address**", unsafe_allow_html=True)
                email = st.text_input("Email", placeholder="your.email@example.com", label_visibility="collapsed")
                
                st.markdown("**Location Where Sighting Occurred** <span style='color: #ef4444;'>*</span>", unsafe_allow_html=True)
                address = st.text_input(
                    "Location", 
                    placeholder="City, area, or specific location", 
                    label_visibility="collapsed"
                )
                
                st.markdown("**Birth Marks / Identifying Features**", unsafe_allow_html=True)
                birth_marks = st.text_input(
                    "Marks", 
                    placeholder="Scars, moles, tattoos, etc.", 
                    label_visibility="collapsed"
                )

                st.markdown("<br>", unsafe_allow_html=True)
                submit_bt = st.form_submit_button(
                    "✅ Submit Sighting", use_container_width=True
                )

                if submit_bt:
                    errors = []
                    if not sub_name.strip():
                        errors.append("❌ Your Name is required.")
                    if not mobile_number.strip():
                        errors.append("❌ Mobile Number is required.")
                    elif (
                        not mobile_number.strip().isdigit()
                        or len(mobile_number.strip()) != 10
                    ):
                        errors.append("❌ Mobile Number must be exactly 10 digits.")
                    if not address.strip():
                        errors.append("❌ Location is required.")

                    if errors:
                        for err in errors:
                            st.error(err)
                    else:
                        details = PublicSubmissions(
                            submitted_by=sub_name.strip(),
                            location=address.strip(),
                            email=email.strip() or None,
                            face_mesh=json.dumps(face_mesh),
                            id=unique_id,
                            mobile=mobile_number.strip(),
                            birth_marks=birth_marks.strip() or None,
                            image_data=image_data,
                            status="NF",
                        )
                        db_queries.new_public_case(details)
                        confirmed_matches = db_queries.auto_confirm_public_matches()
                        save_flag = 1

            if save_flag == 1:
                st.markdown("""
                    <div style="background: rgba(34, 197, 94, 0.1); border-left: 4px solid #22c55e; 
                               padding: 1.5rem; border-radius: 10px; margin: 1rem 0; text-align: center;">
                    <h3 style="margin: 0; color: #22c55e;">✅ Submission Received!</h3>
                    <p style="margin: 0.5rem 0 0 0; opacity: 0.8;">Thank you for helping find missing persons</p>
                    </div>
                    """, unsafe_allow_html=True)
                if confirmed_matches:
                    st.success("✅ AI confirmed this sighting and marked the case as Found.")
            
            st.markdown("</div>", unsafe_allow_html=True)

# ── Video upload ──────────────────────────────────────────────────────────────
else:
    with image_col:
        st.markdown("<div class='upload-card'>", unsafe_allow_html=True)
        st.markdown("#### 🎥 Upload Video")
        st.markdown("Upload a video clearly showing the person's face")
        
        video_obj = st.file_uploader(
            "Upload video", 
            type=["mp4", "mov", "avi"], 
            key="user_submission_video",
            label_visibility="collapsed"
        )
        
        if video_obj:
            video_key = f"{video_obj.name}:{video_obj.size}"
            if st.session_state.get("public_video_key") != video_key:
                suffix = "." + video_obj.name.rsplit(".", 1)[-1]
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(video_obj.getvalue())
                        tmp_path = tmp.name
                    with st.spinner("🎬 Extracting faces from video..."):
                        extracted_faces = extract_unique_faces_from_video(tmp_path)
                finally:
                    if tmp_path:
                        os.unlink(tmp_path)
                st.session_state["public_video_key"] = video_key
                st.session_state["public_video_faces"] = extracted_faces
            else:
                extracted_faces = st.session_state.get("public_video_faces", [])

                if not extracted_faces:
                    st.markdown("""
                        <div class="info-text">
                        ⚠️ <strong>No faces detected in video</strong><br>
                        Tips: Ensure video shows clear front-facing view in good lighting
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                        <div style="background: rgba(34, 197, 94, 0.1); border-left: 4px solid #22c55e; 
                                   padding: 1rem; border-radius: 8px; margin: 1rem 0;">
                        ✅ <strong>Found {len(extracted_faces)} Unique Face(s)</strong><br>
                        Ready to submit your sighting
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("**📸 Detected Faces:**")
                    thumb_cols = st.columns(min(len(extracted_faces), 4))
                    for idx, (_, frame_rgb) in enumerate(extracted_faces):
                        with thumb_cols[idx % 4]:
                            st.image(frame_rgb, width=120)
        
        st.markdown("</div>", unsafe_allow_html=True)

    if extracted_faces:
        with form_col:
            st.markdown("<div class='form-card'>", unsafe_allow_html=True)
            st.markdown("<div class='form-title'>📝 Your Information</div>", unsafe_allow_html=True)
            
            with st.form(key="video_submission_form"):
                st.markdown("**Your Name** <span style='color: #ef4444;'>*</span>", unsafe_allow_html=True)
                sub_name = st.text_input("Full Name", placeholder="Enter your full name", label_visibility="collapsed")
                
                st.markdown("**Mobile Number** <span style='color: #ef4444;'>*</span>", unsafe_allow_html=True)
                mobile_number = st.text_input(
                    "Mobile", 
                    placeholder="10-digit phone number", 
                    label_visibility="collapsed"
                )
                
                st.markdown("**Email Address**", unsafe_allow_html=True)
                email = st.text_input("Email", placeholder="your.email@example.com", label_visibility="collapsed")
                
                st.markdown("**Location Where Sighting Occurred** <span style='color: #ef4444;'>*</span>", unsafe_allow_html=True)
                address = st.text_input(
                    "Location", 
                    placeholder="City, area, or specific location", 
                    label_visibility="collapsed"
                )
                
                st.markdown("**Birth Marks / Identifying Features**", unsafe_allow_html=True)
                birth_marks = st.text_input(
                    "Marks", 
                    placeholder="Scars, moles, tattoos, etc.", 
                    label_visibility="collapsed"
                )

                st.markdown("<br>", unsafe_allow_html=True)
                submit_bt = st.form_submit_button(
                    f"✅ Submit {len(extracted_faces)} Face(s)",
                    use_container_width=True,
                )

                if submit_bt:
                    errors = []
                    if not sub_name.strip():
                        errors.append("❌ Your Name is required.")
                    if not mobile_number.strip():
                        errors.append("❌ Mobile Number is required.")
                    elif (
                        not mobile_number.strip().isdigit()
                        or len(mobile_number.strip()) != 10
                    ):
                        errors.append("❌ Mobile Number must be exactly 10 digits.")
                    if not address.strip():
                        errors.append("❌ Location is required.")

                    if errors:
                        for err in errors:
                            st.error(err)
                    else:
                        count = 0
                        for landmarks, _ in extracted_faces:
                            sub_id = str(uuid.uuid4())
                            details = PublicSubmissions(
                                submitted_by=sub_name.strip(),
                                location=address.strip(),
                                email=email.strip() or None,
                                face_mesh=json.dumps(landmarks),
                                id=sub_id,
                                mobile=mobile_number.strip(),
                                birth_marks=birth_marks.strip() or None,
                                status="NF",
                            )
                            db_queries.new_public_case(details)
                            count += 1
                        confirmed_matches = db_queries.auto_confirm_public_matches()
                        
                        st.markdown(f"""
                            <div style="background: rgba(34, 197, 94, 0.1); border-left: 4px solid #22c55e; 
                                       padding: 1.5rem; border-radius: 10px; margin: 1rem 0; text-align: center;">
                            <h3 style="margin: 0; color: #22c55e;">✅ {count} Submission(s) Received!</h3>
                            <p style="margin: 0.5rem 0 0 0; opacity: 0.8;">Thank you for helping find missing persons</p>
                            </div>
                            """, unsafe_allow_html=True)
                        if confirmed_matches:
                            st.success(
                                "✅ AI confirmed a matching sighting and marked the case as Found."
                            )
            
            st.markdown("</div>", unsafe_allow_html=True)
