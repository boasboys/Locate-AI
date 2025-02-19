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


SCRAPINGDOG = '********'
OPENAI = '*******'
# 🎯 Initialize Flask App
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)

# 🛠 Logging Setup
logging.basicConfig(level=logging.INFO)

### **🔍 1. Download and Compare Images**
def download_image(image_url):
    """Download an image and convert it to OpenCV format."""
    try:
        logging.info(f"📥 Downloading image: {image_url}")
        resp = urlopen(image_url, timeout=15)
        image_array = np.asarray(bytearray(resp.read()), dtype=np.uint8)
        return cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    except Exception as e:
        logging.error(f"🚨 Failed to download image: {e}")
        return None

### **📖 2. Google Lens Search (via ScrapingDog)**
def get_google_lens_results(image_url, retries=3):
    """Fetch first 5 search results from Google Lens via ScrapingDog API with retries."""
    if not SCRAPINGDOG_API_KEY:
        logging.error("🚨 Missing ScrapingDog API key.")
        return []

    lens_api_url = f"https://api.scrapingdog.com/google_lens?api_key={SCRAPINGDOG_API_KEY}&url={image_url}"

    for attempt in range(retries):
        try:
            response = requests.get(lens_api_url, timeout=20)
            response.raise_for_status()
            lens_results = response.json().get("lens_results", [])[:5]

            # ✅ Debugging: Print the collected Google Lens results
            logging.info(f"🔍 Google Lens returned {len(lens_results)} results:")
            for i, result in enumerate(lens_results):
                logging.info(f"  📌 [{i+1}] Title: {result.get('title', 'No Title')}, Link: {result.get('link', 'No Link')}")
            
            return lens_results

        except requests.exceptions.RequestException as e:
            logging.warning(f"⚠️ Attempt {attempt+1}: Google Lens API Timeout. Retrying...")

    logging.error("🚨 Google Lens API failed after retries.")
    return []

### **📍 3. AI-Based Image Analysis with Google Lens Validation**
def analyze_image_with_ai(image_url, text_summaries, google_lens_results):
    """Analyze an image using AI, incorporating contextual text and Google Lens results."""
    if not OPENAI_API_KEY:
        logging.error("🚨 OpenAI API Key is missing.")
        return None

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    combined_text = " ".join(text_summaries[:3]) if text_summaries else "No text found."

    # **Force AI to consider Google Lens results**
    google_lens_summary = "\n".join(
        [f"- {result['title']} (Link: {result['link']})" for result in google_lens_results]
    )

    final_prompt = (
        f"Analyze this image and determine its most likely location.\n"
        f"📸 **Google Lens Suggestions** (MUST BE CHECKED):\n{google_lens_summary}\n\n"
        f"📖 **Additional Context (if any)**: {combined_text}"
    )

    system_prompt = (
        "You are an AI trained to geolocate images accurately.\n"
        "🔍 **Your Task:** Determine the most likely location of the image **only using real evidence**.\n"
        "🛠 **Rules to Follow:**\n"
        "1️⃣ **Scene Analysis**: Identify visual clues (landmarks, language, architecture, climate).\n"
        "2️⃣ **Google Lens Data (VERY IMPORTANT)**: If Google Lens already suggests a location, **you MUST check if it is correct**.\n"
        "3️⃣ **Text Extraction**: If there is text in the image, use it to confirm a location.\n"
        "4️⃣ **No Assumptions**: If there is no clear match, say so. Do NOT randomly pick a famous city.\n"
        "\n"
        "📌 **Final Output Format:**\n"
        "{\n"
        '  "top_location_guesses": ["Most Likely Location", "Alternative Guess 1", "Alternative Guess 2"],\n'
        '  "confidence_score": "Final confidence score (0-100%)",\n'
        '  "reasoning": "Why this location was chosen, based on visual + Google Lens data"\n'
        "}\n"
        "❌ Do NOT output extra text or explanations."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": final_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}
            ],
            max_tokens=500,
        )

        raw_response = response.choices[0].message.content.strip()

        # ✅ Validate OpenAI Response Before Parsing
        if not raw_response.startswith("{") or not raw_response.endswith("}"):
            logging.error(f"🚨 OpenAI response is not in expected JSON format:\n{raw_response}")
            return None

        ai_result = json.loads(raw_response)
        logging.info(f"🤖 AI Analysis Result: {json.dumps(ai_result, indent=2)}")
        return ai_result

    except (json.JSONDecodeError, Exception) as e:
        logging.error(f"🚨 OpenAI JSON Parsing Error: {e}\nRaw Response: {raw_response}")
        return None

### **🚀 4. Flask API - /analyze**
@app.route("/analyze", methods=["POST"])
def analyze_image():
    """API Endpoint to analyze an image for location and contextual data."""
    try:
        data = request.get_json()
        image_url = data.get("image_url")

        if not image_url:
            return jsonify({"error": "Missing image URL"}), 400

        logging.info(f"📸 Processing image: {image_url}")

        # Step 1: Fetch Google Lens results
        google_lens_results = get_google_lens_results(image_url)

        # Step 2: AI Scene Analysis (with Google Lens validation)
        text_summaries = ["Summary of the webpage content goes here..."]  # Placeholder for now
        ai_results = analyze_image_with_ai(image_url, text_summaries, google_lens_results)

        return jsonify({
            "status": "success",
            "top_location": ai_results["top_location_guesses"][0] if ai_results else "Unknown",
            "confidence": ai_results["confidence_score"] if ai_results else 50,
            "ai_analysis": ai_results,
            "google_lens_results": google_lens_results,
            "contextual_text": text_summaries
        })

    except Exception as e:
        logging.error(f"🚨 Backend Error: {e}")
        return jsonify({"error": str(e), "status": "failed"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)