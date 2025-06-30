source ../.env

gst-launch-1.0 -e \
    rtspsrc location=$RTSP_1 latency=200 ! \
    parsebin ! \
    mp4mux ! \
    filesink location=buffered_output.mp4
