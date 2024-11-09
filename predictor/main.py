import requests
import numpy as np
from collections import deque
from sklearn.preprocessing import MinMaxScaler
import time


class EmotionMonitoringSystem:
    def __init__(
        self,
        endpoint="http://192.168.156.142/get_all_data",
        max_points=100,
        smoothing_window=5,
        emotion_window=30,
        alpha=0.3,
    ):
        # Data processing parameters
        self.endpoint = endpoint
        self.smoothing_window = smoothing_window
        self.alpha = alpha
        self.max_points = max_points

        # Initialize raw data storage
        self.mag_x = deque(maxlen=max_points)
        self.mag_y = deque(maxlen=max_points)
        self.mag_z = deque(maxlen=max_points)
        self.heading = deque(maxlen=max_points)
        self.scl = deque(maxlen=max_points)
        self.scr = deque(maxlen=max_points)
        self.heart_bpm = deque(maxlen=max_points)
        self.resp_bpm = deque(maxlen=max_points)

        # Initialize processed data buffers for emotion prediction
        self.processed_heart_rate = deque(maxlen=emotion_window)
        self.processed_resp_rate = deque(maxlen=emotion_window)
        self.processed_scl = deque(maxlen=emotion_window)
        self.processed_scr = deque(maxlen=emotion_window)

        # Initialize emotion prediction parameters
        self.emotion_window = emotion_window
        self.scalers = {
            "heart_rate": MinMaxScaler(),
            "resp_rate": MinMaxScaler(),
            "scl": MinMaxScaler(),
            "scr": MinMaxScaler(),
        }

        # Define emotion characteristics
        self.emotion_patterns = {
            "amusing": {
                "heart_rate": "medium_high",
                "heart_rate_variability": "high",
                "resp_rate": "medium_high",
                "scl": "medium_high",
                "scr": "high",
            },
            "boring": {
                "heart_rate": "low",
                "heart_rate_variability": "low",
                "resp_rate": "low",
                "scl": "low",
                "scr": "low",
            },
            "relaxed": {
                "heart_rate": "low_medium",
                "heart_rate_variability": "medium",
                "resp_rate": "low_medium",
                "scl": "low_medium",
                "scr": "low_medium",
            },
            "scary": {
                "heart_rate": "high",
                "heart_rate_variability": "high",
                "resp_rate": "high",
                "scl": "high",
                "scr": "very_high",
            },
        }

    def remove_outliers(self, data, threshold=3):
        """Remove outliers using z-score method"""
        if len(data) < 4:
            return data

        data_array = np.array(data)
        z_scores = np.abs((data_array - np.mean(data_array)) / np.std(data_array))
        return [
            d if z < threshold else np.mean(data_array)
            for d, z in zip(data_array, z_scores)
        ]

    def smooth_data_sma(self, data):
        """Apply Simple Moving Average smoothing"""
        if len(data) < self.smoothing_window:
            return list(data)

        smoothed = []
        data_array = np.array(data)

        for i in range(len(data_array)):
            start_idx = max(0, i - self.smoothing_window + 1)
            window = data_array[start_idx : (i + 1)]
            smoothed.append(np.mean(window))

        return smoothed

    def smooth_data_ema(self, data):
        """Apply Exponential Moving Average smoothing"""
        if len(data) < 2:
            return list(data)

        smoothed = [data[0]]
        for n in range(1, len(data)):
            smoothed.append(self.alpha * data[n] + (1 - self.alpha) * smoothed[n - 1])

        return smoothed

    def process_data(self, data):
        """Remove outliers and apply smoothing"""
        clean_data = self.remove_outliers(data)
        smoothed_data = self.smooth_data_ema(clean_data)
        final_smooth = self.smooth_data_sma(smoothed_data)
        return final_smooth

    def fetch_data(self):
        """Fetch data from the endpoint"""
        try:
            response = requests.get(self.endpoint, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return None

    def calculate_features(self):
        """Calculate statistical features from the processed physiological signals"""
        if len(self.processed_heart_rate) < 2:
            return None

        features = {
            "heart_rate_mean": np.mean(self.processed_heart_rate),
            "heart_rate_std": np.std(self.processed_heart_rate),
            "resp_rate_mean": np.mean(self.processed_resp_rate),
            "resp_rate_std": np.std(self.processed_resp_rate),
            "scl_mean": np.mean(self.processed_scl),
            "scl_std": np.std(self.processed_scl),
            "scr_mean": np.mean(self.processed_scr),
            "scr_slope": np.gradient(list(self.processed_scr)).mean(),
        }

        # Normalize features
        if len(self.processed_heart_rate) >= self.emotion_window:
            for feature_name, scaler in self.scalers.items():
                if feature_name in ["heart_rate", "resp_rate", "scl", "scr"]:
                    buffer_mean = features[f"{feature_name}_mean"]
                    features[f"{feature_name}_mean"] = float(
                        scaler.fit_transform([[buffer_mean]])[0][0]
                    )

        return features

    def get_level_score(self, value, category):
        """Convert numerical values to categorical levels"""
        thresholds = {
            "very_low": 0.2,
            "low": 0.35,
            "low_medium": 0.45,
            "medium": 0.55,
            "medium_high": 0.65,
            "high": 0.8,
            "very_high": 0.9,
        }

        for level, threshold in thresholds.items():
            if value <= threshold:
                return level
        return "very_high"

    def calculate_emotion_scores(self, features):
        """Calculate scores for each emotion based on physiological features"""
        emotion_scores = {emotion: 0.0 for emotion in self.emotion_patterns.keys()}

        for emotion, pattern in self.emotion_patterns.items():
            score = 0
            weights = {
                "heart_rate": 0.3,
                "heart_rate_variability": 0.2,
                "resp_rate": 0.2,
                "scl": 0.15,
                "scr": 0.15,
            }

            # Calculate scores for each physiological feature
            hr_level = self.get_level_score(features["heart_rate_mean"], "heart_rate")
            if hr_level == pattern["heart_rate"]:
                score += weights["heart_rate"]

            hrv_level = self.get_level_score(features["heart_rate_std"], "hrv")
            if hrv_level == pattern["heart_rate_variability"]:
                score += weights["heart_rate_variability"]

            resp_level = self.get_level_score(features["resp_rate_mean"], "resp_rate")
            if resp_level == pattern["resp_rate"]:
                score += weights["resp_rate"]

            scl_level = self.get_level_score(features["scl_mean"], "scl")
            if scl_level == pattern["scl"]:
                score += weights["scl"]

            scr_level = self.get_level_score(features["scr_mean"], "scr")
            if scr_level == pattern["scr"]:
                score += weights["scr"]

            emotion_scores[emotion] = score

        return emotion_scores

    def update_and_predict(self):
        """Fetch new data, process it, and predict emotion"""
        # Fetch new data
        data = self.fetch_data()
        if not data:
            return None

        # Update raw data buffers
        for key, buffer in {
            "mag_x": self.mag_x,
            "mag_y": self.mag_y,
            "mag_z": self.mag_z,
            "heading": self.heading,
            "scl": self.scl,
            "scr": self.scr,
            "heart_bpm": self.heart_bpm,
            "resp_bpm": self.resp_bpm,
        }.items():
            if key in data:
                buffer.append(data[key])

        # Process data and update processed buffers
        if len(self.heart_bpm) > self.smoothing_window:
            processed_heart = self.process_data(list(self.heart_bpm))[-1]
            processed_resp = self.process_data(list(self.resp_bpm))[-1]
            processed_scl = self.process_data(list(self.scl))[-1]
            processed_scr = self.process_data(list(self.scr))[-1]

            self.processed_heart_rate.append(processed_heart)
            self.processed_resp_rate.append(processed_resp)
            self.processed_scl.append(processed_scl)
            self.processed_scr.append(processed_scr)

        # Calculate features and predict emotion
        features = self.calculate_features()
        if features is None:
            return None

        emotion_scores = self.calculate_emotion_scores(features)
        most_likely_emotion = max(emotion_scores.items(), key=lambda x: x[1])

        return {
            "predicted_emotion": most_likely_emotion[0],
            "confidence": most_likely_emotion[1],
            "all_scores": emotion_scores,
            "features": features,
            "raw_data": data,
        }


if __name__ == "__main__":
    # Initialize the system
    monitoring_system = EmotionMonitoringSystem(
        emotion_window=10,  # Smaller window for demo purposes
        max_points=20,
        smoothing_window=5,
    )

    print("Starting emotion monitoring...")
    print("Press Ctrl+C to stop")
    print("-" * 50)

    try:
        while True:
            result = monitoring_system.update_and_predict()
            
            if result:
                print(f"\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Predicted Emotion: {result['predicted_emotion']}")
                print(f"Confidence: {result['confidence']:.2f}")
                print("\nEmotion Scores:")
                for emotion, score in result["all_scores"].items():
                    print(f"{emotion}: {score:.2f}")
                print("-" * 50)
            
            time.sleep(1)  # Wait 1 second between updates

    except KeyboardInterrupt:
        print("\nStopping emotion monitoring...")