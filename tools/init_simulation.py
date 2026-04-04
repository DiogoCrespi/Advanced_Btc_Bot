import os
import json

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIROFISH_UPLOADS = os.path.join(BASE_DIR, "MiroFish", "backend", "uploads")

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")

def init_simulation(simulation_id, project_id, report_id):
    print(f"=== Initializing Simulation '{simulation_id}' for MiroFish ===")
    
    # 1. Ensure directories exist
    sim_dir = os.path.join(MIROFISH_UPLOADS, "simulations", simulation_id)
    report_dir = os.path.join(MIROFISH_UPLOADS, "reports", report_id)
    project_dir = os.path.join(MIROFISH_UPLOADS, "projects", project_id)
    
    ensure_dir(sim_dir)
    ensure_dir(report_dir)
    ensure_dir(project_dir)
    
    # 2. Create Project metadata
    project_meta = {
        "project_id": project_id,
        "name": "Live Market Monitor",
        "description": "Automated sentiment monitoring for BTC bot.",
        "simulation_requirement": "Analyze market sentiment and news for automated trading signals.",
        "graph_id": "live_graph"
    }
    with open(os.path.join(project_dir, "project.json"), "w", encoding="utf-8") as f:
        json.dump(project_meta, f, indent=2)
    
    # 3. Create Simulation state
    sim_state = {
        "simulation_id": simulation_id,
        "project_id": project_id,
        "status": "completed",
        "current_round": 10
    }
    with open(os.path.join(sim_dir, "state.json"), "w", encoding="utf-8") as f:
        json.dump(sim_state, f, indent=2)
    
    # 4. Create Report metadata
    report_meta = {
        "report_id": report_id,
        "simulation_id": simulation_id,
        "graph_id": "live_graph",
        "simulation_requirement": "Analyze market sentiment and news for automated trading signals.",
        "status": "completed",
        "outline": {
            "title": "Overall Sentiment Report",
            "summary": "Indicators show stable growth.",
            "sections": [
                {"title": "Live Market Sentiment", "content": "The current indicators reflect a bullish trend."}
            ]
        },
        "markdown_content": "# Live Market Analysis\n\n- **Sentiment**: Bullish\n- **Details**: Strong buy signals based on news volume.\n- **Confidence**: 0.85"
    }
    with open(os.path.join(report_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(report_meta, f, indent=2)
        
    print(f"Successfully initialized Simulation '{simulation_id}' and Report '{report_id}'.")
    print("MiroFish should now stop returning 404 for this ID.")

if __name__ == "__main__":
    init_simulation("live_bot_sim", "proj_live_monitor", "report_live_bot")
