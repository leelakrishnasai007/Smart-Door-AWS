# Replace SNS ARN
# Replace URL
# Replace Email-ID


import base64
import json
import random
import time

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

VISITORS_TABLE = "visitors"
PASSCODES_TABLE = "passcodes"
RATE_LIMITS_TABLE = "rate_limits"
SNS_TOPIC_ARN = "*****************************"

UNKNOWN_VISITOR_PAGE_URL = (
    "http://**********.s3-website-us-east-1.amazonaws.com/web/wp1-unknown.html"
)

visitors_table = dynamodb.Table(VISITORS_TABLE)
passcodes_table = dynamodb.Table(PASSCODES_TABLE)
rate_limits_table = dynamodb.Table(RATE_LIMITS_TABLE)


def generate_otp() -> str:
    """Generate a 6-digit OTP as a string."""
    return f"{random.randint(0, 999999):06d}"


def store_otp(face_id: str, otp: str):
    """Store OTP in DynamoDB with TTL ~5 minutes."""
    ttl_seconds = int(time.time()) + 300  # 5 minutes from now
    print(f"Storing OTP for faceId={face_id} with ttl={ttl_seconds}")
    passcodes_table.put_item(
        Item={
            "otp": otp,
            "faceId": face_id,
            "ttl": ttl_seconds,
        }
    )


def send_otp_email(email: str, name: str, otp: str):
    """Send OTP by email using SNS."""
    subject = "Your Smart Door OTP"
    message = f"Hello {name},\n\nYour one-time passcode is: {otp}\n\nIt is valid for 5 minutes."
    print(f"Sending OTP email to {email} via SNS topic {SNS_TOPIC_ARN}")
    try:
        # Note: SNS email ignores the 'email' variable; it goes to all subscribers of the topic.
        resp = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message,
        )
        print("SNS publish success for OTP:", resp.get("MessageId"))
    except ClientError as e:
        print("SNS publish FAILED for OTP:", e)
        raise


def get_visitor_by_face(face_id: str):
    """Look up visitor info from visitors table by FaceId."""
    print(f"Looking up visitor by faceId={face_id}")
    response = visitors_table.get_item(Key={"faceId": face_id})
    item = response.get("Item")
    if not item:
        print(f"No visitor record found for faceId={face_id}")
    else:
        print(f"Found visitor record for faceId={face_id}: {item}")
    return item


def acquire_rate_limit(key: str, window_seconds: int) -> bool:
    """
    Simple rate limit using DynamoDB:
      - If there's no item, or its ttl is in the past -> allow and set new ttl.
      - If ttl is in the future -> block.

    This does NOT depend on DynamoDB's TTL feature to be perfect; TTL is
    only used to auto-clean rows eventually.
    """
    now = int(time.time())
    new_ttl = now + window_seconds
    print(f"[RateLimit] Checking key={key}, window={window_seconds}s, now={now}")

    try:
        # 1) Read existing item (if any)
        resp = rate_limits_table.get_item(Key={"id": key})
        item = resp.get("Item")

        if item:
            existing_ttl_raw = item.get("ttl", 0)
            try:
                existing_ttl = int(existing_ttl_raw)
            except Exception:
                existing_ttl = 0
            print(f"[RateLimit] Existing item for {key} with ttl={existing_ttl}")
            if existing_ttl > now:
                # Still inside the window -> block
                print(
                    f"[RateLimit] ACTIVE for {key} "
                    f"(expires at {existing_ttl}), skipping send."
                )
                return False

        # 2) No item or expired -> allow and set new ttl
        rate_limits_table.put_item(
            Item={
                "id": key,
                "ttl": new_ttl,
            }
        )
        print(f"[RateLimit] ALLOWED for {key}, new ttl={new_ttl}")
        return True

    except ClientError as e:
        print(f"[RateLimit] DynamoDB error for key={key}: {e}")
        # On error, be safe and block rather than spamming
        return False


def process_known_visitor(face_id: str):
    """Generate and send OTP for a known visitor, with rate limiting."""
    # allow at most once per 5 minutes per face
    if not acquire_rate_limit(f"known-{face_id}", 300):
        # Already sent recently; skip
        return

    visitor = get_visitor_by_face(face_id)
    if not visitor:
        # Nothing to do if we don't have a record
        return

    name = visitor.get("name", "Visitor")
    otp = generate_otp()
    store_otp(face_id, otp)

    # For this project, send OTP to YOUR email (owner) so you can see it.
    owner_email = "**********************"
    send_otp_email(owner_email, name, otp)

    print(f"Generated OTP {otp} for known visitor {name} ({face_id})")


def notify_unknown_visitor():
    """Send email to owner with link to unknown visitor page, rate-limited globally."""
    # global 5-minute limit for unknown visitor emails
    if not acquire_rate_limit("unknown-global", 300):
        return

    subject = "Unknown visitor at Smart Door"
    message = (
        "An unknown visitor was detected at the smart door.\n\n"
        f"To approve this visitor and generate an OTP, open this page:\n{UNKNOWN_VISITOR_PAGE_URL}\n"
    )
    print(f"Sending UNKNOWN visitor email via SNS topic {SNS_TOPIC_ARN}")
    try:
        resp = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message,
        )
        print("SNS publish success for UNKNOWN visitor:", resp.get("MessageId"))
    except ClientError as e:
        print("SNS publish FAILED for UNKNOWN visitor:", e)
        raise

    print("Sent unknown visitor notification email.")


def lambda_handler(event, context):
    """
    Entry point for Kinesis trigger.

    For each Kinesis record:
      1. Decode base64
      2. Parse Rekognition JSON
      3. Look for FaceSearchResponse -> MatchedFaces -> FaceId
      4. If known FaceId -> generate OTP and email (rate-limited)
      5. If no MatchedFaces -> unknown visitor -> email owner with WP1 link (rate-limited)
    """
    print("Received event (trimmed):", json.dumps(event)[:1000])

    for record in event.get("Records", []):
        try:
            payload = base64.b64decode(record["kinesis"]["data"])
            rek_event = json.loads(payload)
            print("Decoded Rekognition event fragment:", json.dumps(rek_event)[:500])
        except Exception as e:
            print("Failed to decode record:", e)
            continue

        face_search_list = rek_event.get("FaceSearchResponse", [])
        print(f"FaceSearchResponse count: {len(face_search_list)}")

        for fs in face_search_list:
            matched_faces = fs.get("MatchedFaces", [])
            if not matched_faces:
                print("Unknown visitor detected (no MatchedFaces).")
                notify_unknown_visitor()
                continue

            best_match = matched_faces[0]
            face = best_match.get("Face", {})
            similarity = best_match.get("Similarity", 0.0)
            face_id = face.get("FaceId")

            print(f"Detected faceId={face_id}, similarity={similarity}")
            if face_id:
                process_known_visitor(face_id)

    return {"statusCode": 200}
