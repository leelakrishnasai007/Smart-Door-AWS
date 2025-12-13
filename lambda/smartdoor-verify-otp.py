import json
import os
import boto3

dynamodb = boto3.resource("dynamodb")
PASSCODES_TABLE = "passcodes"
VISITORS_TABLE = "visitors"

passcodes_table = dynamodb.Table(PASSCODES_TABLE)
visitors_table = dynamodb.Table(VISITORS_TABLE)


def lambda_handler(event, context):
    # event comes from API Gateway HTTP API (JSON body)
    print("Event:", json.dumps(event))

    try:
        body = event.get("body")
        if isinstance(body, str):
            body = json.loads(body)
    except Exception as e:
        print("Failed to parse body:", e)
        return _response(400, {"message": "Invalid request body"})

    otp = (body or {}).get("otp")
    if not otp:
        return _response(400, {"message": "OTP is required"})

    # Look up OTP in DynamoDB
    resp = passcodes_table.get_item(Key={"otp": otp})
    item = resp.get("Item")
    if not item:
        # OTP not found or expired
        return _response(200, {"valid": False})

    face_id = item.get("faceId")

    # Get visitor name
    name = "Visitor"
    if face_id:
        v_resp = visitors_table.get_item(Key={"faceId": face_id})
        visitor = v_resp.get("Item")
        if visitor and "name" in visitor:
            name = visitor["name"]

    # Optionally, you could delete the OTP here so it's one-time use:
    # passcodes_table.delete_item(Key={"otp": otp})

    return _response(200, {"valid": True, "name": name})


def _response(status_code, body_dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            # allow JS in browser
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body_dict),
    }