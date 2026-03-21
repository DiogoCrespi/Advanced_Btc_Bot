import requests
import json
import logging
import os
from typing import Dict, Any, Optional, List

logger = logging.getLogger('mirofish.client')

class MiroFishClient:
    """
    Client for interacting with the MiroFish REST API.
    """
    def __init__(self, base_url: Optional[str] = None):
        # Fallback order: Argument -> Environment Var -> Default Localhost
        self.base_url = base_url or os.getenv("MIROFISH_API_URL", "http://localhost:5000/api")
        self.timeout = 30

    def create_simulation(self, project_id: str, graph_id: Optional[str] = None) -> Dict[str, Any]:
        """Creates a new simulation."""
        url = f"{self.base_url}/simulation/create"
        payload = {
            "project_id": project_id,
            "graph_id": graph_id
        }
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error creating simulation: {e}")
            return {"success": False, "error": str(e)}

    def prepare_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Prepares a simulation (async)."""
        url = f"{self.base_url}/simulation/prepare"
        payload = {"simulation_id": simulation_id}
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error preparing simulation: {e}")
            return {"success": False, "error": str(e)}

    def start_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Starts a prepared simulation."""
        url = f"{self.base_url}/simulation/start"
        payload = {"simulation_id": simulation_id}
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error starting simulation: {e}")
            return {"success": False, "error": str(e)}

    def get_report_by_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Retrieves an existing report for a simulation."""
        url = f"{self.base_url}/report/by-simulation/{simulation_id}"
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 404:
                return {"success": False, "error": "Report not found", "has_report": False}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting report: {e}")
            return {"success": False, "error": str(e)}

    def generate_report(self, simulation_id: str) -> Dict[str, Any]:
        """Trigger report generation (async)."""
        url = f"{self.base_url}/report/generate"
        payload = {"simulation_id": simulation_id}
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return {"success": False, "error": str(e)}

    def get_sentiment_summary(self, simulation_id: str) -> Dict[str, Any]:
        """
        Helper to get a condensed sentiment summary from a report.
        Parses the markdown content for 'Bullish' or 'Bearish' keywords.
        """
        report_data = self.get_report_by_simulation(simulation_id)
        if not report_data.get("success") or not report_data.get("has_report"):
            return {"sentiment": "Neutral", "confidence": 0}

        content = report_data.get("data", {}).get("markdown_content", "").lower()
        
        # Simple heuristic parsing
        bullish_count = content.count("bullish") + content.count("positivo") + content.count("alta")
        bearish_count = content.count("bearish") + content.count("negativo") + content.count("baixa")
        
        if bullish_count > bearish_count:
            return {"sentiment": "Bullish", "confidence": min(1.0, bullish_count / 10)}
        elif bearish_count > bullish_count:
            return {"sentiment": "Bearish", "confidence": min(1.0, bearish_count / 10)}
        else:
            return {"sentiment": "Neutral", "confidence": 0.5}
