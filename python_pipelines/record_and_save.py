import os

os.environ["GST_DEBUG"] = "0"
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)
import subprocess
import sys
import time
from collections import deque

import cv2
import gi

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
from dotenv import load_dotenv
from gi.repository import GLib, Gst

load_dotenv(dotenv_path="../.env")

class SmartRecorder:
    def __init__(self):
        Gst.init(None)
        
        # Configuration
        self.rtsp_url = os.getenv("RTSP_1")
        self.buffer_duration = 1 * 60 * Gst.SECOND  # 5 minutes in nanoseconds
        self.buffer_queue = deque(maxlen=1000)
        
        # Initialize recording pipeline
        self.pipeline = Gst.parse_launch(
            f'rtspsrc location={self.rtsp_url} latency=200 ! '
            'rtpmp4vdepay ! '
            'appsink name=sink emit-signals=true sync=false'
        )
        
        # Save recording pipeline diagram
        self.save_pipeline_graph("recording_pipeline.png")
        
        # Connect to appsink
        self.appsink = self.pipeline.get_by_name('sink')
        self.appsink.connect("new-sample", self.on_new_sample, None)
        
    def save_pipeline_graph(self, png_file="pipeline.png"):
        """Save pipeline diagram to PNG file"""
        dot_file = png_file.replace(".png", ".dot")
        with open(dot_file, "w") as f:
            f.write(Gst.debug_bin_to_dot_data(self.pipeline, Gst.DebugGraphDetails.ALL))
        subprocess.run(["dot", "-Tpng", dot_file, "-o", png_file])
        logger.info(f"Saved pipeline graph as {png_file}")
    
    def on_new_sample(self, sink, data):
        """Callback to handle each new sample"""
        sample = sink.emit("pull-sample")
        buf = sample.get_buffer()
        result, mapinfo = buf.map(Gst.MapFlags.READ)
        if result:
            data = mapinfo.data
            pts = buf.pts
            self.buffer_queue.append((data, pts))
            # Drop frames older than buffer duration
            while self.buffer_queue and (pts - self.buffer_queue[0][1] > self.buffer_duration):
                self.buffer_queue.popleft()
            buf.unmap(mapinfo)
        return Gst.FlowReturn.OK
    
    def analyze_video_file(self, video_path):
        """Analyze video statistics using OpenCV"""
        cap = cv2.VideoCapture(video_path)
        
        # Get fps from video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        # Count frames by reading through the video
        total_frames = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            total_frames += 1
        
        # Calculate duration
        duration = total_frames / fps if fps > 0 else 0
        
        # Release the video capture
        cap.release()
        
        return total_frames, duration, fps
    
    def save_buffered_video(self, output_file):
        """Save buffered frames to MP4 file"""
        logger.info("Start saving the buffered video")
        # Create and start pipeline
        save_pipe = Gst.parse_launch(
            'appsrc name=src format=time ! '
            'mpeg4videoparse ! '
            'mp4mux ! '
            f'filesink location={output_file} sync=false'
        )
        
        # Save saving pipeline diagram
        self.pipeline = save_pipe
        self.save_pipeline_graph("saving_pipeline.png")
        
        save_pipe.set_state(Gst.State.PLAYING)
        
        # Get appsrc element
        appsrc = save_pipe.get_by_name('src')
        
        # Push frames to appsrc
        for data, pts in list(self.buffer_queue):
            buf = Gst.Buffer.new_allocate(None, len(data), None)
            buf.fill(0, data)
            buf.pts = pts
            appsrc.emit("push-buffer", buf)
        
        # Signal EOS and wait for the muxer to finish
        appsrc.emit("end-of-stream")
        bus = save_pipe.get_bus()
        bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE,
            Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        
        # Cleanup
        save_pipe.set_state(Gst.State.NULL)
        logger.info(f"Saved {len(self.buffer_queue)} buffers to {output_file}")
        
        # Analyze the saved video
        logger.info("Analyzing saved video...")
        total_frames, duration, fps = self.analyze_video_file(output_file)
        logger.info("Video Statistics:")
        logger.info(f"Total Frames: {total_frames}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"FPS: {fps:.2f}")
    
    def play(self):
        """Start the recording pipeline"""
        self.pipeline.set_state(Gst.State.PLAYING)

        time.sleep(30)

        self.save_buffered_video("buffered_output.mp4")
     
        try:
            self.main_loop = GLib.MainLoop()
            self.main_loop.run()
        except KeyboardInterrupt:
            pass
        
        self.pipeline.set_state(Gst.State.NULL)


def main():
    recorder = SmartRecorder()
    recorder.play()
    

if __name__ == "__main__":
    main()
