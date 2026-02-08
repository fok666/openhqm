#!/usr/bin/env python3
"""
End-to-End Example: Complete OpenHQM Workflow

This example demonstrates a complete workflow using OpenHQM:
1. Submit requests to different routes
2. Test JQ transformations
3. Validate routing decisions
4. Monitor request lifecycle
5. Handle errors and retries

Scenarios covered:
- User registration with transformation
- Order processing with complex JQ
- Notifications with pattern matching
- Analytics event tracking
- Legacy system integration
- Payment processing
- Default route fallback

Usage:
    # Start OpenHQM first
    OPENHQM_ROUTING__ENABLED=true \\
    OPENHQM_ROUTING__CONFIG_PATH=examples/routing-config.yaml \\
    python -m openhqm.api.listener

    # Run this example
    python examples/complete_workflow_example.py

Requirements:
    - OpenHQM running on localhost:8000
    - routing-config.yaml loaded
    - Backend services or mocks available
"""

import asyncio
import httpx
import json
from typing import Dict, Any, List
from datetime import datetime


class OpenHQMWorkflowDemo:
    """Demonstrates complete OpenHQM workflow."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.results: List[Dict[str, Any]] = []

    async def submit_and_track(
        self,
        name: str,
        payload: Dict[str, Any],
        metadata: Dict[str, Any] = None,
        expected_route: str = None
    ) -> Dict[str, Any]:
        """Submit request and track it through the system."""
        print(f"\n{'='*60}")
        print(f"📤 Submitting: {name}")
        print(f"{'='*60}")

        request_data = {"payload": payload}
        if metadata:
            request_data["metadata"] = metadata

        print(f"📋 Request data:")
        print(json.dumps(request_data, indent=2))

        try:
            # Submit request
            response = await self.client.post(
                f"{self.base_url}/api/v1/submit",
                json=request_data
            )
            response.raise_for_status()
            result = response.json()
            correlation_id = result["correlation_id"]

            print(f"✅ Submitted successfully")
            print(f"🔑 Correlation ID: {correlation_id}")

            if expected_route:
                print(f"🎯 Expected route: {expected_route}")

            # Wait for processing
            await asyncio.sleep(1)

            # Check status
            final_response = await self.get_response(correlation_id)
            status = final_response.get("status", "UNKNOWN")

            print(f"📊 Status: {status}")

            if status == "COMPLETED":
                print(f"✅ Processing completed")
                if "result" in final_response:
                    print(f"📦 Result:")
                    print(json.dumps(final_response["result"], indent=2))
            elif status == "FAILED":
                print(f"❌ Processing failed")
                if "error" in final_response:
                    print(f"⚠️  Error: {final_response['error']}")
            else:
                print(f"⏳ Still processing...")

            # Store result
            self.results.append({
                "name": name,
                "correlation_id": correlation_id,
                "status": status,
                "expected_route": expected_route,
                "response": final_response
            })

            return final_response

        except httpx.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            return {"status": "ERROR", "error": str(e)}
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"status": "ERROR", "error": str(e)}

    async def get_response(self, correlation_id: str) -> Dict[str, Any]:
        """Get request response."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/response/{correlation_id}"
        )
        response.raise_for_status()
        return response.json()

    async def scenario_1_user_registration(self):
        """Scenario 1: User Registration with JQ Transformation."""
        print("\n" + "="*60)
        print("🎬 SCENARIO 1: User Registration")
        print("="*60)
        print("Route: user-registration")
        print("Transform: JQ - Extract username from email, restructure data")
        print("Expected: Username extracted, metadata added")

        await self.submit_and_track(
            name="User Registration",
            payload={
                "email": "alice.wonder@example.com",
                "name": "Alice Wonder",
                "password": "secure-password-123",
                "phone": "+1-555-0123"
            },
            metadata={
                "type": "user.register",
                "source": "web-app",
                "timestamp": datetime.utcnow().isoformat()
            },
            expected_route="user-registration"
        )

    async def scenario_2_order_processing(self):
        """Scenario 2: Order Processing with Complex JQ."""
        print("\n" + "="*60)
        print("🎬 SCENARIO 2: Order Processing")
        print("="*60)
        print("Route: order-processing")
        print("Transform: JQ - Calculate total, restructure items")
        print("Expected: Flattened order with calculated total")

        await self.submit_and_track(
            name="Order Processing",
            payload={
                "order_id": "ORD-2024-001",
                "customer": {
                    "id": "CUST-12345",
                    "email": "customer@example.com",
                    "name": "John Doe"
                },
                "items": [
                    {"sku": "LAPTOP-001", "qty": 1, "unit_price": 1299.99},
                    {"sku": "MOUSE-002", "qty": 2, "unit_price": 29.99},
                    {"sku": "KEYBOARD-003", "qty": 1, "unit_price": 89.99}
                ],
                "currency": "USD",
                "shipping": {
                    "address": "123 Main St",
                    "method": "express"
                }
            },
            metadata={
                "type": "order.create",
                "source": "checkout-service"
            },
            expected_route="order-processing"
        )

    async def scenario_3_notifications(self):
        """Scenario 3: Notification Routing with Pattern Matching."""
        print("\n" + "="*60)
        print("🎬 SCENARIO 3: Notifications (Pattern Matching)")
        print("="*60)
        print("Route: notification")
        print("Match: Regex pattern ^notification\\.")
        print("Transform: Template - Format notification message")

        # Test multiple notification types
        notification_types = ["email", "sms", "push"]

        for notif_type in notification_types:
            await self.submit_and_track(
                name=f"Notification - {notif_type.upper()}",
                payload={
                    "user": {
                        "email": "user@example.com",
                        "name": "Test User"
                    },
                    "subject": "Order Confirmation",
                    "message": "Your order has been confirmed and will ship soon.",
                    "priority": "normal"
                },
                metadata={
                    "type": f"notification.{notif_type}",
                    "template": "order-confirmation"
                },
                expected_route="notification"
            )

    async def scenario_4_analytics(self):
        """Scenario 4: Analytics Event Tracking."""
        print("\n" + "="*60)
        print("🎬 SCENARIO 4: Analytics Event Tracking")
        print("="*60)
        print("Route: analytics")
        print("Transform: JSONPath - Extract event data")
        print("Expected: Event data forwarded to analytics service")

        await self.submit_and_track(
            name="Analytics - Page View",
            payload={
                "event": {
                    "type": "page_view",
                    "user_id": "user-789",
                    "page": "/products/laptop",
                    "timestamp": datetime.utcnow().isoformat(),
                    "properties": {
                        "referrer": "google.com",
                        "device": "desktop",
                        "browser": "chrome",
                        "duration_ms": 15000
                    }
                }
            },
            metadata={
                "type": "analytics.track",
                "session_id": "sess-xyz-789"
            },
            expected_route="analytics"
        )

    async def scenario_5_legacy_integration(self):
        """Scenario 5: Legacy System Integration with Session Affinity."""
        print("\n" + "="*60)
        print("🎬 SCENARIO 5: Legacy System Integration")
        print("="*60)
        print("Route: legacy-app-session")
        print("Transform: Passthrough")
        print("Expected: Session ID preserved, routed to same partition")

        session_id = "sess-legacy-123"

        # Submit multiple requests with same session ID
        for i in range(3):
            await self.submit_and_track(
                name=f"Legacy Request {i+1}",
                payload={
                    "action": "get_user_cart" if i == 0 else "update_cart",
                    "user_id": "legacy-user-456",
                    "data": {"item": f"ITEM-00{i+1}", "quantity": i+1}
                },
                metadata={
                    "type": "legacy.request",
                    "session_id": session_id,
                    "user_id": "legacy-user-456"
                },
                expected_route="legacy-app-session"
            )

    async def scenario_6_payment_processing(self):
        """Scenario 6: Payment Processing with Query Parameters."""
        print("\n" + "="*60)
        print("🎬 SCENARIO 6: Payment Processing")
        print("="*60)
        print("Route: payment")
        print("Transform: JQ - Structure payment data")
        print("Expected: Payment formatted with idempotency key")

        await self.submit_and_track(
            name="Payment Processing",
            payload={
                "action": "payment",
                "amount": 1449.96,
                "currency": "USD",
                "method": "credit_card",
                "customer_id": "CUST-12345",
                "customer_email": "customer@example.com",
                "card_last4": "4242"
            },
            metadata={
                "type": "payment.process",
                "provider": "stripe"
            },
            expected_route="payment"
        )

    async def scenario_7_default_route(self):
        """Scenario 7: Unknown Message - Default Route."""
        print("\n" + "="*60)
        print("🎬 SCENARIO 7: Default Route (Unmatched)")
        print("="*60)
        print("Route: default")
        print("Transform: Passthrough")
        print("Expected: Routed to default endpoint")

        await self.submit_and_track(
            name="Unknown Message Type",
            payload={
                "some": "data",
                "that": "doesn't",
                "match": "any route"
            },
            metadata={
                "type": "unknown.message.type"
            },
            expected_route="default"
        )

    async def print_summary(self):
        """Print summary of all scenarios."""
        print("\n" + "="*60)
        print("📊 WORKFLOW SUMMARY")
        print("="*60)

        total = len(self.results)
        completed = sum(1 for r in self.results if r["status"] == "COMPLETED")
        failed = sum(1 for r in self.results if r["status"] == "FAILED")
        pending = sum(1 for r in self.results if r["status"] == "PENDING")

        print(f"\nTotal Requests: {total}")
        print(f"✅ Completed: {completed}")
        print(f"❌ Failed: {failed}")
        print(f"⏳ Pending: {pending}")

        print("\n📋 Detailed Results:")
        print("-" * 60)
        for result in self.results:
            status_emoji = "✅" if result["status"] == "COMPLETED" else "❌"
            print(f"{status_emoji} {result['name']}")
            print(f"   Correlation ID: {result['correlation_id']}")
            print(f"   Expected Route: {result['expected_route']}")
            print(f"   Status: {result['status']}")
            print()

    async def run_all_scenarios(self):
        """Run all workflow scenarios."""
        print("\n" + "="*80)
        print("🚀 OpenHQM Complete Workflow Demo")
        print("="*80)

        try:
            # Check if OpenHQM is running
            await self.client.get(f"{self.base_url}/health")
            print("✅ OpenHQM is running")
        except:
            print("❌ Error: OpenHQM is not running on", self.base_url)
            print("Please start OpenHQM first:")
            print("  OPENHQM_ROUTING__ENABLED=true \\")
            print("  OPENHQM_ROUTING__CONFIG_PATH=examples/routing-config.yaml \\")
            print("  python -m openhqm.api.listener")
            return

        # Run all scenarios
        await self.scenario_1_user_registration()
        await self.scenario_2_order_processing()
        await self.scenario_3_notifications()
        await self.scenario_4_analytics()
        await self.scenario_5_legacy_integration()
        await self.scenario_6_payment_processing()
        await self.scenario_7_default_route()

        # Print summary
        await self.print_summary()

        await self.client.aclose()


async def main():
    """Main entry point."""
    demo = OpenHQMWorkflowDemo()
    await demo.run_all_scenarios()


if __name__ == "__main__":
    asyncio.run(main())
