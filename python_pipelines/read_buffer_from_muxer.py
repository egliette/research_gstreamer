import os

os.environ["GST_DEBUG"] = "2"
import logging
import subprocess
import sys

import gi
from dotenv import load_dotenv

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
import cv2
import numpy as np
from gi.repository import GLib, Gst
from helper.profiler import FPSCounter

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
        self.fps_counter = FPSCounter(True, 5, "FakeSink")

    def save_pipeline_graph(self, png_file="pipeline.png"):
        dot_file = png_file.replace(".png", ".dot")
        with open(dot_file, "w") as f:
            f.write(Gst.debug_bin_to_dot_data(self.pipeline, Gst.DebugGraphDetails.ALL))
        subprocess.run(["dot", "-Tpng", dot_file, "-o", png_file])
        logger.info(f"Saved pipeline graph as {png_file}")

    def create_elements(self):
        # Create compositor and downstream elements.
        self.compositor = Gst.ElementFactory.make("compositor", "comp")
        self.vidconv_final = Gst.ElementFactory.make("videoconvert", "vidconv_final")
        # Use fakesink to capture frames.
        self.fake_sink = Gst.ElementFactory.make("fakesink", "fake_sink")
        fake_sink_pad = self.fake_sink.get_static_pad("sink")
        fake_sink_pad.add_probe(Gst.PadProbeType.BUFFER, self.on_fake_sink_probe)

        # Branch 0 elements (Camera 0)
        self.src0 = Gst.ElementFactory.make("uridecodebin", "source0")
        self.src0.set_property("uri", self.uri0)
        self.conv0 = Gst.ElementFactory.make("videoconvert", "conv0")
        self.scale0 = Gst.ElementFactory.make("videoscale", "scale0")
        self.capsfilter0 = Gst.ElementFactory.make("capsfilter", "capsfilter0")
        caps0 = Gst.Caps.from_string("video/x-raw,format=RGB,width=640,height=360")
        self.capsfilter0.set_property("caps", caps0)

        # Branch 1 elements (Camera 1)
        self.src1 = Gst.ElementFactory.make("uridecodebin", "source1")
        self.src1.set_property("uri", self.uri1)
        self.conv1 = Gst.ElementFactory.make("videoconvert", "conv1")
        self.scale1 = Gst.ElementFactory.make("videoscale", "scale1")
        self.capsfilter1 = Gst.ElementFactory.make("capsfilter", "capsfilter1")
        caps1 = Gst.Caps.from_string("video/x-raw,format=RGB,width=640,height=360")
        self.capsfilter1.set_property("caps", caps1)

    def setup_pipeline(self):
        # Add all elements to the pipeline.
        elements = [
            self.compositor,
            self.vidconv_final,
            self.fake_sink,
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

        # Link the compositor chain: compositor -> videoconvert -> fakesink.
        self.compositor.link(self.vidconv_final)
        self.vidconv_final.link(self.fake_sink)

        # Setup Branch 0: src0 -> conv0 -> scale0 -> capsfilter0 -> compositor sink pad.
        self.src0.connect("pad-added", self.on_decodebin_pad_added, self.conv0)
        self.conv0.link(self.scale0)
        self.scale0.link(self.capsfilter0)
        comp_sink0 = self.compositor.request_pad_simple("sink_0")
        capsfilter0_src = self.capsfilter0.get_static_pad("src")
        capsfilter0_src.link(comp_sink0)
        comp_sink0.set_property("xpos", 0)
        comp_sink0.set_property("ypos", 0)

        # Setup Branch 1: src1 -> conv1 -> scale1 -> capsfilter1 -> compositor sink pad.
        self.src1.connect("pad-added", self.on_decodebin_pad_added, self.conv1)
        self.conv1.link(self.scale1)
        self.scale1.link(self.capsfilter1)
        comp_sink1 = self.compositor.request_pad_simple("sink_1")
        capsfilter1_src = self.capsfilter1.get_static_pad("src")
        capsfilter1_src.link(comp_sink1)
        comp_sink1.set_property("xpos", 640)
        comp_sink1.set_property("ypos", 0)

        self.save_pipeline_graph()

    def on_decodebin_pad_added(self, decodebin, pad, target):
        caps = pad.get_current_caps()
        if not caps:
            return
        struct = caps.get_structure(0)
        name = struct.get_name()
        if name.startswith("video/"):
            sink_pad = target.get_static_pad("sink")
            pad.link(sink_pad)

    def on_fake_sink_probe(self, pad, info):
        composite_width = 1280
        composite_height = 360
        self.fps_counter.update()
        buffer = info.get_buffer()
        buffer_size = buffer.get_size()

        if buffer_size < composite_height * composite_height * 3:
            return Gst.PadProbeReturn.OK

        success, map_info = buffer.map(Gst.MapFlags.READ)

        composite_frame = np.ndarray(
            shape=(composite_height, composite_width, 3),
            dtype=np.uint8,
            buffer=map_info.data,
        ).copy()

        # Convert from RGB to BGR
        composite_frame = cv2.cvtColor(composite_frame, cv2.COLOR_RGB2BGR)
        cv2.imwrite("composite_frame.jpg", composite_frame)

        # Split the composite frame into two halves.
        half_width = composite_width // 2
        frame_cam0 = composite_frame[:, :half_width]
        frame_cam1 = composite_frame[:, half_width:]
        cv2.imwrite("camera0.jpg", frame_cam0)
        cv2.imwrite("camera1.jpg", frame_cam1)

        buffer.unmap(map_info)
        return Gst.PadProbeReturn.OK

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
    uri0 = os.getenv("RTSP_1")
    uri1 = os.getenv("RTSP_2")
    if not uri0 or not uri1:
        logger.error("RTSP_1 and/or RTSP_2 environment variables are not set")
        sys.exit(1)
    pipeline = MultiSourcePipeline(uri0, uri1)
    pipeline.run()


if __name__ == "__main__":
    main()
