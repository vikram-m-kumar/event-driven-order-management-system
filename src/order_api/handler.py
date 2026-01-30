import json
import os
import boto3
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from logutil import log


dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

ORDERS_TABLE = os.environ["ORDERS_TABLE"]
ORDER_EVENTS_QUEUE_URL = os.environ["ORDER_EVENTS_QUEUE_URL"]

table = dynamodb.Table(ORDERS_TABLE)

def _json_safe(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj%1 == 0 else float(obj)
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    return obj



def _response(status_code: int, body: dict, extra_headers: dict | None = None):
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(_json_safe(body)),
        "isBase64Encoded": False,
    }



def lambda_handler(event, context):

    aws_request_id = getattr(context, "aws_request_id", None)

    headers = event.get("headers") or {}
    cid = headers.get("X-Correlation-Id") or headers.get("x-correlation-id") or str(uuid.uuid4())



    path = event.get("path", "")
    method = event.get("httpMethod", "")
    
    log("INFO", "http_request_received",
        correlation_id=cid,
        aws_request_id=aws_request_id,
        method=method,
        path=path
    )
    
    if method == "GET" and path.endswith("/health"):
        return _response(200, {"message": "order_api ok"})
    
    if method == "POST" and path.endswith("/orders"):
        try:
            body = event.get("body") or "{}"
            payload = json.loads(body)

            customer_id = payload.get("customer_id")
            items = payload.get("items", [])

            if not customer_id or not isinstance(items, list) or len(items) == 0:
                return _response(400, {"error": "customer_id and non-empty items[] are required"})

            order_id = f"ORD-{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()
            order_item = {
                "order_id": order_id,
                "customer_id": customer_id,
                "items": items,
                "status": "PENDING",
                "created_at": now,
                "updated_at": now
            }
            
            table.put_item(Item = order_item)

            log("INFO", "order_created",
            correlation_id=cid,
            aws_request_id=aws_request_id,
            order_id=order_id,
            status="PENDING",
            customer_id=customer_id
            )


            sqs.send_message(
                QueueUrl=ORDER_EVENTS_QUEUE_URL,
                MessageBody=json.dumps({
                    "type": "OrderCreated",
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "items": items,
                    "created_at": now
                }),
                MessageAttributes={
                    "correlation-id": {"DataType": "String", "StringValue": cid},
                    "order_id": {"DataType": "String", "StringValue": order_id},
                }
            )

            log("INFO", "order_published_to_queue",
                correlation_id=cid,
                aws_request_id=aws_request_id,
                order_id=order_id,
                queue="OrderCreatedQueue"
            )

            return _response(201, {"order_id": order_id, "status": "PENDING"}, {"X-Correlation-Id": cid})


        except json.JSONDecodeError:
            return _response(400, {"error": "Invalid JSON body"})
        except Exception as e:
            log("ERROR", "order_create_failed",
                correlation_id=cid,
                aws_request_id=aws_request_id,
                error=str(e)
            )
            return _response(500, {"error": "Internal server error"})


    if method == "GET" and "/orders/" in path:
        order_id = (event.get("pathParameters") or {}).get("order_id")
        if not order_id:
            return _response(400, {"error": "order_id is required"})
        
        resp = table.get_item(Key = {"order_id": order_id})
        item = resp.get("Item")

        if not item:
            return _response(404, {"error": "Order not found"})
        
        return _response(200, item)
        
    return _response(404, {"error": "Not found"})


    
