import inspect
import json
import urllib.request
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None
import PIL
import PIL.ImageDraw
import PIL.ImageFont
import numpy as np
import streamlit as st
try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
except ImportError:
    mp = None
    mp_python = None
    mp_vision = None
from streamlit.elements.image import ImageMixin


def _normalize_streamlit_kwargs(func, kwargs: dict) -> dict:
    """Translate newer Streamlit kwargs to the names supported by this environment."""
    if not kwargs:
        return kwargs
    signature = inspect.signature(func)
    new_kwargs = dict(kwargs)
    if new_kwargs.get("width") == "stretch" and "width" in signature.parameters:
        new_kwargs.pop("width")
        if "use_container_width" in signature.parameters:
            new_kwargs["use_container_width"] = True
        elif "use_column_width" in signature.parameters:
            new_kwargs["use_column_width"] = True

    if "use_container_width" not in new_kwargs:
        return new_kwargs

    if "use_column_width" in signature.parameters and "use_container_width" not in signature.parameters:
        new_kwargs["use_column_width"] = new_kwargs.pop("use_container_width")
    return new_kwargs


def render_image(*args, **kwargs):
    return st.image(*args, **_normalize_streamlit_kwargs(ImageMixin.image, kwargs))


def render_dataframe(data, **kwargs):
    return st.dataframe(data, **_normalize_streamlit_kwargs(st.dataframe, kwargs))


def is_user_authenticated(session_state: dict | None = None) -> bool:
    state = session_state or {}
    auth_value = state.get("authentication_status")
    if auth_value is True:
        return True
    if state.get("login_status") is True:
        return True
    if state.get("username") or state.get("user"):
        return True
    return False


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_resources_dir() -> Path:
    resources_dir = get_project_root() / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    return resources_dir


def get_login_config_path() -> Path:
    return get_project_root() / "login_config.yml"


def get_database_path() -> Path:
    return get_project_root() / "sqlite_database.db"


def get_model_path() -> Path:
    return get_project_root() / "face_landmarker.task"


def get_case_image_path(case_id: str) -> Path | None:
    """Return the stored image path for a case, or None when it is unavailable."""
    image_path = get_resources_dir() / f"{case_id}.jpg"
    return image_path if image_path.exists() else None


def get_matching_image_path(face_mesh: str | list | None) -> Path | None:
    """Find a stored image whose landmarks exactly match a case's face mesh."""
    if not face_mesh:
        return None
    try:
        target = np.asarray(json.loads(face_mesh) if isinstance(face_mesh, str) else face_mesh)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    for image_path in get_resources_dir().glob("*.jpg"):
        try:
            image = PIL.Image.open(image_path).convert("RGB")
            landmarks = extract_face_mesh_from_frame(np.asarray(image))
            if landmarks is not None and np.array_equal(target, np.asarray(landmarks)):
                return image_path
        except Exception:
            continue
    return None


_MODEL_PATH = str(get_model_path())
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
_FACE_MODEL_DIR = get_resources_dir() / "models"
_FACE_DETECTOR_PATH = _FACE_MODEL_DIR / "face_detection_yunet_2023mar.onnx"
_FACE_RECOGNIZER_PATH = _FACE_MODEL_DIR / "face_recognition_sface_2021dec.onnx"
_FACE_DETECTOR_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
    "face_detection_yunet_2023mar.onnx"
)
_FACE_RECOGNIZER_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/"
    "face_recognition_sface_2021dec.onnx"
)


def _ensure_model():
    if not get_model_path().exists():
        get_model_path().parent.mkdir(parents=True, exist_ok=True)
        with st.spinner("Downloading face landmarker model (one-time, ~30 MB)..."):
            urllib.request.urlretrieve(_MODEL_URL, str(get_model_path()))


def _ensure_model_silent():
    if not get_model_path().exists():
        get_model_path().parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(_MODEL_URL, str(get_model_path()))


def _ensure_face_models():
    _FACE_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not _FACE_DETECTOR_PATH.exists():
        urllib.request.urlretrieve(_FACE_DETECTOR_URL, str(_FACE_DETECTOR_PATH))
    if not _FACE_RECOGNIZER_PATH.exists():
        urllib.request.urlretrieve(_FACE_RECOGNIZER_URL, str(_FACE_RECOGNIZER_PATH))


@st.cache_resource
def _build_face_recognizer():
    if cv2 is None:
        raise RuntimeError("OpenCV is unavailable in this deployment environment.")
    _ensure_face_models()
    detector = cv2.FaceDetectorYN.create(
        str(_FACE_DETECTOR_PATH), "", (320, 320), 0.6, 0.3, 5000
    )
    recognizer = cv2.FaceRecognizerSF.create(str(_FACE_RECOGNIZER_PATH), "")
    return detector, recognizer


def _detect_identity_faces(image: np.ndarray) -> list[dict]:
    """Detect faces with YuNet and return boxes plus SFace embeddings."""
    image = cv2.cvtColor(_normalize_image(image), cv2.COLOR_RGB2BGR)
    detector, recognizer = _build_face_recognizer()
    height, width = image.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(image)
    if faces is None:
        return []

    identity_faces = []
    for face in faces:
        aligned = recognizer.alignCrop(image, face)
        feature = recognizer.feature(aligned)
        x, y, box_width, box_height = face[:4]
        identity_faces.append(
            {
                "bbox": (
                    max(0, int(x)),
                    max(0, int(y)),
                    min(width, int(x + box_width)),
                    min(height, int(y + box_height)),
                ),
                "embedding": feature.reshape(-1).astype(float).tolist(),
            }
        )
    return identity_faces


def extract_face_embeddings(image: np.ndarray) -> list[list[float]]:
    """Return SFace identity embeddings, one for each detected face."""
    return [face["embedding"] for face in _detect_identity_faces(image)]


def _build_detector(num_faces: int = 5):
    if mp is None or mp_python is None or mp_vision is None:
        raise RuntimeError("Face detection dependencies are unavailable in this deployment environment.")
    base_options = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
    options = mp_vision.FaceLandmarkerOptions(
        base_options=base_options,
        num_faces=num_faces,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False,
    )
    return mp_vision.FaceLandmarker.create_from_options(options)


def _normalize_image(image: np.ndarray) -> np.ndarray:
    if image.dtype != np.uint8:
        image = image.astype(np.uint8)
    if image.ndim == 2:
        image = np.stack([image] * 3, axis=-1)
    elif image.shape[2] == 4:
        image = image[:, :, :3]
    return image


def image_obj_to_numpy(image_obj) -> np.ndarray:
    """Convert a Streamlit-uploaded image object to an RGB numpy array."""
    image = PIL.Image.open(image_obj).convert("RGB")
    return np.array(image)


def detect_all_faces(image: np.ndarray, max_faces: int = 5):
    """
    Detect up to max_faces in an image.

    Returns a list of dicts, one per detected face:
        {
            "landmarks": [x1,y1,z1, x2,y2,z2, ...],   # flattened, normalised
            "bbox": (x_min, y_min, x_max, y_max),      # pixel coords
        }
    Returns an empty list if no faces are found.
    """
    _ensure_model()
    image = _normalize_image(image)
    h, w = image.shape[:2]

    try:
        detector = _build_detector(num_faces=max_faces)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        result = detector.detect(mp_image)
        detector.close()
    except Exception as e:
        st.error(f"❌ Face detection failed: {e}")
        return []

    faces = []
    try:
        identity_embeddings = extract_face_embeddings(image)
    except Exception:
        identity_embeddings = []
    for lm_list in result.face_landmarks:
        xs = [lm.x * w for lm in lm_list]
        ys = [lm.y * h for lm in lm_list]
        padding = 0.08 * max(w, h)
        bbox = (
            max(0, int(min(xs) - padding)),
            max(0, int(min(ys) - padding)),
            min(w, int(max(xs) + padding)),
            min(h, int(max(ys) + padding)),
        )
        landmarks_flat = [coord for lm in lm_list for coord in (lm.x, lm.y, lm.z)]
        embedding = None
        if len(identity_embeddings) == len(result.face_landmarks):
            embedding = identity_embeddings[len(faces)]
        faces.append(
            {"landmarks": landmarks_flat, "bbox": bbox, "embedding": embedding}
        )

    if not faces:
        try:
            # MediaPipe is best for mesh landmarks; YuNet/SFace handles
            # profile, tilted, low-contrast, and smaller faces.
            for identity_face in _detect_identity_faces(image):
                faces.append(
                    {
                        "landmarks": [],
                        "bbox": identity_face["bbox"],
                        "embedding": identity_face["embedding"],
                    }
                )
        except Exception as exc:
            st.warning(f"Face detector fallback failed: {exc}")
    return faces


# Distinct colours for up to 5 faces (unselected state)
_FACE_COLORS = [
    (255, 200, 0),  # yellow
    (0, 180, 255),  # cyan
    (255, 100, 0),  # orange
    (180, 0, 255),  # purple
    (255, 0, 150),  # pink
]
_SELECTED_COLOR = (50, 220, 80)  # green
_UNSELECTED_DIM = (160, 160, 160)  # grey when another face is selected


def draw_face_boxes(
    image_numpy: np.ndarray, faces: list, selected_idx: int = None
) -> PIL.Image.Image:
    """
    Draw labelled bounding boxes around detected faces.

    - Single face: one green box labelled "Face detected"
    - Multiple faces, nothing selected: each box gets a distinct colour + number
    - Multiple faces, one selected: selected = bright green, others = grey + number
    """
    img = PIL.Image.fromarray(_normalize_image(image_numpy))
    draw = PIL.ImageDraw.Draw(img)
    n = len(faces)

    for i, face in enumerate(faces):
        x0, y0, x1, y1 = face["bbox"]
        box_w = max(1, (x1 - x0) // 200 + 2)  # line width scales with box size

        if n == 1:
            color = _SELECTED_COLOR
            label = "Face detected"
        elif selected_idx is None:
            color = _FACE_COLORS[i % len(_FACE_COLORS)]
            label = f"Face {i + 1}"
        elif i == selected_idx:
            color = _SELECTED_COLOR
            label = f"Face {i + 1} (selected)"
        else:
            color = _UNSELECTED_DIM
            label = f"Face {i + 1}"

        # Draw rounded-corner-ish box with a slightly thicker outline
        for offset in range(box_w):
            draw.rectangle(
                [x0 - offset, y0 - offset, x1 + offset, y1 + offset],
                outline=color,
            )

        # Label background + text
        font_size = max(12, (y1 - y0) // 8)
        text_x, text_y = x0, max(0, y0 - font_size - 4)
        draw.rectangle(
            [
                text_x,
                text_y,
                text_x + len(label) * font_size // 2 + 8,
                text_y + font_size + 4,
            ],
            fill=color,
        )
        draw.text((text_x + 4, text_y + 2), label, fill=(0, 0, 0))

    return img


# ── Single-face helper (kept for mobile_app compatibility) ────────────────────


def extract_face_mesh_landmarks(image: np.ndarray):
    """
    Extract face mesh landmarks for exactly one face.
    Shows a Streamlit error if none found. Returns None on failure.
    """
    faces = detect_all_faces(image, max_faces=1)
    if not faces:
        st.error(
            "❌ No face detected in this image.\n\n"
            "**Tips for a better result:**\n"
            "- Ensure the face is clearly visible and not obscured\n"
            "- Use good lighting — avoid dark or back-lit photos\n"
            "- Use a front-facing photo where possible"
        )
        return None
    return faces[0].get("embedding") or faces[0]["landmarks"]


# ── Frame-level helper (video) ────────────────────────────────────────────────


def extract_face_mesh_from_frame(frame_rgb: np.ndarray):
    """Silent version for batch/video use. Returns landmarks or None."""
    _ensure_model_silent()
    frame_rgb = _normalize_image(frame_rgb)
    try:
        detector = _build_detector(num_faces=1)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = detector.detect(mp_image)
        detector.close()
        if result.face_landmarks:
            lm_list = result.face_landmarks[0]
            return [coord for lm in lm_list for coord in (lm.x, lm.y, lm.z)]
        return None
    except Exception:
        return None


def extract_face_feature_from_frame(frame_rgb: np.ndarray):
    """Return an identity embedding for the largest face in a video frame."""
    embeddings = extract_face_embeddings(frame_rgb)
    return embeddings[0] if embeddings else None


def _cosine_distance(a: list, b: list) -> float:
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 1.0
    return 1.0 - float(np.dot(a, b) / denom)


def extract_unique_faces_from_video(
    video_path: str,
    frame_interval: int = 15,
    similarity_threshold: float = 0.05,
):
    """
    Extract unique face landmarks from a video file.
    Returns list of (landmarks, frame_rgb) tuples — one per unique face.
    """
    _ensure_model_silent()
    if cv2 is None:
        st.error("Video processing is unavailable in this deployment environment.")
        return []
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    unique_faces = []
    frame_idx = 0
    while True:
        ret, frame_bgr = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            landmarks = extract_face_feature_from_frame(frame_rgb)
            if landmarks is not None:
                is_duplicate = any(
                    _cosine_distance(landmarks, ex_lm) < similarity_threshold
                    for ex_lm, _ in unique_faces
                )
                if not is_duplicate:
                    unique_faces.append((landmarks, frame_rgb))
        frame_idx += 1

    cap.release()
    return unique_faces
