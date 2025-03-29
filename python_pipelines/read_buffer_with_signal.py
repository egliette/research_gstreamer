import os

os.environ["GST_DEBUG"] = "2"
import logging

logging.basicConfig(
    level=logging.DEBUG, format="[%(name)s] [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)
import subprocess
import sys

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
import cv2
import numpy as np
from dotenv import load_dotenv
from gi.repository import GLib, Gst

load_dotenv(dotenv_path="../.env")

from helper.profiler import FPSCounter


class Player:
    def __init__(self, uri):
        self.main_loop = GLib.MainLoop()

        self.pipeline = Gst.Pipeline.new("multisource_player")

        self.source = Gst.ElementFactory.make("uridecodebin", "source")
        self.video_convert = Gst.ElementFactory.make("videoconvert", "video_convert")
        self.identity = Gst.ElementFactory.make("identity", "identity")
        self.app_sink = Gst.ElementFactory.make("appsink", "app_sink")

        self.pipeline.add(self.source)
        self.pipeline.add(self.video_convert)
        self.pipeline.add(self.identity)
        self.pipeline.add(self.app_sink)

        self.video_convert.link(self.identity)
        self.identity.link(self.app_sink)

        self.source.set_property("uri", uri)
        self.source.connect("pad-added", self.on_pad_added)

        self.identity.connect("handoff", self.handoff)

        self.app_sink.connect("new-sample", self.new_sample)
        self.app_sink.set_property("emit-signals", True)
        self.app_sink.set_property("drop", True)
        self.app_sink.set_property("max-buffers", 1)
        self.format = "RGB"
        self.width = 1920
        self.height = 1080
        self.caps = Gst.caps_from_string(
            f"video/x-raw,format={self.format},width={self.width},height={self.height}"
        )
        self.app_sink.set_property("caps", self.caps)

        self.fps_counter = FPSCounter(True, 5, "Sink")
        self.identity_fps_counter = FPSCounter(True, 5, "Identity")

    def handoff(self, buffer, data):
        self.identity_fps_counter.update()

    def new_sample(self, sink):
        ret, frame_number = sink.query_position(Gst.Format.DEFAULT)
        sample = sink.emit("pull-sample")
        if not sample:
            return Gst.FlowReturn.ERROR

        buffer = sample.get_buffer()

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            raise ValueError("Buffer mapping failed")
        frame = np.ndarray(
            shape=(self.height, self.width, 3), dtype=np.uint8, buffer=map_info.data
        ).copy()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        cv2.imwrite("frame.jpg", frame)
        buffer.unmap(map_info)

        self.fps_counter.update()
        return Gst.FlowReturn.OK

    def save_pipeline_graph(self, png_file="pipeline.png"):
        dot_file = png_file.replace(".png", ".dot")
        with open(dot_file, "w") as f:
            f.write(Gst.debug_bin_to_dot_data(self.pipeline, Gst.DebugGraphDetails.ALL))
        subprocess.run(["dot", "-Tpng", dot_file, "-o", png_file])
        logger.info(f"Saved pipeline graph as {png_file}")

    def on_pad_added(self, src, new_pad):
        logger.info(f"Received new pad '{new_pad.get_name()}' from '{src.get_name()}'")

        new_pad_caps = new_pad.get_current_caps()
        new_pad_struct = new_pad_caps.get_structure(0)
        new_pad_type = new_pad_struct.get_name()

        logger.info(f"Found {new_pad_type = }, trying to link...")
        if not new_pad_type.startswith("video/x-raw"):
            return

        sink_pad = self.video_convert.get_static_pad("sink")
        new_pad.link(sink_pad)

        self.save_pipeline_graph()

    def play(self):
        self.pipeline.set_state(Gst.State.PLAYING)

        try:
            self.main_loop.run()
        except KeyboardInterrupt:
            logger.info("Keyboard Interrupt")
            self.main_loop.quit()
        finally:
            self.pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    Gst.init(sys.argv[1:])
    uri = os.getenv("RTSP_1")
    player = Player(uri)
    player.play()
