# FaceTrace-AI: Missing Person Identification System

![Issues](https://img.shields.io/github/issues/gaganmanku96/Finding-missing-person-using-AI) ![Stars](https://img.shields.io/github/stars/gaganmanku96/Finding-missing-person-using-AI?style=social)
![CodeRabbit Reviews](https://img.shields.io/coderabbit/prs/github/gaganmanku96/Finding-missing-person-using-AI?utm_source=oss&utm_medium=github&utm_campaign=gaganmanku96%2FFinding-missing-person-using-AI&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)

![Streamlit](https://img.shields.io/badge/Streamlit-000000?style=for-the-badge&logo=streamlit&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-000000?style=for-the-badge&logo=mediapipe&logoColor=white)
![Python](https://img.shields.io/badge/Python-000000?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-000000?style=for-the-badge&logo=postgresql&logoColor=white)

Admin URL : https://yyelz3g4gcjkrudqkbnekr.streamlit.app/


Public URL : https://mobileapppy-agprmysksydbfafyltug9d.streamlit.app


---

> **Disclaimer**
>
> All images of individuals appearing in the screenshots and used as sample data in this project were sourced from the internet solely for the purpose of demonstrating the facial recognition pipeline in a non-commercial, educational context. These images are the property of their respective owners. No claim of ownership is made. If you are the rights holder of any image and wish it to be removed, please open an issue and it will be taken down promptly.
>
> This project does not store, distribute, or commercialise any personal images. The face data derived from sample images (landmark vectors) is used only locally for matching demonstration and is not shared with any third party.

---

## Table of Contents

- [The Problem](#the-problem)
- [A Case, Start to Finish](#a-case-start-to-finish)
- [How It Works](#how-it-works)
- [Features](#features)
- [Getting Started](#getting-started)
- [Configuring Login Credentials](#configuring-login-credentials)
- [Seeding Demo Data](#seeding-demo-data)
- [Tech Stack](#tech-stack)
- [FAQ](#faq)

---

## The Problem

Hundreds of people — mostly children — go missing every day in India. When a sighting is reported, officers have to manually compare photos, sift through paperwork, and coordinate across stations. By the time a match is confirmed, the trail has often gone cold.

---

## A Case, Start to Finish

**Step 1 — Family files a report. Officer registers the case.**

A family in Haridwar reports their child missing. An officer opens the portal, uploads a photo, and the AI immediately detects the face and extracts a 468-point mesh — no manual tagging needed.

<img src="./assets/screenshots/register_new_case.png" alt="Register New Case — face detected with bounding box" width="700"/>

---

**Step 2 — The dashboard tracks every open case.**

The officer's home screen shows live counts of found and not-found cases, and a map that plots where cases are concentrated across India.

<img src="./assets/screenshots/homepage.png" alt="Officer dashboard with case counts and India map" width="700"/>

---

**Step 3 — A member of the public submits a sighting.**

Someone recognises the person and submits a photo through the public portal (no login required). The same face mesh is extracted and stored.

When an admin clicks **Match Cases**, the KNN model compares all sightings against all open cases. If a face is close enough, the case is automatically flipped to **Found** and the complainant is notified by email.

<img src="./assets/screenshots/view_cases.png" alt="View cases — Found status with sighting location and submitter details" width="700"/>

---

**Step 4 — The city map tells the bigger picture.**

Admins can see which cities have the most unresolved cases and track resolution rates over time.

<img src="./assets/screenshots/cases_by_city.png" alt="Cases by city — India map with city summary table" width="700"/>

---

## How It Works

1. **Officer registers a case** → uploads a photo → AI extracts a 468-point face mesh
2. **Public submits a sighting** → uploads a photo or video → same extraction
3. **Admin clicks Refresh** → KNN matches faces across both datasets → email sent to complainant on match

No manual photo comparison. No paperwork pile-up.

---

## Features

| Feature | Details |
|---|---|
| Face detection | MediaPipe Face Landmarker — highlights detected faces, handles multiple people in frame |
| AI matching | KNN on 1,404-dimensional face vectors; shows confidence % |
| Video sightings | Upload a video — unique faces extracted automatically per frame |
| Live map | Dashboard map showing case density by city across India |
| Email alerts | Auto-notifies complainant email when a match is confirmed |
| Role-based access | Admins can match, edit, delete; Officers can register and view |
| Public portal | Separate mobile-friendly submission page, no login needed |

---

## Getting Started

```bash
git clone https://github.com/SUBHAJIT-mallickbnj/-FaceTrace-AI.git
cd Finding-missing-person-using-AI
pip install -r requirements.txt
```

Run the officer/admin portal:
```bash
streamlit run Home.py
```

Run the public submission portal:
```bash
streamlit run mobile_app.py
```

The SQLite database and face landmarker model (~30 MB, auto-downloaded on first use) are created automatically.

### Optional: Email notifications

Set these environment variables to enable email alerts on match:
```
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
```
The complainant's email entered during case registration is used as the recipient.

### Recommended: Independent image backup

Images are stored in the shared PostgreSQL database. For recovery if PostgreSQL loses
an image, configure an independent S3-compatible bucket in Streamlit Cloud secrets:

```
IMAGE_BACKUP_BUCKET = "your-private-bucket"
IMAGE_BACKUP_ACCESS_KEY = "your-access-key"
IMAGE_BACKUP_SECRET_KEY = "your-secret-key"
IMAGE_BACKUP_REGION = "auto"
IMAGE_BACKUP_ENDPOINT_URL = "https://your-s3-endpoint" # omit for AWS S3
```

New admin and public images are written to PostgreSQL and the backup bucket. If a
database image is missing, the app restores it from the bucket automatically. Keep
the bucket private and enable versioning/retention according to your organisation's
data policy. Images that were already deleted from both PostgreSQL and local storage
cannot be reconstructed without another existing copy.

---

## Configuring Login Credentials

Credentials are stored in `login_config.yml`. To add or change a user:

**1. Generate a bcrypt password hash:**
```python
import bcrypt
print(bcrypt.hashpw(b"your_password", bcrypt.gensalt()).decode())
```

**2. Edit `login_config.yml`:**
```yaml
credentials:
  usernames:
    your_username:               # used as the login username
      name: Your Display Name
      email: you@example.com
      city: Delhi
      area: Sector 1
      role: Admin                # Admin or Officer
      password: '$2b$12$...'     # paste the hash from step 1
```

**Roles:**
| Role | Permissions |
|---|---|
| Admin | Register cases, view all cases, trigger matching, edit/delete cases |
| Officer | Register cases, view own cases |

> `login_config.yml` is git-ignored by default. Never commit real credentials.

---

## Seeding Demo Data

The `scripts/` folder contains two utilities for populating the database with demo data.

### Step 1 — Download sample images

```bash
# Download ~2 images per celebrity into scripts/bulk_data/reported/
uv run scripts/download_celebrity_images.py --dest reported

# Or split across both folders (reported + publicly_seen)
uv run scripts/download_celebrity_images.py --dest both
```

This uses DuckDuckGo image search — no API key needed.

You can also drop your own images directly into:
```
scripts/bulk_data/reported/        ← missing person cases
scripts/bulk_data/publicly_seen/   ← public sighting submissions
```

### Step 2 — Run the bulk upload

```bash
python scripts/bulk_upload.py
```

This processes every image in both folders:
- Extracts a face mesh using MediaPipe (images with no detectable face are skipped)
- Generates realistic metadata (names, cities, Aadhaar numbers, last-seen locations)
- Inserts records into the PostgreSQL database
- Copies images to `resources/` so the app can display them

By default `submitted_by` is set to `gagan` (the username in the default `login_config.yml`). If you've changed your username, pass it explicitly:

```bash
python scripts/bulk_upload.py --officer your_username
```

To reset and re-seed from scratch:
```bash
sqlite3 sqlite_database.db "DELETE FROM registeredcases; DELETE FROM publicsubmissions;"
python scripts/bulk_upload.py
```

---

## Tech Stack

- **Streamlit** — UI for both portals
- **MediaPipe Tasks** — face mesh landmark extraction (468 points × 3D)
- **scikit-learn KNN** — face matching
- **SQLModel + PostgreSQL** — data storage
- **Folium** — interactive map
- **OpenCV** — video frame extraction

---

## FAQ

**Q: Can I run this without an internet connection?**
The face landmarker model (~30 MB) is downloaded once on first run and cached locally. After that, both portals work fully offline.

**Q: How accurate is the face matching?**
Accuracy depends heavily on photo quality. Front-facing, well-lit photos work best. The confidence score shown on each match reflects KNN distance — higher is a stronger match.

**Q: Can I add multiple officers?**
Yes. Add as many usernames as needed to `login_config.yml`. Each officer sees only their own registered cases; Admins see all cases.

**Q: The map doesn't show a city I entered.**
The map uses a built-in city → coordinates lookup. If a city is missing, open an issue or add it to the `CITY_COORDS` dict in `Home.py`.

**Q: Where is the data stored?**
Everything is in `PostgreSQL_database.db` (git-ignored) in the project root. Images are stored as JPGs in `resources/` (also git-ignored). Nothing is sent to any external server.

**Q: How do I reset the database?**
```bash
PostgreSQL PostgreSQL_database.db "DELETE FROM registeredcases; DELETE FROM publicsubmissions;"
```
Or simply delete `PostgreSQL_database.db` — it will be recreated on next run.

**Q: Can the public portal be hosted separately from the officer portal?**
Yes. They are independent Streamlit apps (`Home.py` and `mobile_app.py`) and share only the SQLite database. Point both to the same database file path and they will work together.

---

*Thanks to the [MediaPipe](https://mediapipe.dev/) team for the open-source face landmarker model.*
