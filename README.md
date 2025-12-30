# Smart Door System on AWS

This project implements a cloud-based smart door system using:

- **Amazon Kinesis Video Streams** for ingesting camera video
- **Amazon Rekognition** for face recognition on the video stream
- **Amazon Kinesis Data Streams** as the event bus
- **AWS Lambda** for stream processing and OTP logic (`smartdoor-lf1`, `smartdoor-verify-otp`, `smartdoor-register-visitor`)
- **Amazon DynamoDB** for storing visitors and one-time passcodes
- **Amazon SNS** for sending email notifications and OTPs
- **Amazon S3** for hosting static web pages (unknown visitor approval page and virtual door page)

## Smart Door Preview

<p align="center">
  <img src="images/Admin Access.png" width="900">
</p>

<p align="center">
  <img src="images/UKV Web Page" width="900">
</p>

<p align="center">
  <img src="images/UKV Opened" width="900">
</p>


## System Overview (architecture)

<p align="center">
  <img src="images/Archi Diagram.jpg" width="900">
</p>

## Features

- Detects known visitors using Rekognition face collection.
- Sends an email with an OTP when a known visitor is recognized.
- For unknown visitors, emails a link to a web form where the owner can approve the visitor and generate an OTP.
- Virtual door web page where a visitor can enter an OTP to gain temporary access.

## Project Structure

- `lambda/` – Lambda function source code.
- `web/` – Static HTML pages hosted on S3.
- `templates/` – Example JSON templates for AWS resources (e.g., Rekognition stream processor).
- `diagrams/` – Architecture diagrams.
- `docs/` – Project report and documentation.

## How to Use (High-level)

1. Deploy the Lambda functions and configure IAM roles.
2. Create and configure the Kinesis Video Stream, Kinesis Data Stream, and Rekognition stream processor.
3. Create DynamoDB tables for `visitors` and `passcodes` and set TTL on passcodes.
4. Configure the SNS topic and subscribe an email address.
5. Host `web/wp1-unknown.html` and `web/wp2-door.html` on S3 as static websites.
6. Start streaming video to Kinesis Video Streams from a camera or RTSP source.
7. Test the known and unknown visitor flows.

