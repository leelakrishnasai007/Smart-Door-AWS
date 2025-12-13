# Replace SNS_ARN

import json
import os
import random
import time
import boto3

dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

PASSCODES_TABLE = "passcodes"
VISITORS_TABLE = "visitors"
SNS_TOPIC_ARN = "***********************"  # same topic you used before

passcodes_table = dynamodb.Table(PASSCODES_TABLE)
visitors_table = dynamodb.Table(VISITORS_TABLE)


def generate_otp() -> str:
    return f"{random.randint(0, 999999):06d}"


def store_otp(face_id: str, otp: str):
    ttl_seconds = int(time.time()) + 300  # 5 minutes
    passcodes_table.put_item(
        Item={
            "otp": otp,
            "faceId": face_id,
            "ttl": ttl_seconds,
        }
    )


def send_owner_email(visitor_name: str, note: str, otp: str):
    subject = "Smart Door OTP for Unknown Visitor"
    msg_lines = [
        f"Unknown visitor approved.",
        f"Name: {visitor_name}",
        f"Note: {note or '(no note)'}",
        "",
        f"OTP: {otp}",
        "",
        "Share this OTP with the visitor so they can open the virtual door.",
    ]
    message = "\n".join(msg_lines)
    sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=message)


def lambda_handler(event, context):
    print("Event:", json.dumps(event))

    # Parse JSON body (HTTP API format)
    body = event.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except Exception as e:
            print("Failed to parse body:", e)
            return _response(400, {"ok": False, "message": "Invalid body"})

    name = (body or {}).get("name")
    note = (body or {}).get("note", "")

    if not name:
        return _response(400, {"ok": False, "message": "Name is required"})

    # For unknown visitors we just create a synthetic faceId
    face_id = f"unknown-{int(time.time())}"

    otp = generate_otp()
    store_otp(face_id, otp)
    send_owner_email(name, note, otp)

    # Optionally insert a minimal visitor record (no photos)
    visitors_table.put_item(
        Item={
            "faceId": face_id,
            "name": name,
            "phoneNumber": "unknown",
        }
    )

    return _response(200, {"ok": True})


def _response(status_code, body_dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body_dict),
    }
