import json
import os
import boto3
from datetime import datetime, timezone
from logutil import log

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])


def lambda_handler(event, context):
    for record in event.get("Records", []):

        aws_request_id = getattr(context, "aws_request_id", None)
        attrs = record.get("messageAttributes") or {}
        cid = (attrs.get("correlation-id") or {}).get("stringValue")

        body = record.get("body", "{}")
        msg = json.loads(body)

        log("ERROR", "dlq_message_received",
            correlation_id=cid,
            aws_request_id=aws_request_id,
            queue="InventoryReservedDLQ",
            raw_body=body
        )

        order_id = msg.get("order_id")
        if not order_id:
            print("DLQ message missing order_id: ", msg)
            continue

        now = datetime.now(timezone.utc).isoformat()

        table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET #s = :s, updated_at = :u, payment_error = :e",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "PAYMENT_FAILED",
                ":u": now,
                ":e": "Moved to DLQ after retries (simulated payment decline)",
            },
        )

        log("ERROR", "order_marked_payment_failed",
            correlation_id=cid,
            aws_request_id=aws_request_id,
            order_id=order_id,
            new_status="PAYMENT_FAILED"
        )
