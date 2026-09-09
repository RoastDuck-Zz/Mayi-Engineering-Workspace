# ROS2 Jazzy driver status

The planned package is `guidedog_l2_driver` with node `l2_ethernet_node`.
It will use `sensor_data` QoS and publish sensor-native data with
`frame_id=lidar_link` to `/lidar/points` and `/lidar/imu`. PointCloud2 fields
are intended to be `x,y,z` FLOAT32, `intensity` FLOAT32, `time` FLOAT32 and
`ring` UINT32. IMU covariance remains unknown unless a trusted source is found;
zero covariance must not imply perfect measurement.

This phase does not create the ROS2 package because the Pi has no
`/opt/ros/jazzy/setup.bash`, and the Ethernet acceptance gate is not complete:
the 60-second raw UDP stream is CRC-clean but Cloud sequence gaps match larger
device timestamp intervals and are classified `LINK_OR_SOURCE_LOSS_LIKELY`.
Installing ROS2 online was explicitly out of scope. Once Jazzy is present and
the transport classification is reviewed, the package can be added with pure
conversion tests that also run when ROS2 is absent.

No TF is published by the future node until the mount validation in
`L2_MOUNT_VALIDATION.md` verifies all axes and translation.
