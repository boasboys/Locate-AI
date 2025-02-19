import express from "express";
import mongoose from "mongoose";
import cors from "cors";
import dotenv from "dotenv";

dotenv.config();
const app = express();
const PORT = 5000;

mongoose.connect("mongodb://127.0.0.1:27017/imageDB", {
  useNewUrlParser: true,
  useUnifiedTopology: true,
});

const ImageSchema = new mongoose.Schema({
  url: String,
  location: {
    latitude: Number,
    longitude: Number
  },
  uploadedAt: { type: Date, default: Date.now },
});

const Image = mongoose.model("Image", ImageSchema);

app.use(cors());
app.use(express.json());

// Handle image upload
app.post("/upload", async (req, res) => {
  const { url, location } = req.body;

  if (!url) {
    return res.status(400).json({ error: "Image URL is required" });
  }

  if (!location || !location.latitude || !location.longitude) {
    return res.status(400).json({ error: "Location data is required" });
  }

  try {
    const newImage = new Image({
      url,
      location: {
        latitude: location.latitude,
        longitude: location.longitude
      }
    });
    await newImage.save();
    res.status(201).json({ message: "Image uploaded successfully", image: newImage });
  } catch (err) {
    console.error("Error saving image:", err);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

// Fetch all images
app.get("/images", async (req, res) => {
  try {
    const images = await Image.find({});
    console.log("Found images:", images.length);

    if (!images || images.length === 0) {
      return res.status(404).json({
        error: "No images found in the database"
      });
    }

    res.json(images);
  } catch (err) {
    console.error("Error fetching images:", err);
    res.status(500).json({
      error: "Failed to fetch images from database"
    });
  }
});

// Endpoint to get user's IP address (for location display)
app.get("/location", (req, res) => {
  const ip = req.headers["x-forwarded-for"] || req.connection.remoteAddress;
  res.json({ ip });
});

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});