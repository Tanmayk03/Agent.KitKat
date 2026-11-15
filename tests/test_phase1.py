"""
Phase 1 Verification Tests for Agent KitKat Backend.
Tests:
1. Root endpoint (GET /)
2. Health check endpoint (GET /api/health)
3. AI generation test endpoint (POST /api/ai/test)
4. AI generation validation (empty prompt error handling)
"""

import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from backend.main import app


async def run_tests():
    print("==================================================")
    print("🚀 Starting Agent KitKat Phase 1 Verification Tests")
    print("==================================================")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Test Root Endpoint
        print("\n[Test 1] Testing Root Endpoint (GET /)...")
        res = await client.get("/")
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert res.json().get("app") == "Agent KitKat"
        print("✅ Test 1 Passed: Root endpoint is functioning correctly.")

        # 2. Test Health Check Endpoint
        print("\n[Test 2] Testing Health Check Endpoint (GET /api/health)...")
        res = await client.get("/api/health")
        print(f"Status Code: {res.status_code}")
        health_data = res.json()
        print(f"Response: {health_data}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert health_data.get("status") in ["healthy", "degraded"], f"Unexpected status: {health_data.get('status')}"
        assert health_data["ollama"]["status"] == "connected", "Ollama is not connected"
        assert health_data["ollama"]["model_available"] is True, "Target model qwen2.5:1.5b not found in Ollama"
        print(f"✅ Test 2 Passed: Ollama connected ({health_data['ollama']['latency_ms']} ms), target model ready.")

        # 3. Test AI Generation Endpoint
        print("\n[Test 3] Testing AI Generation Endpoint (POST /api/ai/test)...")
        test_payload = {
            "prompt": "Introduce yourself in one brief sentence as Agent KitKat.",
            "temperature": 0.5
        }
        res = await client.post("/api/ai/test", json=test_payload)
        print(f"Status Code: {res.status_code}")
        ai_data = res.json()
        print(f"Model: {ai_data.get('model')}")
        print(f"Response Duration: {ai_data.get('duration_ms')} ms")
        print(f"AI Response: {ai_data.get('response')}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert ai_data.get("success") is True
        assert len(ai_data.get("response", "")) > 0
        print("✅ Test 3 Passed: Qwen2.5 1.5B generated response successfully via local Ollama.")

        # 4. Test Validation Error Handling
        print("\n[Test 4] Testing AI Generation Validation Error Handling (empty prompt)...")
        bad_payload = {
            "prompt": ""
        }
        res = await client.post("/api/ai/test", json=bad_payload)
        print(f"Status Code: {res.status_code} (Expected 422)")
        assert res.status_code == 422, f"Expected 422, got {res.status_code}"
        print("✅ Test 4 Passed: Empty prompt correctly rejected by Pydantic validation.")

    print("\n==================================================")
    print("🎉 ALL PHASE 1 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_tests())
