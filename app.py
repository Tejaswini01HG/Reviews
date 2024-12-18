from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
from pymongo import MongoClient, ASCENDING
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import logging
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
import joblib
import os
import tensorflow as tf

# Initialize Flask app
app = Flask(__name__)

# Initialize VADER Sentiment Analyzer
analyzer = SentimentIntensityAnalyzer()

# Set up logging for error tracking
logging.basicConfig(level=logging.ERROR)

# Load the trained TensorFlow model
model = tf.keras.models.load_model("mymodel.keras")

# Load the pre-trained tokenizer used during model training
tokenizer = joblib.load("tokenizer.pkl")

# MongoDB connection (use environment variable for Render deployment)
try:
    print("Connecting to MongoDB...")
    client = MongoClient(os.environ.get("MONGODB_URI", "mongodb://localhost:27017/"))
    db = client["sentiment_analysis_db"]
    collection = db["reviews"]

    # Create indexes to improve query performance
    collection.create_index([("sentiment", ASCENDING)])
    collection.create_index([("timestamp", ASCENDING)])

    print("MongoDB connected successfully.")
except Exception as e:
    print("MongoDB connection error:", str(e))


@app.route('/')
def index():
    return render_template_string("""
 <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sentiment Analyzer</title>
    <style>
        /* Basic styles */
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: url('https://www.revuze.it/blog/wp-content/uploads/sites/2/2020/03/Amazon-Review-Analysis.png');
            background-size: cover;
            color: #fff;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            text-align: center;
        }
        .container {
            background: rgba(0, 0, 0, 0.6);
            padding: 20px;
            border-radius: 10px;
            width: 90%;
            max-width: 800px;
        }
        button {
            background-color: #007bff;
            color: #fff;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #0056b3;
        }
        .hidden {
            display: none;
        }
        textarea {
            width: 100%;
            height: 80px;
            margin-bottom: 10px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            resize: none;
            font-size: 16px;
        }
        canvas {
            height: 300px !important;
            width: 100% !important;
        }
        .chart {
            margin-top: 20px;
            background: #fff;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        }
        .microphone {
            background-color: #ff4d4d;
            margin-top: 10px;
        }
        .microphone:hover {
            background-color: #e63939;
        }
        .spinner {
            display: none;
        }
    </style>
</head>
<body>
    <div id="welcomePage" class="container">
        <h1>Welcome to the Sentiment Review Analyzer</h1>
        <p>Click the button below to analyze a review.</p>
        <button id="goToAnalyzerButton">Go to Analyzer</button>
    </div>

    <div id="analyzerPage" class="container hidden">
        <h1>Sentiment Review Analyzer</h1>
        <textarea id="textInput" placeholder="Enter your review here..."></textarea>
        <button id="analyzeButton">Analyze Sentiment</button>
        <button id="microphoneButton" class="microphone">🎤 Speak</button>
        <p>Sentiment: <span id="sentimentOutput">N/A</span></p>
        <div class="chart">
            <canvas id="sentimentChart"></canvas>
        </div>
        <button id="finishButton">Finish</button>
    </div>

    <div id="thankYouPage" class="container hidden">
        <h1>Thank You for Visiting!</h1>
        <p>We hope you enjoyed using the Sentiment Review Analyzer.</p>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", () => {
            const welcomePage = document.getElementById('welcomePage');
            const analyzerPage = document.getElementById('analyzerPage');
            const thankYouPage = document.getElementById('thankYouPage');
            const goToAnalyzerButton = document.getElementById('goToAnalyzerButton');
            const finishButton = document.getElementById('finishButton');
            const analyzeButton = document.getElementById('analyzeButton');
            const microphoneButton = document.getElementById('microphoneButton');
            const textInput = document.getElementById('textInput');
            const sentimentOutput = document.getElementById('sentimentOutput');

            let sentimentChart;

            // Show Analyzer Page
            function showAnalyzer() {
                welcomePage.classList.add('hidden');
                analyzerPage.classList.remove('hidden');
            }

            // Show Thank You Page
            function showThankYou() {
                analyzerPage.classList.add('hidden');
                thankYouPage.classList.remove('hidden');
            }

            // Sentiment calculation logic
            function calculateSentiment(text) {
                const positiveKeywords = ["good", "great", "excellent", "awesome", "amazing", "fantastic", "happy", "love"];
                const negativeKeywords = ["bad", "terrible", "awful", "horrible", "hate", "poor", "worse", "disappointing"];
                const neutralKeywords = ["okay", "average", "fine", "mediocre", "normal"];

                const words = text.toLowerCase().split(/\W+/);
                let positiveCount = 0, negativeCount = 0, neutralCount = 0;

                words.forEach(word => {
                    if (positiveKeywords.includes(word)) positiveCount++;
                    else if (negativeKeywords.includes(word)) negativeCount++;
                    else if (neutralKeywords.includes(word)) neutralCount++;
                });

                return {
                    sentiment: (positiveCount > negativeCount) ? (positiveCount > neutralCount ? "Positive" : "Neutral") : (negativeCount > neutralCount ? "Negative" : "Neutral"),
                    intensity: { positiveCount, negativeCount, neutralCount }
                };
            }

            // Update Chart
            function updateChart(data) {
                const ctx = document.getElementById("sentimentChart").getContext("2d");

                if (sentimentChart) sentimentChart.destroy();

                sentimentChart = new Chart(ctx, {
                    type: "bar",
                    data: {
                        labels: ["Positive", "Negative", "Neutral"],
                        datasets: [{
                            label: "Sentiment Intensity",
                            data: [data.positiveCount, data.negativeCount, data.neutralCount],
                            backgroundColor: ["green", "red", "gray"],
                            borderColor: ["darkgreen", "darkred", "darkgray"],
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: { beginAtZero: true }
                        }
                    }
                });
            }

            // Analyze Button Event Listener
            analyzeButton.addEventListener("click", async () => {
                const text = textInput.value.trim();
                if (!text) {
                    alert("Please enter a review to analyze!");
                    return;
                }

                // Send data to backend
                try {
                    const response = await fetch('/analyze', {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ review: text })
                    });

                    if (!response.ok) {
                        throw new Error("Failed to send data to backend.");
                    }

                    const result = await response.json();
                    const sentimentData = calculateSentiment(text);

                    sentimentOutput.textContent = result.sentiment;

                    // Update chart with data from backend
                    updateChart({
                        positiveCount: sentimentData.intensity.positiveCount,
                        negativeCount: sentimentData.intensity.negativeCount,
                        neutralCount: sentimentData.intensity.neutralCount
                    });
                } catch (error) {
                    console.error("Error occurred during the sentiment analysis:", error);
                }
            });

            // Microphone Button Event Listener (Speech-to-Text)
            microphoneButton.addEventListener("click", () => {
                if (!('webkitSpeechRecognition' in window)) {
                    alert("Your browser does not support speech recognition.");
                    return;
                }

                const recognition = new webkitSpeechRecognition();
                recognition.lang = 'en-US';
                recognition.start();

                recognition.onresult = (event) => {
                    const transcript = event.results[0][0].transcript;
                    textInput.value = transcript;
                };

                recognition.onerror = (event) => {
                    alert("Error occurred in speech recognition.");
                };
            });

            // Go to analyzer page
            goToAnalyzerButton.addEventListener("click", showAnalyzer);

            // Finish button event listener
            finishButton.addEventListener("click", showThankYou);
        });
    </script>
</body>
</html>
    """)

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    review = data.get("review", "")
    
    if review:
        # Sentiment analysis with VADER
        sentiment_score = analyzer.polarity_scores(review)
        sentiment = "Positive" if sentiment_score['compound'] > 0.1 else "Negative" if sentiment_score['compound'] < -0.1 else "Neutral"
        
        # Save the review and sentiment to MongoDB
        review_data = {
            "review": review,
            "sentiment": sentiment,
            "timestamp": datetime.utcnow()
        }
        collection.insert_one(review_data)
        
        return jsonify({"sentiment": sentiment})
    return jsonify({"error": "No review provided"}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))









