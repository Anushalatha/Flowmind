import sqlite3
import json

conn = sqlite3.connect('flowmind.db')
cursor = conn.cursor()

cursor.execute('SELECT id, status, state_json FROM workflows ORDER BY created_at DESC LIMIT 5')
rows = cursor.fetchall()

print('Workflow status comparison:')
for r in rows:
    print(f'ID: {r[0][:8]}...')
    print(f'  DB status: {r[1]}')
    state = json.loads(r[2])
    print(f'  State status: {state.get("status")}')
    print()

conn.close()
