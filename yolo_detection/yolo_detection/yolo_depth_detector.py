# import rclpy
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

from ultralytics import YOLO
import cv2
from cv_bridge import CvBridge, CvBridgeError
import torch
import yaml
import numpy as np

# import required msgs
from sensor_msgs.msg import Image
from sensor_msgs.msg import PointCloud2


class YOLO_depth(Node):

    def __init__(self):
        super().__init__('YOLO_depth_detection')

        # Declare Parameters
        self.model = YOLO("yolo11n.pt")
  
        self.declare_parameter(name='names', value=None)
        self.labels = self.get_parameter(name='names').value
        print(self.labels)
        
        # Initialize Variables
        self.previous_bboxes = torch.tensor([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]])
        self.raw_image = None
        self.depth_image = None

        # Define QoS profile
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Create subcribers
        self.image_subscriber = self.create_subscription(
            Image,
            '/zed/zed_node/rgb_raw/image_rect_color',
            self.image_callback,
            qos_profile
        )
        
        self.depth_subscriber = self.create_subscription(
            Image,
            '/zed/zed_node/depth/depth_registered',
            self.depth_callback,
            qos_profile
        )
        
        # Timer setup
        self.main_timer = self.create_timer(0.2, self.main_timer_callback)

    # services
    def draw_bboxes(self, results, bboxes):

        color = (0, 255, 0)
        thickness = 3
        original_image = results[0].orig_img

        for row in bboxes :
            x_min, y_min, x_max, y_max, confidence, class_index = row.tolist()
            label = f"{results[0].names[class_index]}: {confidence:.2f}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            font_thickness = 1
            text_size = cv2.getTextSize(label, font, font_scale, font_thickness)[0]
            text_x, text_y = int(x_min), int(y_min) - 10  # Position above the box
            text_bg_color = (0, 255, 0)  # Same as rectangle color
            cv2.rectangle(original_image, (text_x, text_y - text_size[1]), (text_x + text_size[0], text_y), text_bg_color, -1)
            cv2.putText(original_image, label, (text_x, text_y), font, font_scale, (0, 0, 0), font_thickness)



    # Callback functions for timers
    def image_callback(self, msg):
        try:
            image = CvBridge().imgmsg_to_cv2(msg, "rgb8")
            self.raw_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        except CvBridgeError as e:
            self.get_logger().error(f"Failed to convert image: {e}")


    def depth_callback(self, msg):
        try:
            self.depth_image = CvBridge().imgmsg_to_cv2(msg, "32FC1")

        except CvBridgeError as e:
            self.get_logger().error(f"Failed to convert image: {e}")



    def main_timer_callback(self):
        if self.depth_image is not None and self.raw_image is not None:
            results = self.model(self.raw_image)
            original_image = results[0].orig_img
            bboxes = results[0].boxes.data

            # Iterate over each bounding box
            for bbox in bboxes:
                x_min, y_min, x_max, y_max, confidence, class_index = bbox.tolist()
                x_min, x_max, y_min, y_max = int(x_min), int(x_max), int(y_min), int(y_max)

                # Extract depth values for the bounding box
                depth_values = self.depth_image[y_min:y_max, x_min:x_max]
                valid_depths = depth_values[np.isfinite(depth_values)]
                depth_value = np.mean(valid_depths) if valid_depths.size > 0 else float('nan')

                print(f"Estimated depth value: {depth_value:.2f}")

            # Draw bounding boxes and display images
            self.draw_bboxes(results=results, bboxes=bboxes)
            cv2.imshow("Depth Image", self.depth_image)
            cv2.imshow("Detection Results", original_image)
            cv2.waitKey(1)
        else:
            print("Depth or raw image is None")



def main(args=None):
    rclpy.init(args=args)
    ros2_node = YOLO_depth()

    rclpy.spin(ros2_node)

    ros2_node.destroy_node()
    rclpy.shutdown()