source ../.env

# GStreamer Server
# Endpoint: `tcp://127.0.0.1:5000`
```
GST_DEBUG=2  gst-launch-1.0 -v \
    udpsrc port=5000 caps="application/x-rtp, media=video, encoding-name=H264, clock-rate=90000, payload=96" ! \
    rtph264depay ! \
    avdec_h264 ! \
    videoconvert ! \
    autovideosink
```
