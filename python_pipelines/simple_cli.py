import os

os.environ["GST_DEBUG"] = "2"
import logging
import subprocess
import sys

import gi
from dotenv import load_dotenv
from gi.repository import GLib, Gst

load_dotenv(dotenv_path="../.env")

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")

logging.basicConfig(
    level=logging.DEBUG, format="[%(name)s] [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)


class Player:
    def __init__(self, pipeline_desc):
        self.main_loop = GLib.MainLoop()
        self.pipeline = Gst.parse_launch(pipeline_desc)

    def save_pipeline_graph(self, png_file="pipeline.png"):
        dot_file = png_file.replace(".png", ".dot")
        with open(dot_file, "w") as f:
            f.write(Gst.debug_bin_to_dot_data(self.pipeline, Gst.DebugGraphDetails.ALL))
        subprocess.run(["dot", "-Tpng", dot_file, "-o", png_file])
        logger.info(f"Saved pipeline graph as {png_file}")

    def play(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        GLib.timeout_add_seconds(5, self.save_pipeline_graph)

        try:
            self.main_loop.run()
        except KeyboardInterrupt:
            pass

        self.pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    Gst.init(sys.argv[1:])
    pipeline_desc = """
    Your gstreamer pipeline go here
    """
    player = Player(pipeline_desc)
    player.play()
