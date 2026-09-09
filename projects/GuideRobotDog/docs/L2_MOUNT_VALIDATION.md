# L2 mount validation

The current verified mechanical fact is `+Z_lidar → -Z_base`. The former
`+Z_lidar → +X_base` statement is superseded by the later installation
confirmation and remains historical only. `base_link` uses
REP-103: +X is robot forward, +Y is left and +Z is up. The decoder and Ethernet
driver preserve L2 sensor-native XYZ; no 90-degree rotation is applied in packet
validation, replay or ROS conversion.

The complete rotation is unknown because native X/Y directions remain
unverified. No candidate matrix is active in configuration:

```text
X_base = UNKNOWN
Y_base = UNKNOWN
Z_base = -Z_lidar
```

It is not calibrated or verified. Translation is also unknown and remains null.
Before any static TF is published, place a clear target in the robot forward,
left and ground/upper directions one at a time and record the dominant native
axis. The result must be an explicit axis mapping; it must not be tuned by
swapping axes until an RViz view looks plausible.

The future TF must use parent/child semantics explicitly: `base_link` is the
parent and `lidar_link` the child. A full static transform requires verified
rotation and measured translation. Until then `publish_tf=false`.
