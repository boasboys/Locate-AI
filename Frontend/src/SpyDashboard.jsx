import React, { useEffect, useState } from "react";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import axios from "axios";
import "./SpyDashboard.css"; 

export default function SpyDashboard() {
  const [viewer, setViewer] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showLogin, setShowLogin] = useState(true);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileType, setFileType] = useState(null); // Determines if it's an image or video

  useEffect(() => {
    let cesiumViewer;

    const initializeCesium = async () => {
      Cesium.Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_TOKEN;
      cesiumViewer = new Cesium.Viewer("cesiumContainer", {
        terrainProvider: await Cesium.createWorldTerrainAsync(),
        baseLayerPicker: false,
      });

      setViewer(cesiumViewer);
    };

    initializeCesium();

    return () => {
      if (cesiumViewer) {
        cesiumViewer.destroy();
      }
    };
  }, []);

  const handleLogin = () => {
    setTimeout(() => {
      setShowLogin(false);
    }, 2000);
  };

  // 📤 **Handle File Selection (Image or Video)**
  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setSelectedFile(file);
    
    // Determine file type
    if (file.type.startsWith("image/")) {
      setFileType("image");
    } else if (file.type.startsWith("video/")) {
      setFileType("video");
    } else {
      alert("❌ Unsupported file type. Please upload an image or video.");
      setSelectedFile(null);
      setFileType(null);
    }
  };

  // 📤 **Upload Image or Video & Send to Backend**
  const handleFileUpload = async () => {
    if (!selectedFile || !fileType) {
      alert("❌ Please select a file first.");
      return;
    }
  
    setIsAnalyzing(true);
  
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("upload_preset", "Aa123456"); // Your Cloudinary preset
  
      let cloudinaryRes;
      let backendRes;
  
      if (fileType === "image") {
        // **Upload Image to Cloudinary**
        cloudinaryRes = await axios.post(
          "https://api.cloudinary.com/v1_1/dbs8wrvlv/image/upload",
          formData
        );
      } 
      else if (fileType === "video") {
        // **Upload Video to Cloudinary**
        cloudinaryRes = await axios.post(
          "https://api.cloudinary.com/v1_1/dbs8wrvlv/video/upload",
          formData
        );
      }
  
      const fileUrl = cloudinaryRes.data.secure_url;
      console.log(`✅ Cloudinary ${fileType} URL:`, fileUrl);
  
      // **Send URL to Backend**
      if (fileType === "image") {
        backendRes = await axios.post("http://localhost:5001/analyze", {
          image_url: fileUrl,
        });
      } else if (fileType === "video") {
        backendRes = await axios.post("http://localhost:5001/analyze_video", {
          video_url: fileUrl,
        });
      }
  
      handleBackendResponse(backendRes.data);
  
    } catch (error) {
      console.error("❌ Error uploading file:", error.response ? error.response.data : error.message);
      alert("Failed to analyze file.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  // 🔍 **Handle Backend Response**
  const handleBackendResponse = (data) => {
    console.log("📡 Backend Response:", data);

    if (!data) {
      alert("Invalid backend response.");
      return;
    }

    if (fileType === "image") {
      const { top_location, confidence, ai_analysis, google_lens_results, contextual_text, sources_used } = data;

      setAnalysisResult({
        type: "image",
        location: top_location || "Unknown",
        confidence: confidence || "N/A",
        ai_analysis: ai_analysis || {},
        google_lens_results: google_lens_results || [],
        contextual_text: contextual_text || [],
        sources_used: sources_used || []
      });
    } 
    
    else if (fileType === "video") {
      const { top_location, frames_analyzed, locations_found } = data;

      setAnalysisResult({
        type: "video",
        location: top_location || "Unknown",
        frames_analyzed: frames_analyzed || 0,
        locations_found: locations_found || []
      });
    }
  };

  return (
    <div className="spy-dashboard">
      {showLogin && (
        <div className="retina-scan-overlay">
          <div className="retina-scan-circle"></div>
          <p className="scan-text">SCANNING...</p>
          <button onClick={handleLogin} className="access-btn">Access Granted</button>
        </div>
      )}

      <div id="cesiumContainer" className="cesium-container"></div>

      {isAnalyzing && (
        <div className="hologram-loader">
          <div className="loading-ring"></div>
          <p>Analyzing File...</p>
        </div>
      )}

      <div className="hud-controls">
        <input 
          type="file" 
          accept="image/*, video/*" 
          onChange={handleFileSelect} 
          className="file-input"
        />
        <button className="hud-button" onClick={handleFileUpload}>Upload File</button>
      </div>

      {/* 📝 **Display Analysis Results** */}
      {analysisResult && (
        <div className="analysis-results">
          <h2>Analysis Results</h2>

          {analysisResult.type === "image" ? (
            <>
              <p><strong>Predicted Location:</strong> {analysisResult.location}</p>
              <p><strong>Confidence Score:</strong> {analysisResult.confidence}%</p>

              <h3>Google Lens Matches</h3>
              {analysisResult.google_lens_results.length > 0 ? (
                <ul>
                  {analysisResult.google_lens_results.map((item, index) => (
                    <li key={index}>
                      <a href={item.link} target="_blank" rel="noopener noreferrer">
                        {item.title ? item.title : "Google Lens Match"}
                      </a>
                      <br />
                      <img src={item.thumbnail} alt={item.title || "Google Lens Result"} width="100" />
                    </li>
                  ))}
                </ul>
              ) : <p>No matches found.</p>}

              <h3>Contextual Analysis</h3>
              {analysisResult.contextual_text.length > 0 ? (
                <ul>
                  {analysisResult.contextual_text.map((text, index) => (
                    <li key={index}>{text}</li>
                  ))}
                </ul>
              ) : <p>No additional context available.</p>}

              <h3>AI Analysis</h3>
              {analysisResult.ai_analysis && Object.keys(analysisResult.ai_analysis).length > 0 ? (
                <pre>{JSON.stringify(analysisResult.ai_analysis, null, 2)}</pre>
              ) : <p>No AI analysis available.</p>}
            </>
          ) : (
            <>
              <p><strong>Predicted Location from Video:</strong> {analysisResult.location}</p>
              <p><strong>Frames Analyzed:</strong> {analysisResult.frames_analyzed}</p>
              <h3>Locations Found in Frames</h3>
              {analysisResult.locations_found.length > 0 ? (
                <ul>
                  {analysisResult.locations_found.map((loc, index) => (
                    <li key={index}>{loc}</li>
                  ))}
                </ul>
              ) : <p>No clear location detected.</p>}
            </>
          )}
        </div>
      )}
    </div>
  );
}