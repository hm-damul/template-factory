import os
import json
import logging
import traceback
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import time

# Try to import Gemini
try:
    # Check for new SDK first
    import google.genai as genai
    HAS_GEMINI = True
    GEMINI_VERSION = "new"
except ImportError as e:
    logger.warning(f"google.genai import failed: {e}")
    HAS_GEMINI = False
    GEMINI_VERSION = None

# Setup logging
logger = logging.getLogger("ErrorLearningSystem")

class ErrorLearningSystem:
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).resolve().parents[1]
        self.data_dir = self.project_root / "data"
        self.knowledge_base_path = self.data_dir / "error_knowledge_base.json"
        self.error_log_path = self.data_dir / "error_history.json"
        
        self.knowledge_base = self._load_json(self.knowledge_base_path, {"patterns": []})
        self.error_history = self._load_json(self.error_log_path, [])
        
        # Configure Gemini if available
        self._setup_ai()

    def _load_json(self, path: Path, default: Any) -> Any:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load {path}: {e}")
        return default

    def _save_json(self, path: Path, data: Any):
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save {path}: {e}")

    def _setup_ai(self):
        if not HAS_GEMINI:
            logger.warning("Google Generative AI not installed. AI features disabled.")
            return

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            # Try loading from secrets.json
            secrets_path = self.data_dir / "secrets.json"
            if secrets_path.exists():
                try:
                    with open(secrets_path, "r", encoding="utf-8") as f:
                        secrets = json.load(f)
                        api_key = secrets.get("GOOGLE_API_KEY") or secrets.get("GEMINI_API_KEY")
                except Exception:
                    pass
        
        if api_key:
            if GEMINI_VERSION == "new":
                try:
                    self.client = genai.Client(api_key=api_key)
                    self.model_name = "gemini-2.0-flash"
                    logger.info("AI Error Analysis System Initialized (Gemini 2.0 Flash - New SDK)")
                except Exception as e:
                    logger.error(f"Failed to initialize Gemini Client: {e}")
                    self.client = None
            else:
                logger.warning("Legacy Gemini SDK not supported. Please upgrade to google-genai.")
                self.model = None
        else:
            logger.warning("GOOGLE_API_KEY not found. AI features disabled.")
            self.model = None
            self.client = None

    def log_error(self, error: Exception, context: str = ""):
        """Log an error and return a unique error ID."""
        error_msg = str(error)
        tb = traceback.format_exc()
        
        error_entry = {
            "id": f"ERR-{int(time.time())}-{hash(error_msg) % 10000}",
            "timestamp": time.time(),
            "message": error_msg,
            "traceback": tb,
            "context": context,
            "resolved": False
        }
        
        self.error_history.append(error_entry)
        # Keep only last 100 errors
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-100:]
            
        self._save_json(self.error_log_path, self.error_history)
        logger.error(f"Error logged: {error_entry['id']} - {error_msg}")
        return error_entry

    def analyze_and_fix(self, error: Exception, context: str = "") -> Dict[str, Any]:
        """
        Analyze the error, check knowledge base, or ask AI for a fix.
        Returns a dict with 'action', 'details', 'confidence'.
        """
        entry = self.log_error(error, context)
        error_msg = str(error)
        
        # 1. Check Knowledge Base (Pattern Matching)
        for pattern in self.knowledge_base.get("patterns", []):
            if re.search(pattern["regex"], error_msg, re.IGNORECASE):
                logger.info(f"Known error pattern matched: {pattern['name']}")
                return {
                    "source": "knowledge_base",
                    "action": pattern.get("action", "manual"),
                    "details": pattern.get("solution", "No solution provided"),
                    "confidence": 1.0,
                    "pattern_id": pattern.get("id")
                }

        # 2. Ask AI (if enabled)
        ai_available = False
        if GEMINI_VERSION == "new" and getattr(self, 'client', None):
            ai_available = True
        elif GEMINI_VERSION == "legacy" and getattr(self, 'model', None):
            ai_available = True

        if ai_available:
            logger.info("Asking AI for error analysis...")
            try:
                prompt = f"""
                You are an expert Python debugger and system administrator.
                Analyze the following error and suggest a concrete fix.
                
                Context: {context}
                Error: {error_msg}
                Traceback:
                {entry['traceback']}
                
                Provide your response in JSON format with the following keys:
                - analysis: Brief explanation of the root cause.
                - solution: Step-by-step fix instructions.
                - code_fix: (Optional) Python code block to fix the issue if applicable.
                - command_fix: (Optional) Shell command to fix the issue (e.g., pip install).
                - confidence: Score between 0.0 and 1.0.
                """
                
                if GEMINI_VERSION == "new":
                    response = self.client.models.generate_content(model=self.model_name, contents=prompt)
                else:
                    # Legacy support removed
                    response = None

                if response:
                    try:
                        # Extract JSON from response
                        text = response.text
                        json_match = re.search(r'\{.*\}', text, re.DOTALL)
                        if json_match:
                            ai_solution = json.loads(json_match.group(0))
                            
                            # Learn from this new error
                            self.learn_error(error_msg, ai_solution)
                            
                            return {
                                "source": "ai",
                                "action": "suggested",
                                "details": ai_solution,
                                "confidence": ai_solution.get("confidence", 0.5)
                            }
                    except Exception as e:
                        logger.error(f"Failed to parse AI response: {e}")
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")

        return {
            "source": "unknown",
            "action": "manual_review_required",
            "details": "No known solution found and AI analysis failed.",
            "confidence": 0.0
        }

    def learn_error(self, error_msg: str, solution: Dict[str, Any]):
        """Add a new error pattern to the knowledge base."""
        # Simple regex generation (escape special chars, replace numbers with \d+)
        safe_msg = re.escape(error_msg)
        # Generalize: replace specific IDs/paths with wildcards
        # This is a naive implementation; could be improved with AI
        
        new_pattern = {
            "id": f"PAT-{int(time.time())}",
            "name": f"Error: {error_msg[:30]}...",
            "regex": safe_msg, # Use exact match for now to be safe
            "solution": solution.get("solution", ""),
            "action": "ai_suggested",
            "created_at": time.time()
        }
        
        self.knowledge_base["patterns"].append(new_pattern)
        self._save_json(self.knowledge_base_path, self.knowledge_base)
        logger.info(f"Learned new error pattern: {new_pattern['id']}")

    def apply_fix(self, fix_info: Dict[str, Any]) -> bool:
        """Attempt to apply the fix automatically."""
        details = fix_info.get("details", {})
        
        # 1. Command Fix
        if "command_fix" in details and details["command_fix"]:
            cmd = details["command_fix"]
            logger.info(f"Executing auto-fix command: {cmd}")
            try:
                import subprocess
                subprocess.run(cmd, shell=True, check=True)
                return True
            except Exception as e:
                logger.error(f"Auto-fix command failed: {e}")
                return False
                
        # 2. Code Fix (Too risky to apply blindly, just log for now)
        if "code_fix" in details and details["code_fix"]:
            logger.info(f"Code fix suggested: {details['code_fix']}")
            # TODO: Implement safe code application (e.g., creating a patch file)
            return False
            
        return False

# Singleton instance
_system = None

def get_error_system():
    global _system
    if _system is None:
        _system = ErrorLearningSystem()
    return _system
