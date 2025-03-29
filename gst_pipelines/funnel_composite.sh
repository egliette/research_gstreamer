source ../.env

compositor_locations="sink_0::xpos=0 sink_0::ypos=0 sink_1::xpos=640 sink_1::ypos=0"

GST_DEBUG=2 gst-launch-1.0 \
    funnel name=fun !\
    queue leaky=no max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! \
    streamiddemux name=sid \
    compositor name=comp start-time-selection=0 $compositor_locations ! \
    queue leaky=no max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! \
    videoconvert ! \
    queue leaky=no max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! \
    fpsdisplaysink video-sink=ximagesink sync=false \
    uridecodebin uri=$RTSP_1 ! \
    videoconvert ! \
    videoscale ! \
    video/x-raw,width=640,height=360 ! \
    queue leaky=no max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! \
    fun.sink_0 \
    sid.src_0 ! \
    queue leaky=downstream max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! \
    comp.sink_0 \
    uridecodebin uri=$RTSP_2 ! \
    videoconvert ! \
    videoscale ! \
    video/x-raw,width=640,height=360 ! \
    queue leaky=no max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! \
    fun.sink_1 \
    sid.src_1 ! \
    queue leaky=downstream max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! \
    comp.sink_1
