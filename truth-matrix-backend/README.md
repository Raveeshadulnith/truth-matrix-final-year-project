# Truth Matrix Backend

Truth Matrix is a FastAPI backend for the final year project **Deepfake Detection Web Application and Browser Extension with Explainable AI**.

This backend receives image, video, and audio uploads from the React frontend, and public image URL scans from the browser extension. Image and video inference are connected to the trained PyTorch checkpoints in `models/`; audio returns a clear "not ready" response until the trained audio checkpoint is available.

## Features

- FastAPI backend API
- CORS support for frontend and browser extension calls
- Image, video, and audio upload endpoints
- Trained EfficientNet-B4 image checkpoint inference
- Trained EfficientNet-B4 + BiLSTM video checkpoint inference
- Browser extension image URL download and analysis
- Temporary upload storage in `uploads/`
- Automatic temporary file deletion after analysis
- Static file serving from `results/`
- Grad-CAM image and video XAI heatmap generation in `results/`
- Swagger API documentation

## Project Structure

```text
truth-matrix-backend/
├── main.py
├── requirements.txt
├── README.md
├── .env
├── .gitignore
├── uploads/
│   └── .gitkeep
├── results/
│   └── .gitkeep
├── models/
│   ├── image_model.pth
│   └── video_model_celebdf.pth
├── ml/
│   ├── __init__.py
│   ├── model_common.py
│   ├── image_inference.py
│   ├── video_inference.py
│   └── audio_inference.py
├── utils/
│   ├── __init__.py
│   └── file_utils.py
└── schemas/
    ├── __init__.py
    └── response_schema.py
```

## Setup

Open a terminal in the parent project folder, then run:

```bash
cd truth-matrix-backend
python -m venv venv
```

Activate the virtual environment on Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the backend:

```bash
uvicorn main:app --reload
```

The backend will run at:

```text
http://127.0.0.1:8000
```

Swagger docs will be available at:

```text
http://127.0.0.1:8000/docs
```

## Environment Variables

The backend reads `truth-matrix-backend/.env` directly with real local credentials and model settings. Keep this file local only; it is ignored by git because it can contain Supabase, Firebase, and service-role secrets.

```env
FRONTEND_URL=http://localhost:5173
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=...
FIREBASE_STORAGE_BUCKET=...
FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json
```

Model and XAI settings are also read from the same `.env` file:

```env
IMAGE_MODEL_PATH=./models/image_model.pth
VIDEO_MODEL_PATH=./models/video_model_celebdf.pth
MODEL_INPUT_SIZE=224
IMAGE_MODEL_INPUT_SIZE=380
VIDEO_FRAME_COUNT=16
MODEL_FAKE_CLASS_INDEX=1
IMAGE_FAKE_CLASS_INDEX=0
VIDEO_FAKE_CLASS_INDEX=1
VIDEO_LSTM_POOLING=last
GENERATE_IMAGE_HEATMAPS=true
GENERATE_VIDEO_HEATMAPS=true
IMAGE_GRADCAM_TARGET=fake
IMAGE_GRADCAM_LAYER=blocks.4
IMAGE_GRADCAM_POSITIVE_GRADIENTS=true
IMAGE_GRADCAM_PERCENTILE=98
IMAGE_HEATMAP_COLORMAP=turbo
IMAGE_HEATMAP_ALPHA=0.45
IMAGE_HEATMAP_BLUR=5
IMAGE_HEATMAP_GAMMA=0.75
IMAGE_XAI_PANEL_HEIGHT=360
VIDEO_HEATMAP_FRAMES=8
MAX_REMOTE_IMAGE_BYTES=15728640
```

The bundled image checkpoint is configured with `IMAGE_FAKE_CLASS_INDEX=0`. If a future checkpoint was trained with a different class order, change the modality-specific `*_FAKE_CLASS_INDEX`.

## Endpoints

### Health Check

```http
GET /
```

Response:

```json
{
  "message": "Truth Matrix Deepfake Detection Backend is running"
}
```

### Analyze Image

```http
POST /api/analyze/image
```

Accepted file types:

```text
jpg, jpeg, png, webp
```

Example response:

```json
{
  "media_type": "image",
  "label": "Suspected Deepfake",
  "confidence": 91.28,
  "fake_probability": 91.28,
  "authentic_probability": 8.72,
  "explanation": "The trained image model detected manipulation signals. Deepfake probability: 91.28%; authentic probability: 8.72%.",
  "heatmap_url": "/results/example-heatmap.jpg",
  "xai_method": "Grad-CAM"
}
```

### Analyze Video

```http
POST /api/analyze/video
```

Accepted file types:

```text
mp4, mov, avi, mkv
```

Example response:

```json
{
  "media_type": "video",
  "label": "Suspected Deepfake",
  "confidence": 88.4,
  "fake_probability": 88.4,
  "authentic_probability": 11.6,
  "frames_analyzed": 16,
  "explanation": "The trained video model detected manipulation signals. Deepfake probability: 88.40%; authentic probability: 11.60%.",
  "heatmap_url": "/results/example-video-gradcam.jpg",
  "xai_method": "Grad-CAM"
}
```

### Analyze Audio

```http
POST /api/analyze/audio
```

Accepted file types:

```text
wav, mp3, m4a
```

The audio model is still in progress. Until `ml/audio_inference.py` is connected to a trained checkpoint, this endpoint returns HTTP `501`:

```json
{
  "detail": "Audio analysis is not connected yet because the trained audio model is still in progress."
}
```

## Frontend API Helper

Example file path in your React frontend:

```text
src/api/deepfakeApi.js
```

```javascript
const API_BASE_URL = "http://127.0.0.1:8000";

async function uploadForAnalysis(endpoint, file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    body: formData,
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Analysis request failed");
  }

  return data;
}

export function analyzeImage(file) {
  return uploadForAnalysis("/api/analyze/image", file);
}

export function analyzeVideo(file) {
  return uploadForAnalysis("/api/analyze/video", file);
}

export function analyzeAudio(file) {
  return uploadForAnalysis("/api/analyze/audio", file);
}
```

## Trained Model Files

Keep large trained artifacts in `models/`. The repository `.gitignore` excludes `models/` and `*.pth`, so these checkpoints stay local unless you intentionally publish them somewhere else.

- `models/image_model.pth`: EfficientNet-B4 image classifier checkpoint
- `models/video_model_celebdf.pth`: EfficientNet-B4 frame encoder + two-layer bidirectional LSTM video classifier checkpoint

The browser extension calls `POST /api/analyze/image-url`; the backend downloads that image temporarily, runs the same trained image model, returns the result, then deletes the temporary download.

## Explainable AI

Truth Matrix returns Grad-CAM XAI artifacts through `heatmap_url`.

- Image analysis returns a Grad-CAM overlay for the uploaded or extension-scanned image.
- Video analysis returns a Grad-CAM contact sheet for sampled frames from the uploaded video.
- Heatmap files are written to `results/` and served by FastAPI under `/results/...`.

Use `GENERATE_IMAGE_HEATMAPS=false` or `GENERATE_VIDEO_HEATMAPS=false` only when you need faster inference and can skip XAI output.
