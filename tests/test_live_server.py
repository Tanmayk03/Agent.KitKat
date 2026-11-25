"""
Live Server HTTP Socket Test for Agent KitKat.
Spawns a real Uvicorn HTTP server listening on 127.0.0.1:8000
and executes real network requests over the TCP socket.
"""

import os
import sys
import asyncio
import httpx
import uvicorn

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests._isolation  # noqa: E402,F401  -- throwaway DB; never touches your real data

from backend.main import app


async def run_live_server_test():
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=8000,
        log_level="warning"
    )
    server = uvicorn.Server(config)

    # Start server in background task
    server_task = asyncio.create_task(server.serve())

    # Wait for server to be ready
    while not server.started:
        await asyncio.sleep(0.1)

    print("🚀 Live Uvicorn server is up and listening on http://127.0.0.1:8000")

    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0, trust_env=False) as client:
            # 1. Test Root
            print("\n--> [Live HTTP GET /]")
            res = await client.get("/")
            print(f"Status: {res.status_code}")
            print(f"Payload: {res.json()}")
            assert res.status_code == 200

            # 2. Test Health Check over TCP
            print("\n--> [Live HTTP GET /api/health]")
            res = await client.get("/api/health")
            print(f"Status: {res.status_code}")
            health = res.json()
            print(f"Payload: {health}")
            assert res.status_code == 200
            assert health["status"] == "healthy"
            assert health["ollama"]["status"] == "connected"

            # 3. Test AI Generation over TCP
            print("\n--> [Live HTTP POST /api/ai/test]")
            test_prompt = {
                "prompt": "Say 'Agent KitKat is live and operational!' in one sentence.",
                "temperature": 0.2
            }
            res = await client.post("/api/ai/test", json=test_prompt)
            print(f"Status: {res.status_code}")
            ai_data = res.json()
            print(f"AI Response: {ai_data['response']}")
            print(f"Duration: {ai_data['duration_ms']} ms")
            assert res.status_code == 200
            assert ai_data["success"] is True

            print("\n🎉 Live TCP Socket Server Test PASSED completely!")

    finally:
        print("\nStopping live server...")
        server.should_exit = True
        await server_task
        print("Server stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(run_live_server_test())
