import logging
import os
import subprocess
import threading
import time

os.environ["GST_DEBUG"] = "0"

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

import cv2
import gi
from dotenv import load_dotenv

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
from gi.repository import GLib, Gst

load_dotenv(dotenv_path="../.env")


class Recorder:
    def __init__(self, rtsp_url, output_file):
        Gst.init(None)
        self.rtsp_url = rtsp_url
        self.output_file = output_file
        self.record_pipeline = Gst.parse_launch(
            f"rtspsrc location={self.rtsp_url} latency=200 ! "
            "parsebin ! "
            "mp4mux name=muxer ! "
            f"filesink location={self.output_file} sync=false"
        )
        self.muxer = self.record_pipeline.get_by_name("muxer")
        bus = self.record_pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self.on_eos)
        self.main_loop = GLib.MainLoop()

    def on_eos(self, bus, msg):
        logger.info("EOS reached")
        self.analyze_video_file(self.output_file)
        self.record_pipeline.set_state(Gst.State.NULL)
        self.main_loop.quit()

    def save_pipeline_graph(self, pipeline, png_file="pipeline.png"):
        """Save pipeline diagram to PNG file"""
        dot_file = png_file.replace(".png", ".dot")
        with open(dot_file, "w") as f:
            f.write(Gst.debug_bin_to_dot_data(pipeline, Gst.DebugGraphDetails.ALL))
        subprocess.run(["dot", "-Tpng", dot_file, "-o", png_file])
        logger.info(f"Saved pipeline graph as {png_file}")

    def analyze_video_file(self, video_path):
        """Analyze video statistics using OpenCV"""
        cap = cv2.VideoCapture(video_path)

        fps = cap.get(cv2.CAP_PROP_FPS)

        total_frames = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            total_frames += 1

        duration = total_frames / fps if fps > 0 else 0

        cap.release()

        logger.info("Video Statistics:")
        logger.info(f"Total Frames: {total_frames}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"FPS: {fps:.2f}")

    def check_pad(self):
        while True:
            pad = self.muxer.get_static_pad("video_0")

            if pad:
                logger.info("[INFO] Found muxer video_0 pad.")
                break
            else:
                logger.info("[INFO] muxer video_0 pad not yet available.")

            time.sleep(5)

    def stop_recording(self):
        self.save_pipeline_graph(self.record_pipeline, "record_pipeline.png")
        self.record_pipeline.send_event(Gst.Event.new_eos())
        logger.info("Recording stopped.")
        return False

    def play(self):
        self.record_pipeline.set_state(Gst.State.PLAYING)
        check_pad_thread = threading.Thread(target=self.check_pad, daemon=True)
        check_pad_thread.start()
        logger.info("Recording started...")
        GLib.timeout_add_seconds(20, self.stop_recording)
        try:
            self.main_loop.run()
        except KeyboardInterrupt:
            pass

        self.record_pipeline.set_state(Gst.State.NULL)


def main():
    rtsp_url = os.getenv("RTSP_1")
    output_file = os.getenv("OUTPUT_FILE", "buffered_output.mp4")
    recorder = Recorder(rtsp_url, output_file)
    recorder.play()


if __name__ == "__main__":
    main()
