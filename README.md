# Event-Driven Order Management System (AWS, Python)

## Overview
This project implements a **production-style event-driven order management system**
using **AWS serverless services** and **Python-based microservices**.

The system models a real-world order lifecycle where each step is handled
asynchronously and independently to ensure **scalability, fault isolation, and reliability**.

It is designed to resemble architectures used in **banking, e-commerce, and payment processing systems**.

---

## Business Problem
In real-world systems, order processing must:
- Handle high traffic
- Avoid tight coupling between services
- Retry transient failures
- Track state across distributed components
- Provide observability for support teams

This project solves these problems using **event-driven architecture**.

---

## High-Level Architecture

**Flow:**
1. Client creates an order via REST API
2. Order service publishes an event to SQS
3. Inventory service reserves inventory
4. Payment service attempts payment with retries
5. Notification service sends confirmation
6. Failed payments are routed to a DLQ

(See `/docs/architecture.png`)

---

## Architecture Components

### API Layer
- **API Gateway**
- **Order API Lambda**
- Accepts HTTP requests
- Writes initial order state to DynamoDB
- Publishes domain events to SQS

### Event Processing Layer
Each step is handled by a **dedicated Lambda worker**:
- Inventory Worker
- Payment Worker
- Notification Worker
- DLQ Handler

All communication is **asynchronous via SQS**.

### Data Layer
- **DynamoDB**
- Stores order state
- Acts as the single source of truth

---

## Event-Driven Workflow

| Step | Service | Event | Result |
|----|--------|------|--------|
| Order Created | Order API | `OrderCreated` | Status = `PENDING` |
| Inventory Reserved | Inventory Worker | `InventoryReserved` | Status = `INVENTORY_RESERVED` |
| Payment Attempt | Payment Worker | `PaymentSucceeded / Failed` | Status updated |
| Notification | Notification Worker | `OrderCompleted` | Final confirmation |
| Failure Handling | DLQ Handler | DLQ message | Status = `PAYMENT_FAILED` |

---

## Reliability & Failure Handling

- **SQS retries** with visibility timeouts
- **Dead Letter Queues (DLQ)** for failed messages
- Payment retries tracked with attempt counters
- Idempotent DynamoDB updates

This ensures **no message loss** and **graceful failure handling**.

---

## Observability & Monitoring

- Structured JSON logs
- Correlation IDs propagated across services
- Logs available in CloudWatch
- Designed to integrate with Splunk / centralized logging

This allows:
- Tracing a single order across microservices
- Faster incident resolution
- Support-team friendly debugging

---

## Project Structure

```text
event-driven-order-management-system/
├─ template.yaml
├─ README.md
├─ docs/
│  ├─ architecture.png
│  ├─ message-schemas.md
│  ├─ runbook.md
│  └─ troubleshooting.md
├─ events/
│  ├─ create-order.json
│  └─ sqs-inventory-reserved.json
└─ src/
   ├─ common/
   │  └─ logutil.py
   ├─ order_api/
   ├─ inventory_worker/
   ├─ payment_worker/
   ├─ notification_worker/
   └─ payment_failure_dlq/
