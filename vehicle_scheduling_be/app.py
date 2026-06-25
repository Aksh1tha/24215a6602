import os
import requests
from flask import Flask, jsonify
from dotenv import load_dotenv

# Load credentials from .env file
load_dotenv()

app = Flask(__name__)

REMOTE_SERVER_URL = "http://4.224.186.213/evaluation-service"
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# =====================================================================
# AUTHENTICATION: Self-healing token refresh
# =====================================================================
def get_fresh_token():
    try:
        response = requests.post(f"{REMOTE_SERVER_URL}/auth", json={
            "clientID": CLIENT_ID,
            "clientSecret": CLIENT_SECRET
        }, timeout=6)
        if response.status_code == 200:
            return f"Bearer {response.json().get('token')}"
    except Exception as e:
        print(f"Auth error: {e}")
    return None

# =====================================================================
# OPTIMIZATION: 0/1 Knapsack Algorithm
# =====================================================================
def compute_best_allocation(job_list, available_limit):
    total_jobs = len(job_list)
    matrix = [[0 for _ in range(available_limit + 1)] for _ in range(total_jobs + 1)]
    
    for i in range(1, total_jobs + 1):
        job = job_list[i-1]
        cost = int(job.get("duration", job.get("Duration", 0)))
        gain = int(job.get("impact", job.get("Impact", 0)))
        for w in range(available_limit + 1):
            if cost <= w:
                matrix[i][w] = max(gain + matrix[i-1][w-cost], matrix[i-1][w])
            else:
                matrix[i][w] = matrix[i-1][w]
    
    # Backtrack to find selected tasks
    selected = []
    w = available_limit
    for i in range(total_jobs, 0, -1):
        if matrix[i][w] != matrix[i-1][w]:
            selected.append(job_list[i-1])
            w -= int(job_list[i-1].get("duration", job_list[i-1].get("Duration", 0)))
    
    return selected[::-1], matrix[total_jobs][available_limit]

# =====================================================================
# ROUTES
# =====================================================================
@app.route('/depots/<depot_id>', methods=['GET'])
def get_schedule(depot_id):
    token = get_fresh_token()
    if not token:
        return jsonify({"status": "Authentication failed"}), 401
    
    headers = {"Authorization": token}
    d_res = requests.get(f"{REMOTE_SERVER_URL}/depots", headers=headers, timeout=6)
    v_res = requests.get(f"{REMOTE_SERVER_URL}/vehicles", headers=headers, timeout=6)
    
    if d_res.status_code != 200 or v_res.status_code != 200:
        return jsonify({"status": "Upstream data fetch failed"}), 500

    depots = d_res.json().get("depots", [])
    # Matches using 'id' or 'ID' or 'depotId' to be safe
    matched = next((d for d in depots if str(d.get("id", d.get("ID", d.get("depotId", "")))) == str(depot_id)), None)
    
    if not matched:
        return jsonify({"status": "Depot not found"}), 404

    hours = int(matched.get("mechanicHours", matched.get("MechanicHours", 0)))
    tasks = v_res.json().get("vehicles", [])
    
    scheduled, impact = compute_best_allocation(tasks, hours)
    
    return jsonify({
        "depotID": depot_id,
        "totalOptimizedImpact": impact,
        "scheduledTasks": scheduled
    }), 200

if __name__ == '__main__':
    app.run(debug=True)