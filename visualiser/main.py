import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
import requests
import warnings

warnings.filterwarnings("ignore")


class SensorDataVisualizer:
    def __init__(self, endpoint="http://192.168.156.142/get_all_data", max_points=100):
        # Store endpoint
        self.endpoint = endpoint

        # Initialize data storage
        self.max_points = max_points

        # Magnetic data
        self.mag_x = deque(maxlen=max_points)
        self.mag_y = deque(maxlen=max_points)
        self.mag_z = deque(maxlen=max_points)
        self.heading = deque(maxlen=max_points)

        # GSR data
        self.scl = deque(maxlen=max_points)
        self.scr = deque(maxlen=max_points)
        self.heart_bpm = deque(maxlen=max_points)
        self.resp_bpm = deque(maxlen=max_points)

        # Setup plots
        plt.style.use("ggplot")
        self.fig, self.axs = plt.subplots(2, 2, figsize=(15, 10))
        self.setup_plots()

    def setup_plots(self):
        """Initialize the four plots"""
        self.fig.suptitle("Real-time Sensor Data Visualization", fontsize=16)

        # Magnetic field components
        self.mag_lines = []
        self.axs[0, 0].set_title("Magnetic Field Components")
        self.axs[0, 0].set_ylabel("μT")
        self.mag_lines.extend([
            self.axs[0, 0].plot([], [], label="X", linewidth=2)[0],
            self.axs[0, 0].plot([], [], label="Y", linewidth=2)[0],
            self.axs[0, 0].plot([], [], label="Z", linewidth=2)[0],
        ])
        self.axs[0, 0].grid(True)
        self.axs[0, 0].legend()

        # Heading
        self.heading_line = self.axs[0, 1].plot([], [], label="Heading", linewidth=2)[0]
        self.axs[0, 1].set_title("Magnetic Heading")
        self.axs[0, 1].set_ylabel("Degrees")
        self.axs[0, 1].grid(True)
        self.axs[0, 1].legend()

        # Heart and Respiration BPM
        self.vital_lines = []
        self.axs[1, 0].set_title("Vital Signs")
        self.axs[1, 0].set_ylabel("BPM")
        self.vital_lines.extend([
            self.axs[1, 0].plot([], [], label="Heart Rate", linewidth=2)[0],
            self.axs[1, 0].plot([], [], label="Respiration", linewidth=2)[0],
        ])
        self.axs[1, 0].grid(True)
        self.axs[1, 0].legend()

        # Skin Conductance
        self.gsr_lines = []
        self.axs[1, 1].set_title("GSR Measurements")
        self.gsr_lines.extend([
            self.axs[1, 1].plot([], [], label="SCL", linewidth=2)[0],
            self.axs[1, 1].plot([], [], label="SCR", linewidth=2)[0],
        ])
        self.axs[1, 1].grid(True)
        self.axs[1, 1].legend()

        plt.tight_layout()

    def remove_outliers(self, data, threshold=3):
        """Remove outliers using z-score method"""
        if len(data) < 4:  # Need some minimum data for meaningful statistics
            return data

        data_array = np.array(data)
        z_scores = np.abs((data_array - np.mean(data_array)) / np.std(data_array))
        return [
            d if z < threshold else np.mean(data_array)
            for d, z in zip(data_array, z_scores)
        ]

    def fetch_data(self):
        """Fetch data from the endpoint"""
        try:
            response = requests.get(self.endpoint, timeout=5)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return None

    def update_data(self, frame):
        """Update data from API and refresh plots"""
        try:
            # Fetch data from endpoint
            data = self.fetch_data()
            if data is None:
                return (
                    self.mag_lines
                    + [self.heading_line]
                    + self.vital_lines
                    + self.gsr_lines
                )

            # Update data queues
            self.mag_x.append(data["mag"]["data"]["X"])
            self.mag_y.append(data["mag"]["data"]["Y"])
            self.mag_z.append(data["mag"]["data"]["Z"])
            self.heading.append(data["mag"]["data"]["Heading (degrees)"])
            self.scl.append(data["gsr"]["data"]["SkinConductance"]["SCL"])
            self.scr.append(data["gsr"]["data"]["SkinConductance"]["SCR"])
            self.heart_bpm.append(data["gsr"]["data"]["HeartBeat"]["BPM"])
            self.resp_bpm.append(data["gsr"]["data"]["Respiration"]["BPM"])

            # Remove outliers and update plots
            x = range(len(self.mag_x))

            # Update magnetic field plot
            for line, data in zip(self.mag_lines, [self.mag_x, self.mag_y, self.mag_z]):
                clean_data = self.remove_outliers(data)
                line.set_data(x, clean_data)
                self.axs[0, 0].relim()
                self.axs[0, 0].autoscale_view()

            # Update heading plot
            clean_heading = self.remove_outliers(self.heading)
            self.heading_line.set_data(x, clean_heading)
            self.axs[0, 1].relim()
            self.axs[0, 1].autoscale_view()

            # Update vital signs plot
            for line, data in zip(self.vital_lines, [self.heart_bpm, self.resp_bpm]):
                clean_data = self.remove_outliers(data)
                line.set_data(x, clean_data)
                self.axs[1, 0].relim()
                self.axs[1, 0].autoscale_view()

            # Update GSR plot
            for line, data in zip(self.gsr_lines, [self.scl, self.scr]):
                clean_data = self.remove_outliers(data)
                line.set_data(x, clean_data)
                self.axs[1, 1].relim()
                self.axs[1, 1].autoscale_view()

        except Exception as e:
            print(f"Error updating plots: {e}")

        return self.mag_lines + [self.heading_line] + self.vital_lines + self.gsr_lines

    def start(self, interval=1000):
        """Start the animation"""
        self.anim = FuncAnimation(
            self.fig,
            self.update_data,
            interval=interval,  # Update every 1000ms (1 second)
            blit=True,
        )
        plt.show()


# Create and start the visualizer
if __name__ == "__main__":
    visualizer = SensorDataVisualizer()
    visualizer.start()

