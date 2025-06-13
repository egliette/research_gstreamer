import os

os.environ["GST_DEBUG"] = "2"
import logging
import subprocess
import sys

import gi
from dotenv import load_dotenv

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
from gi.repository import GLib, Gst

load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class MultiSourcePipeline:
    def __init__(self, uri0, uri1):
        self.uri0 = uri0
        self.uri1 = uri1
        Gst.init(sys.argv)
        self.pipeline = Gst.Pipeline.new("multisource_pipeline")
        self.create_elements()
        self.setup_pipeline()

    def save_pipeline_graph(self, png_file="pipeline.png"):
        dot_file = png_file.replace(".png", ".dot")
        with open(dot_file, "w") as f:
            f.write(Gst.debug_bin_to_dot_data(self.pipeline, Gst.DebugGraphDetails.ALL))
        subprocess.run(["dot", "-Tpng", dot_file, "-o", png_file])
        logger.info(f"Saved pipeline graph as {png_file}")

    def create_elements(self):
        # Main aggregator chain elements
        self.funnel = Gst.ElementFactory.make("funnel", "fun")
        self.streamiddemux = Gst.ElementFactory.make("streamiddemux", "sid")
        self.compositor = Gst.ElementFactory.make("compositor", "comp")
        self.vidconv_final = Gst.ElementFactory.make("videoconvert", "vidconv_final")
        self.fpssink = Gst.ElementFactory.make("fpsdisplaysink", "fpssink")
        self.ximagesink = Gst.ElementFactory.make("ximagesink", "ximagesink")

        self.fpssink.set_property("sync", False)
        self.fpssink.set_property("video-sink", self.ximagesink)

        # Branch 0 elements (Camera 0)
        self.src0 = Gst.ElementFactory.make("uridecodebin", "source0")
        self.src0.set_property("uri", self.uri0)
        self.conv0 = Gst.ElementFactory.make("videoconvert", "conv0")
        self.scale0 = Gst.ElementFactory.make("videoscale", "scale0")
        self.capsfilter0 = Gst.ElementFactory.make("capsfilter", "capsfilter0")
        caps0 = Gst.Caps.from_string("video/x-raw,width=640,height=360")
        self.capsfilter0.set_property("caps", caps0)

        # Branch 1 elements (Camera 1)
        self.src1 = Gst.ElementFactory.make("uridecodebin", "source1")
        self.src1.set_property("uri", self.uri1)
        self.conv1 = Gst.ElementFactory.make("videoconvert", "conv1")
        self.scale1 = Gst.ElementFactory.make("videoscale", "scale1")
        self.capsfilter1 = Gst.ElementFactory.make("capsfilter", "capsfilter1")
        caps1 = Gst.Caps.from_string("video/x-raw,width=640,height=360")
        self.capsfilter1.set_property("caps", caps1)

    def setup_pipeline(self):
        # Add all elements to the pipeline
        elements = [
            self.funnel,
            self.streamiddemux,
            self.compositor,
            self.vidconv_final,
            self.fpssink,
            self.src0,
            self.conv0,
            self.scale0,
            self.capsfilter0,
            self.src1,
            self.conv1,
            self.scale1,
            self.capsfilter1,
        ]
        for elem in elements:
            self.pipeline.add(elem)

        # Link the main aggregator chain: funnel -> streamiddemux -> compositor -> vidconv_final -> fpssink
        self.funnel.link(self.streamiddemux)
        self.streamiddemux.link(self.compositor)
        self.compositor.link(self.vidconv_final)
        self.vidconv_final.link(self.fpssink)

        # Setup Branch 0: src0 -> conv0 -> scale0 -> capsfilter0 -> funnel.sink_0
        self.src0.connect("pad-added", self.on_decodebin_pad_added, self.conv0)
        self.conv0.link(self.scale0)
        self.scale0.link(self.capsfilter0)
        fun_sink0 = self.funnel.get_request_pad("sink_0")
        capsfilter0_src = self.capsfilter0.get_static_pad("src")
        capsfilter0_src.link(fun_sink0)

        # Setup Branch 1: src1 -> conv1 -> scale1 -> capsfilter1 -> funnel.sink_1
        self.src1.connect("pad-added", self.on_decodebin_pad_added, self.conv1)
        self.conv1.link(self.scale1)
        self.scale1.link(self.capsfilter1)
        fun_sink1 = self.funnel.get_request_pad("sink_1")
        capsfilter1_src = self.capsfilter1.get_static_pad("src")
        capsfilter1_src.link(fun_sink1)

        # Link streamiddemux dynamic pads to compositor sink pads
        self.streamiddemux.connect(
            "pad-added", self.on_streamiddemux_pad_added, self.compositor
        )

    def on_decodebin_pad_added(self, decodebin, pad, target):
        caps = pad.get_current_caps()
        if not caps:
            return
        struct = caps.get_structure(0)
        name = struct.get_name()
        # Only link video/x-raw pads
        if name.startswith("video/"):
            sink_pad = target.get_static_pad("sink")
            pad.link(sink_pad)

    def on_streamiddemux_pad_added(self, demux, pad, compositor):
        pad_name = pad.get_name()
        index = int(
            pad_name.split("_")[1]
        )  # Extract index from pad name (e.g., "src_0" -> 0)
        mixer_pad = compositor.request_pad_simple(f"sink_{index}")
        mixer_pad.set_property("xpos", index * 640)
        mixer_pad.set_property("ypos", 0)
        pad.link(mixer_pad)

        self.save_pipeline_graph()

    def run(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted, exiting...")
        finally:
            self.pipeline.set_state(Gst.State.NULL)


def main():
    # Retrieve RTSP URIs from environment variables loaded by python-dotenv
    uri0 = os.getenv("RTSP_1")
    uri1 = os.getenv("RTSP_2")
    if not uri0 or not uri1:
        logger.error("RTSP_1 and/or RTSP_2 environment variables are not set")
        sys.exit(1)
    pipeline = MultiSourcePipeline(uri0, uri1)
    pipeline.run()


if __name__ == "__main__":
    main()
