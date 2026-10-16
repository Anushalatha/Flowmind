import asyncio
import json
import logging
from app.orchestrator.engine import engine
from app.persistence.database import init_db

logging.basicConfig(level=logging.INFO)
init_db()

async def run_evaluation():
    with open("evaluation/datasets/basic.json") as f:
        datasets = json.load(f)
        
    results = []
    
    for case in datasets:
        logging.info(f"Running evaluation: {case['id']}")
        try:
            workflow_id = engine.new_workflow(case["request"])
            await engine.run_workflow(workflow_id)
            state = engine.active_workflows[workflow_id]
            status = state.status.value
            
            success = status == case.get("expected_status", "completed")
            
            results.append({
                "id": case["id"],
                "success": success,
                "status": status,
                "errors": state.errors
            })
            logging.info(f"Result for {case['id']}: {'PASS' if success else 'FAIL'}")
        except Exception as e:
            logging.error(f"Error evaluating {case['id']}: {e}")
            results.append({"id": case["id"], "success": False, "error": str(e)})
            
    import os
    os.makedirs("evaluation/reports", exist_ok=True)
    with open("evaluation/reports/report.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_evaluation())
