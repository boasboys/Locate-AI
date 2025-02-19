from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import openai
import os
import json
import logging
import cv2
import numpy as np
from urllib.request import urlopen
import tempfile


SCRAPINGDOG = '*****'
OPENAI = '*****'

CLOUDINARY_UPLOAD_PRESET = "Aa123456"  # Replace with your Cloudinary preset
CLOUDINARY_URL = "https://api.cloudinary.com/v1_1/dbs8wrvlv/image/upload"

# 🎯 Initialize Flask App
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)

# 🛠 Logging Setup
logging.basicConfig(level=logging.INFO)

### **🔍 1. Upload Image to Cloudinary**
def upload_to_cloudinary(image_bytes):
    """Uploads image bytes to Cloudinary and returns the image URL."""
    try:
        files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
        data = {'upload_preset': CLOUDINARY_UPLOAD_PRESET}
        
        session = requests.Session()
        response = session.post(CLOUDINARY_URL, files=files, data=data, timeout=30)
        response.raise_for_status()

        return response.json().get("secure_url")

    except requests.exceptions.RequestException as e:
        logging.error(f"🚨 Cloudinary Upload Error: {e}")
        return None

### **📍 2. Extract Key Frames from Video**
def extract_key_frames(video_path):
    """Extracts key frames every 2 seconds from a video and uploads them to Cloudinary."""
    frames = []
    cloudinary_urls = []
    
    try:
        cap = cv2.VideoCapture(video_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))  # Get frames per second
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = fps * 2  # ✅ Extract frame every 2 seconds

        logging.info(f"🎥 Processing video: {video_path}, Total frames: {total_frames}, FPS: {fps}")
        logging.info(f"⏳ Extracting a frame every {frame_interval} frames (~2 seconds)")

        count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if count % frame_interval == 0:
                # Convert frame to JPEG format
                _, buffer = cv2.imencode(".jpg", frame)
                frame_bytes = buffer.tobytes()

                # ✅ Upload frame to Cloudinary
                frame_url = upload_to_cloudinary(frame_bytes)
                if frame_url:
                    cloudinary_urls.append(frame_url)

            count += 1

        cap.release()
        logging.info(f"✅ Extracted {len(cloudinary_urls)} key frames from video")
        return cloudinary_urls  # Return URLs instead of raw frames

    except Exception as e:
        logging.error(f"🚨 Video Processing Error: {e}")
        return []
### **📖 3. Google Lens Search (via ScrapingDog)**
def get_google_lens_results(image_url):
    """Fetches first 5 search results from Google Lens via ScrapingDog API."""
    if not SCRAPINGDOG_API_KEY:
        logging.error("🚨 Missing ScrapingDog API key.")
        return []

    try:
        lens_api_url = f"https://api.scrapingdog.com/google_lens?api_key={SCRAPINGDOG_API_KEY}&url={image_url}"
        response = requests.get(lens_api_url, timeout=20)
        response.raise_for_status()
        lens_results = response.json().get("lens_results", [])[:5]

        logging.info(f"🔍 Google Lens returned {len(lens_results)} results")
        return lens_results

    except requests.exceptions.RequestException as e:
        logging.error(f"🚨 Google Lens API Error: {e}")
        return []

### **📍 4. AI-Based Image Analysis**
def analyze_image_with_ai(image_url, google_lens_results):
    """Analyzes an image using OpenAI's Vision API."""
    if not OPENAI_API_KEY:
        logging.error("🚨 OpenAI API Key is missing.")
        return None

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    google_lens_summary = "\n".join(
        [f"- {result['title']} (Link: {result['link']})" for result in google_lens_results]
    )

    system_prompt = (
        "You are an AI trained to analyze images and determine their location.\n"
        "Rules:\n"
        "1️⃣ **Use Google Lens Results if available** - Verify if they match the image.\n"
        "2️⃣ **Analyze Visual Elements** - Look at buildings, signs, landmarks.\n"
        "3️⃣ **No Assumptions** - If the location is unclear, say 'Unknown'.\n"
        "Output format:\n"
        "{\n"
        '  "top_location_guesses": ["Most Likely Location", "Alternative Guess 1", "Alternative Guess 2"],\n'
        '  "confidence_score": "Final confidence score (0-100%)"\n'
        "}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Analyze this image. Google Lens Suggestions:\n{google_lens_summary}"},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}
            ],
            max_tokens=500,
        )

        ai_result = json.loads(response.choices[0].message.content.strip())
        logging.info(f"🤖 AI Analysis Result: {json.dumps(ai_result, indent=2)}")
        return ai_result

    except Exception as e:
        logging.error(f"🚨 OpenAI Analysis Error: {e}")
        return None

### **🚀 5. Flask API - /analyze_video**
@app.route("/analyze_video", methods=["POST"])
def analyze_video():
    """API Endpoint to analyze a video from Cloudinary and determine its most likely location."""
    try:
        data = request.get_json()
        video_url = data.get("video_url")

        if not video_url or not video_url.startswith("http"):
            return jsonify({"error": "Invalid or missing video URL"}), 400

        logging.info(f"📸 Processing video: {video_url}")

        # ✅ Use a safer download method
        temp_path = "/tmp/temp_video.mp4"
        response = requests.get(video_url, stream=True, timeout=60)

        if response.status_code != 200:
            logging.error(f"🚨 Failed to download video from Cloudinary: HTTP {response.status_code}")
            return jsonify({"error": "Failed to download video"}), 500

        with open(temp_path, "wb") as video_file:
            for chunk in response.iter_content(chunk_size=8192):
                video_file.write(chunk)

        # ✅ Extract key frames (now uploaded to Cloudinary)
        frame_urls = extract_key_frames(temp_path)

        if not frame_urls:
            return jsonify({"error": "No frames extracted from video"}), 500

        all_results = []

        for frame_url in frame_urls[:5]:
            google_lens_results = get_google_lens_results(frame_url)
            ai_results = analyze_image_with_ai(frame_url, google_lens_results)
            if ai_results:
                all_results.append(ai_results["top_location_guesses"][0])

        final_location = max(set(all_results), key=all_results.count) if all_results else "Unknown"

        return jsonify({
            "status": "success",
            "top_location": final_location,
            "frames_analyzed": len(frame_urls),
            "locations_found": all_results
        })

    except Exception as e:
        logging.error(f"🚨 Backend Error: {e}")
        return jsonify({"error": str(e), "status": "failed"}), 500
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)