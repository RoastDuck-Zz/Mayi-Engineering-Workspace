# L2 mount validation

The only verified mechanical fact is `+Z_lidar → +X_base`. `base_link` uses
REP-103: +X is robot forward, +Y is left and +Z is up. The decoder and Ethernet
driver preserve L2 sensor-native XYZ; no 90-degree rotation is applied in packet
validation, replay or ROS conversion.

The candidate rotation, pending confirmation of native X/Y, is:

```text
X_base =  Z_lidar
Y_base =  Y_lidar
Z_base = -X_lidar
```

It is not calibrated or verified. Translation is also unknown and remains null.
Before any static TF is published, place a clear target in the robot forward,
left and ground/upper directions one at a time and record the dominant native
axis. The result must be an explicit axis mapping; it must not be tuned by
swapping axes until an RViz view looks plausible.

The future TF must use parent/child semantics explicitly: `base_link` is the
parent and `lidar_link` the child. A full static transform requires verified
rotation and measured translation. Until then `publish_tf=false`.
