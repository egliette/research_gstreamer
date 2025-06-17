# Standard library
import os
import subprocess
import time
from collections import deque
import logging

os.environ["GST_DEBUG"] = "2"

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

import cv2
from dotenv import load_dotenv
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
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
        self.record_pipeline = Gst.parse_launch(
            f'rtspsrc location={self.rtsp_url} latency=200 ! '
            'parsebin ! '
            'appsink name=sink emit-signals=true sync=false'
        )
                
        # Connect to appsink
        self.appsink = self.record_pipeline.get_by_name('sink')
        self.appsink.connect("new-sample", self.on_new_sample, None)
        
    def save_pipeline_graph(self, pipeline, png_file="pipeline.png"):
        """Save pipeline diagram to PNG file"""
        dot_file = png_file.replace(".png", ".dot")
        with open(dot_file, "w") as f:
            f.write(Gst.debug_bin_to_dot_data(pipeline, Gst.DebugGraphDetails.ALL))
        subprocess.run(["dot", "-Tpng", dot_file, "-o", png_file])
        logger.info(f"Saved pipeline graph as {png_file}")
    
    def on_new_sample(self, sink, data):
        """Callback to handle each new sample"""
        sample = sink.emit("pull-sample")
        buf = sample.get_buffer()
        self.buffer_queue.append(buf)
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
        sink_pad = self.appsink.get_static_pad("sink")
        caps = sink_pad.get_current_caps()
        save_pipeline = Gst.parse_launch(
            f'appsrc name=src format=time caps="{caps.to_string()}" ! '
            'parsebin ! '
            'mp4mux  ! '
            f'filesink location={output_file} sync=false'
        )
        save_pipeline.set_state(Gst.State.PLAYING)

        # Get appsrc element
        appsrc = save_pipeline.get_by_name('src')

        # Push frames to appsrc
        logger.info("Start adding buffer to video")
        first_pts = self.buffer_queue[0].pts
        fps = 0
        if len(self.buffer_queue) >= 2:
            total_frames = len(self.buffer_queue)
            last_pts = self.buffer_queue[-1].pts

            duration_sec = (last_pts - first_pts) / Gst.SECOND
            fps = int(total_frames / duration_sec) if duration_sec > 0 else 0
        
        for i, buf in enumerate(self.buffer_queue):
            if fps:
                buf.pts = int(i * Gst.SECOND / fps)
            else:
                buf.pts = buf.pts - first_pts
            appsrc.emit("push-buffer", buf)
        
        # Save saving pipeline diagram
        self.save_pipeline_graph(save_pipeline, "saving_pipeline.png")

        # Signal EOS and wait for the muxer to finish
        appsrc.emit("end-of-stream")
        bus = save_pipeline.get_bus()
        bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE,
            Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        
        # Cleanup
        save_pipeline.set_state(Gst.State.NULL)
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
        self.record_pipeline.set_state(Gst.State.PLAYING)

        time.sleep(30)
        
        # Save recording pipeline diagram
        self.record_pipeline.set_state(Gst.State.PAUSED)
        self.save_pipeline_graph(self.record_pipeline, "recording_pipeline.png")  
        self.save_buffered_video("buffered_output.mp4")
     
        try:
            self.main_loop = GLib.MainLoop()
            self.main_loop.run()
        except KeyboardInterrupt:
            pass
        
        self.record_pipeline.set_state(Gst.State.NULL)


def main():
    recorder = SmartRecorder()
    recorder.play()
    

if __name__ == "__main__":
    main()
