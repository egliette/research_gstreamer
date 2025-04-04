source ../.env

# GStreamer Server
# Endpoint: `tcp://127.0.0.1:5000`
```
GST_DEBUG=2 gst-launch-1.0 \
    uridecodebin uri=$RTSP_1 ! \
    x264enc tune=zerolatency ! \
    rtph264pay config-interval=1 pt=96 ! \
    application/x-rtp,media=video,encoding-name=H264,clock-rate=90000,payload=96 ! \
    udpsink host=127.0.0.1 port=5000
```
