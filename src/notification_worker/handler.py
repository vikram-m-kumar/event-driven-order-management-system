import json
import os
from datetime import datetime, timezone
from logutil import log

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])

def lambda_handler(event, context):
    for record in event.get("Records", []):

        aws_request_id = getattr(context, "aws_request_id", None)
        attrs = record.get("messageAttributes") or {}
        cid = (attrs.get("correlation-id") or {}).get("stringValue")

        body = record.get("body", "{}")
        msg = json.loads(body)

        if msg.get("type") != "PaymentSuccess":
            continue

        order_id = msg["order_id"]
        now = datetime.now(timezone.utc).isoformat()

        log(
            "INFO",
            "Notification Worker start",
            correlation_id= cid,
            aws_request_id=aws_request_id,
            order_id = order_id
        )

        table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET #s = :s, updated_at = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "CONFIRMED", ":u": now},
        )

        log(
            "INFO",
            "Status updated to CONFIRMED",
            correlation_id= cid,
            aws_request_id=aws_request_id,
            order_id = order_id
        )