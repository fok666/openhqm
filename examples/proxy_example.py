#!/usr/bin/env python3
"""
Example: Using OpenHQM in Reverse Proxy Mode

This example demonstrates how to configure and use OpenHQM
as a reverse proxy to forward requests to backend endpoints.
"""

import asyncio
import httpx
import json
from typing import Dict, Any


class OpenHQMClient:
    """Simple client for interacting with OpenHQM API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def submit_request(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str] = None,
        endpoint: str = None,
        timeout: int = 300,
    ) -> str:
        """
        Submit a request to OpenHQM.

        Args:
            payload: Request payload to forward to backend
            headers: Headers to forward to backend
            endpoint: Named endpoint to use
            timeout: Request timeout in seconds

        Returns:
            Correlation ID for tracking
        """
        request_data = {"payload": payload}

        if headers:
            request_data["headers"] = headers

        if endpoint or timeout != 300:
            request_data["metadata"] = {}
            if endpoint:
                request_data["metadata"]["endpoint"] = endpoint
            if timeout != 300:
                request_data["metadata"]["timeout"] = timeout

        response = await self.client.post(
            f"{self.base_url}/api/v1/submit",
            json=request_data,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        result = response.json()
        return result["correlation_id"]

    async def get_status(self, correlation_id: str) -> Dict[str, Any]:
        """Get request status."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/status/{correlation_id}"
        )
        response.raise_for_status()
        return response.json()

    async def get_response(self, correlation_id: str) -> Dict[str, Any]:
        """Get request response."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/response/{correlation_id}"
        )
        response.raise_for_status()
        return response.json()

    async def wait_for_completion(
        self, correlation_id: str, max_wait: int = 60, poll_interval: float = 1.0
    ) -> Dict[str, Any]:
        """
        Poll until request completes or times out.

        Args:
            correlation_id: Request correlation ID
            max_wait: Maximum wait time in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Final response
        """
        elapsed = 0
        while elapsed < max_wait:
            response = await self.get_response(correlation_id)
            status = response["status"]

            if status in ["COMPLETED", "FAILED"]:
                return response

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"Request did not complete within {max_wait} seconds")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def example_basic_request():
    """Example: Submit a basic request to default endpoint."""
    print("\n=== Example 1: Basic Request ===")

    client = OpenHQMClient()

    try:
        # Submit request
        print("Submitting request...")
        correlation_id = await client.submit_request(
            payload={"operation": "process", "data": "Hello World"}
        )
        print(f"Correlation ID: {correlation_id}")

        # Wait for completion
        print("Waiting for response...")
        response = await client.wait_for_completion(correlation_id)

        print(f"Status: {response['status']}")
        print(f"Status Code: {response.get('status_code')}")
        print(f"Result: {json.dumps(response['result'], indent=2)}")

    finally:
        await client.close()


async def example_with_headers():
    """Example: Forward headers to backend."""
    print("\n=== Example 2: Request with Headers ===")

    client = OpenHQMClient()

    try:
        # Submit request with custom headers
        print("Submitting request with headers...")
        correlation_id = await client.submit_request(
            payload={"action": "authenticate", "user_id": "12345"},
            headers={
                "Authorization": "Bearer client-token-xyz",
                "X-Request-ID": "req-abc-123",
                "X-Client-Version": "1.0.0",
            },
        )
        print(f"Correlation ID: {correlation_id}")

        # Wait for completion
        print("Waiting for response...")
        response = await client.wait_for_completion(correlation_id)

        print(f"Status: {response['status']}")
        print(f"Result: {json.dumps(response['result'], indent=2)}")
        print(f"Response Headers: {json.dumps(response.get('headers', {}), indent=2)}")

    finally:
        await client.close()


async def example_multiple_endpoints():
    """Example: Route requests to different endpoints."""
    print("\n=== Example 3: Multiple Endpoints ===")

    client = OpenHQMClient()

    try:
        # Request to user service
        print("Request to user-service...")
        user_id = await client.submit_request(
            payload={"action": "get_user", "user_id": "12345"},
            endpoint="user-service",
        )

        # Request to order service
        print("Request to order-service...")
        order_id = await client.submit_request(
            payload={"action": "create_order", "items": ["item1", "item2"]},
            endpoint="order-service",
        )

        # Request to analytics service
        print("Request to analytics-service...")
        analytics_id = await client.submit_request(
            payload={"event": "page_view", "page": "/home"},
            endpoint="analytics-service",
        )

        # Wait for all to complete
        print("\nWaiting for all responses...")
        user_response = await client.wait_for_completion(user_id)
        order_response = await client.wait_for_completion(order_id)
        analytics_response = await client.wait_for_completion(analytics_id)

        print("\n--- User Service Response ---")
        print(f"Status: {user_response['status']}")
        print(f"Result: {json.dumps(user_response['result'], indent=2)}")

        print("\n--- Order Service Response ---")
        print(f"Status: {order_response['status']}")
        print(f"Result: {json.dumps(order_response['result'], indent=2)}")

        print("\n--- Analytics Service Response ---")
        print(f"Status: {analytics_response['status']}")
        print(f"Result: {json.dumps(analytics_response['result'], indent=2)}")

    finally:
        await client.close()


async def example_batch_requests():
    """Example: Submit multiple requests in batch."""
    print("\n=== Example 4: Batch Requests ===")

    client = OpenHQMClient()

    try:
        # Submit batch of requests
        print("Submitting batch of 10 requests...")
        correlation_ids = []

        for i in range(10):
            correlation_id = await client.submit_request(
                payload={"batch_id": i, "data": f"Request {i}"}
            )
            correlation_ids.append(correlation_id)
            print(f"  [{i+1}/10] Submitted: {correlation_id}")

        # Wait for all to complete
        print("\nWaiting for all responses...")
        results = []
        for i, correlation_id in enumerate(correlation_ids):
            response = await client.wait_for_completion(correlation_id, max_wait=120)
            results.append(response)
            print(f"  [{i+1}/10] Completed: {response['status']}")

        # Summary
        completed = sum(1 for r in results if r["status"] == "COMPLETED")
        failed = sum(1 for r in results if r["status"] == "FAILED")

        print(f"\nBatch Summary:")
        print(f"  Total: {len(results)}")
        print(f"  Completed: {completed}")
        print(f"  Failed: {failed}")

    finally:
        await client.close()


async def main():
    """Run all examples."""
    print("OpenHQM Reverse Proxy Mode Examples")
    print("=" * 60)

    try:
        await example_basic_request()
        await example_with_headers()
        # Uncomment to run additional examples:
        # await example_multiple_endpoints()
        # await example_batch_requests()

    except httpx.HTTPError as e:
        print(f"\nHTTP Error: {e}")
        print("Make sure OpenHQM is running on http://localhost:8000")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    asyncio.run(main())
