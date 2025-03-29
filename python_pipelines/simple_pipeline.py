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
from dotenv import load_dotenv
from gi.repository import GLib, Gst

load_dotenv(dotenv_path="../.env")


class Player:
    def __init__(self, uri):
        self.main_loop = GLib.MainLoop()

        self.pipeline = Gst.Pipeline.new("multisource_player")

        self.source = Gst.ElementFactory.make("uridecodebin", "source")
        self.video_sink = Gst.ElementFactory.make("autovideosink", "video_sink")

        self.pipeline.add(self.source)
        self.pipeline.add(self.video_sink)

        self.source.set_property("uri", uri)
        self.source.connect("pad-added", self.on_pad_added)

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

        sink_pad = self.video_sink.get_static_pad("sink")
        new_pad.link(sink_pad)

        self.save_pipeline_graph()

    def play(self):
        self.pipeline.set_state(Gst.State.PLAYING)

        try:
            self.main_loop.run()
        except KeyboardInterrupt:
            pass

        self.pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    Gst.init(sys.argv[1:])
    uri = os.getenv("RTSP_1")
    player = Player(uri)
    player.play()
