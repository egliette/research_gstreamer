# Saving RTSP Streams Without Re-encoding Using GStreamer

In many use cases—such as archiving surveillance footage or processing video downstream—it’s desirable to **save an RTSP stream to a file without any re-encoding**. This ensures **maximum performance**, **preserves original quality**, and avoids unnecessary compute overhead.

GStreamer makes this possible by using **depayloader**, **parser**, and **muxer** elements tailored to the codec used in the RTSP stream.

---

## 🔁 What is "Zero Encoding"?

**Zero encoding** means:
- We don't decode or re-encode the video stream.
- We **directly remux** the raw RTP video into a file container (e.g., MP4 or TS).
- The stream remains in its **original codec and compression**.

---

## ⚠️ Important Notes

- The GStreamer pipeline **must match the codec** used in the RTSP stream.
- You must use the **correct depayloader and parser** elements depending on the stream format (e.g., H.264, MPEG-4 Part 2, MJPEG, etc.).
- If the wrong depay/parser is used, the pipeline will fail or produce broken output.

---

## 📦 Example Pipelines

Below are examples for **saving RTSP streams** into an `.mp4` file **without re-encoding**, depending on the codec:

### H.264 Stream (most common for cameras)

```bash
gst-launch-1.0 -e \
  rtspsrc location=<rtsp_url> protocols=tcp ! \
  rtph264depay ! \
  h264parse ! \
  mp4mux ! \
  filesink location=<output.mp4>
```

---

### MPEG-4 Part 2 (XVID / DivX style)

```bash
gst-launch-1.0 -e \
  rtspsrc location=<rtsp_url> protocols=tcp ! \
  rtpmp4vdepay ! \
  mpeg4videoparse ! \
  mp4mux ! \
  filesink location=<output.mp4>
```

---

## 🧬 Data Flow & Element I/O

Understanding how the **data flows** through the pipeline helps troubleshoot and modify pipelines correctly. Here’s what each element expects and produces:

| Element         | Input Type (Caps)                       | Output Type (Caps)                       | Purpose                                       |
|-----------------|------------------------------------------|------------------------------------------|-----------------------------------------------|
| `rtspsrc`       | RTSP stream (TCP or UDP)                | RTP packets (e.g., `application/x-rtp`) | Receives RTSP stream, outputs RTP             |
| `rtph264depay`  | `application/x-rtp` (H.264 payload)     | `video/x-h264`                          | Strips RTP headers to get raw H.264 NALs      |
| `rtpmp4vdepay`  | `application/x-rtp` (MPEG-4 payload)    | `video/mpeg`                            | Extracts raw MPEG-4 video frames              |
| `h264parse`     | `video/x-h264`                         | `video/x-h264` (aligned + formatted)    | Aligns, reorders, and ensures NAL unit format |
| `mpeg4videoparse`| `video/mpeg`                          | `video/mpeg` (parsed)                   | Ensures correct MPEG4 structure for muxing    |
| `mp4mux`        | Parsed video (e.g., `video/x-h264`)     | ISO MP4 container                       | Wraps the video stream into an `.mp4` file    |
| `filesink`      | File buffer                             | --                                       | Writes output to a file                       |

> 🧠 If any element receives an incompatible input type, the pipeline will **fail to link** or **throw caps negotiation errors**.

For more detailed information on GStreamer media types and capabilities (caps), you can refer to the following resources:

- [GStreamer Media Types and Properties](https://gstreamer.freedesktop.org/documentation/plugin-development/advanced/media-types.html)
- [GStreamer Caps Documentation](https://gstreamer.freedesktop.org/documentation/gstreamer/gstcaps.html)

---


## 💡 Tip

Use `-e` with `gst-launch-1.0` to ensure GStreamer finalizes the file properly when interrupted or stopped.
