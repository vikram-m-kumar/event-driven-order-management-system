import boto3
import json
import os
from datetime import datetime, timezone
from logutil import log



dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

table = dynamodb.Table(os.environ["ORDERS_TABLE"])
QUEUE_URL = os.environ["ORDER_EVENTS_QUEUE_URL"]



def lambda_handler(event, context):
    for record in event.get("Records", []):

        aws_request_id = getattr(context, "aws_request_id", None)
        attrs = record.get("messageAttributes") or {}
        cid = (attrs.get("correlation-id") or {}).get("stringValue")

        log("INFO", "sqs_message_received", correlation_id = cid, aws_request_id = aws_request_id, queue="OrderCreatedQueue")

        body = record.get("body", "{}")
        msg = json.loads(body)
        if msg.get("type") != "OrderCreated":
            continue
            
        order_id = msg["order_id"]
        now = datetime.now(timezone.utc).isoformat()

        log("INFO", "inventory_reserve_start", correlation_id=cid, aws_request_id=aws_request_id, order_id=order_id)


        table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET #s = :s, updated_at = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "INVENTORY_RESERVED", ":u": now},
        )

        log("INFO", "inventory_reserved", 
        correlation_id=cid, 
        aws_request_id=aws_request_id, 
        order_id=order_id,
        new_status = "Inventory Reserved")
 

        sqs.send_message(
            QueueUrl = QUEUE_URL,
            MessageBody = json.dumps({"type": "InventoryReserved", "order_id": order_id, "updated_at": now}),
            MessageAttributes = {
                "correlation-id": {"StringValue": cid or "", "DataType": "String"},
                "order_id":  {"StringValue": order_id, "DataType": "String"},
                }
        )
        
        log("INFO", "inventory_reserved_published", 
        correlation_id=cid, 
        aws_request_id=aws_request_id, 
        order_id=order_id,
        queue="InventoryReservedQueue")


