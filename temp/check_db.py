import sqlite3
conn = sqlite3.connect('DB/adaptiq.db')
cur = conn.cursor()
cur.execute("SELECT career_timeline FROM employees WHERE id='emp_479a9fac'")
print("CAREER TIMELINE RAW JSON:")
print(cur.fetchone()[0])
