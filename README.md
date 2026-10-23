# Sign Language Capture and Illustration System

A sensor-based sign language recognition project developed as part of Electronics and Telecommunication Engineering.

## Overview

This project aims to recognize hand gestures using wearable sensors instead of relying on a camera. Finger-bending and hand-motion data are collected and processed to identify gestures and present the recognized output as text or audio.

## Objectives

- Capture finger movements using flex sensors.
- Measure hand movement using an MPU6050 inertial measurement unit (IMU).
- Process sensor readings to recognize selected gestures.
- Display recognized gestures through a web-based dashboard.
- Explore text and audio output for improved communication accessibility.

## Hardware

- ESP32-S3 development board
- Flex sensors
- MPU6050 accelerometer and gyroscope
- LiPo battery and charging module
- Connecting wires and wearable glove setup

## Software and Technologies

- C/C++ for embedded firmware
- Python for data processing and model training
- HTML, CSS, and JavaScript for the dashboard
- Sensor data collection and gesture classification

## System Workflow

1. Flex sensors capture finger-bending measurements.
2. The MPU6050 captures hand-motion data.
3. The ESP32-S3 reads sensor values.
4. Gesture data is processed and classified.
5. The recognized gesture is displayed as text, with audio output as a project objective.

## Project Status

In development. Hardware integration, sensor calibration, gesture data collection, and recognition are being developed and tested.

## Future Improvements

- Improve recognition accuracy across different users.
- Expand the gesture vocabulary.
- Improve the dashboard and audio output.
- Document hardware connections and provide reproducible setup instructions.

## Author

**Aniket Aher** — Electronics and Telecommunication Engineering student.

[LinkedIn Profile](https://www.linkedin.com/in/aniket-aher-7a4ab8343/)

---

*Note: Features and implementation details will be updated as development progresses.*
