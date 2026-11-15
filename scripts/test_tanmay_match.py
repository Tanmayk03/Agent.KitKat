import os
import sys
import asyncio
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.main import app

async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        job_payload = {
            'text': 'HyperGrowth is seeking a Full Stack Developer Intern. Requirements: B.Tech Computer Science graduating 2027. CGPA 7.5+. Required skills: React, Node.js, Express.js, MongoDB, REST APIs. Location: Remote, India.',
            'title': 'Full Stack Developer Intern',
            'company': 'HyperGrowth'
        }
        res = await client.post('/api/jobs/analyze-text', json=job_payload)
        job_data = res.json()

        eval_res = await client.post(f'/api/matching/evaluate/{job_data["id"]}')
        eval_data = eval_res.json()

        print("\n==================================================")
        print("🎯 TANMAY KAPOOR RESUME MATCH TEST")
        print("==================================================")
        print(f"Role:           {job_data['extracted']['job_title']} at {job_data['extracted']['company_name']}")
        print(f"Eligibility:    {eval_data['eligibility']['overall_status']}")
        print(f"Match Score:    {eval_data['overall_score']}%")
        print(f"Recommendation: {eval_data['recommendation']}")
        print(f"Matching Skills: {', '.join(eval_data['matching_skills'])}")
        print(f"Score Breakdown: {eval_data['category_scores']}")
        print("==================================================")

if __name__ == '__main__':
    asyncio.run(main())
