# Truth Matrix Backend

Truth Matrix is a FastAPI backend for the final year project **Deepfake Detection Web Application and Browser Extension with Explainable AI**.

This backend can receive image, video, and audio uploads from a React frontend or browser extension, run temporary dummy inference, and return a clean JSON response. The real dataset and trained PyTorch model integration can be added later inside the `ml/` files.

## Features

- FastAPI backend API
- CORS support for frontend and browser extension calls
- Image, video, and audio upload endpoints
- Temporary upload storage in `uploads/`
- Automatic temporary file deletion after analysis
- Static file serving from `results/`
- Dummy prediction logic for early frontend integration
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

Create a `.env` file from `.env.example` if you want to customize CORS origins:

```bash
copy .env.example .env
```

Default local value:

```env
CORS_ALLOWED_ORIGINS=*
```

For stricter local frontend-only access, you can use:

```env
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173
```

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
  "label": "Suspected Deepfake",
  "confidence": 88.4,
  "frames_analyzed": 16,
  "explanation": "Temporary dummy result. Replace this with trained video model prediction later.",
  "heatmap_url": null
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

## Notes For Real Model Integration

The current model logic is intentionally dummy logic so the frontend, browser extension, upload flow, and API contracts can be developed first.

Later, replace these files with real trained PyTorch model inference:

- `ml/image_inference.py`
- `ml/video_inference.py`
- `ml/audio_inference.py`

A future real implementation can also write heatmap or explainability images into `results/` and return URLs such as:

```text
http://127.0.0.1:8000/results/example-heatmap.png
```
