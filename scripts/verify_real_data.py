import sqlite3

conn = sqlite3.connect("storage/agent_kitkat.db")
print("=== REAL DISCOVERED OPPORTUNITIES IN DATABASE ===")
for r in conn.execute("SELECT title, company, work_mode, source, url FROM jobs").fetchall():
    print(f"- {r[0]} | {r[1]} ({r[2]}) [{r[3]}] -> {r[4]}")

print("\n=== PREPARED APPLICATIONS & COVER LETTERS ===")
for r in conn.execute("SELECT d.id, j.title, j.company, substr(d.cover_letter, 1, 160) FROM application_drafts d JOIN jobs j ON d.job_id=j.id").fetchall():
    print(f"Draft {r[0][:8]} for {r[1]} at {r[2]}:")
    print(f"  \"{r[3]}...\"\n")

print("=== STATS ===")
for t in ["jobs", "eligibility_results", "match_results", "application_drafts", "approval_requests", "daily_reports"]:
    cnt = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"{t}: {cnt}")
