# Truth Matrix Backend

Truth Matrix is a FastAPI backend for the final year project **Deepfake Detection Web Application and Browser Extension with Explainable AI**.

This backend receives image, video, and audio uploads from the React frontend and browser extension. Video detection uses the local Keras frame classifier at `ml/models/deepfake-detection-video-model1.h5`; audio inference is still a placeholder.

## Features

- FastAPI backend API
- CORS support for frontend and browser extension calls
- Image, video, and audio upload endpoints
- Temporary upload storage in `uploads/`
- Automatic temporary file deletion after analysis
- Static file serving from `results/`
- Keras video inference with bounded frame sampling and upload validation
- Swagger API documentation

## Project Structure

```text
truth-matrix-backend/
├── main.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── uploads/
│   └── .gitkeep
├── results/
│   └── .gitkeep
├── ml/
│   ├── __init__.py
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

The video pipeline supports these optional settings:

```env
FRONTEND_URL=http://localhost:5173
MAX_VIDEO_UPLOAD_BYTES=104857600
VIDEO_NUM_FRAMES=16
VIDEO_FRAME_SIZE=224
VIDEO_FAKE_THRESHOLD=0.5
VIDEO_SIGMOID_FAKE_VALUE=1
VIDEO_KERAS_BACKEND=torch
```

`VIDEO_SIGMOID_FAKE_VALUE=1` means the model's sigmoid output is interpreted as the deepfake probability. Keep this setting consistent with the model's training labels.

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
  "label": "Authentic",
  "confidence": 91.28,
  "explanation": "Temporary dummy result. Replace this with trained image model prediction later.",
  "heatmap_url": null
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
  "label": "Authentic",
  "confidence": 64.1,
  "fake_probability": 35.9,
  "authentic_probability": 64.1,
  "frames_analyzed": 16,
  "video_metadata": {
    "duration_seconds": 248.3,
    "fps": 30.0,
    "width": 1280,
    "height": 720,
    "total_frames": 7449
  },
  "explanation": "The Keras video model analyzed 16 frames sampled across the video..."
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

Example response:

```json
{
  "media_type": "audio",
  "label": "Authentic",
  "confidence": 84.75,
  "explanation": "Temporary dummy result. Replace this with trained audio model prediction later."
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

Video explainability and heatmap generation are intentionally deferred. The current video endpoint returns detection probabilities, sampled-frame count, and container metadata.
