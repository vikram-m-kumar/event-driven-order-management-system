import json
import os
import hashlib
from datetime import datetime, timezone
from logutil import log

import boto3

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

table = dynamodb.Table(os.environ["ORDERS_TABLE"])
QUEUE_URL = os.environ["ORDER_EVENTS_QUEUE_URL"]  # PaymentSuccessQueue URL
FAILURE_RATE = float(os.environ.get("PAYMENT_FAILURE_RATE", 0.3))

def _should_fail(order_id, rate):
    h = hashlib.md5(order_id.encode("utf-8")).hexdigest()
    bucket = int(h[:2], 16) / 255.0
    return bucket < rate

def lambda_handler(event, context):
    for record in event.get("Records", []):

        aws_request_id = getattr(context, "aws_request_id", None)
        attrs = record.get("messageAttributes") or {}
        cid = (attrs.get("correlation-id") or {}).get("stringValue")

        body = record.get("body", "{}")
        msg = json.loads(body)

        if msg.get("type") != "InventoryReserved":
            continue

        order_id = msg["order_id"]
        now = datetime.now(timezone.utc).isoformat()

        receive_count = int((record.get("attributes") or {}).get("ApproximateReceiveCount", "1"))

        log(
            "INFO",
            "payment_attempt",
            correlation_id=cid,
            aws_request_id=aws_request_id,
            order_id = order_id,
            attempt = receive_count,
            failure_rate = FAILURE_RATE
        )

        # ✅ Store attempt count (idempotent: set to the SQS receive_count)
        table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET payment_attempt_count = :c, last_payment_attempt_at = :t",
            ExpressionAttributeValues={":c": receive_count, ":t": now},
        )

        # Simulate failure
        if _should_fail(order_id, FAILURE_RATE):
            log(
                "INFO",
                "payment_declined_simulated",
                correlation_id= cid,
                aws_request_id=aws_request_id,
                order_id = order_id,
                attempt = receive_count
            )
            raise RuntimeError("Payment declined (simulated)")

        # Success path
        table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET #s = :s, updated_at = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "PAID", ":u": now},
        )

        log(
            "INFO",
            "Payment_Success",
            correlation_id= cid,
            aws_request_id= aws_request_id,
            order_id = order_id,
            attempt = receive_count,
            new_staus = "PAID"
        )

        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps({"type": "PaymentSuccess", "order_id": order_id, "updated_at": now}),
            MessageAttributes = {
                "correlation-id": {"StringValue": cid, "DataType": "String"}, 
                "order_id": {"StringValue": order_id, "DataType": "String"}
            }
        )

        log(
            "INFO",
            "Payment_Success_published",
            correlation_id= cid,
            aws_request_id= aws_request_id,
            order_id = order_id,
            attempt = receive_count,
            queue = "PaymentSuccessQueue"
        )