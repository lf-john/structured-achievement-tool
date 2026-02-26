import subprocess, os, shlex, json

class LogicCore:
    def __init__(self, project_path):
        self.project_path = project_path
        self.config_path = os.path.join(project_path, "config.json")
        self.config = self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                return json.load(f)
        return {"phase_models": {}}

    def generate_text(self, prompt, phase="GENERAL", system_prompt=None):
        # Determine the best model for this phase
        model = self.config.get("phase_models", {}).get(phase, self.config.get("default_primary", "sonnet"))
        backup_model = self.config.get("default_backup", "glm")

        try:
            return self._invoke_cli(prompt, model, system_prompt)
        except Exception as e:
            if "quota" in str(e).lower() or "limit" in str(e).lower() or "failed" in str(e).lower():
                print(f"Primary model {model} failed or limited. Falling back to {backup_model}...")
                return self._invoke_cli(prompt, backup_model, system_prompt)
            raise e

    def _invoke_cli(self, prompt, model, system_prompt):
        c, C = None, self.project_path
        try:
            command_str = f"claude -p {shlex.quote(prompt)} --model {model} --dangerously-skip-permissions"
            if system_prompt:
                t = os.path.join(self.project_path, ".tmp_sdt"); os.makedirs(t, exist_ok=True)
                c = os.path.join(t, "CLAUDE.md"); open(c, "w").write(system_prompt); C=t
            
            r = subprocess.run(command_str, shell=True, executable='/bin/bash', cwd=C, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                raise RuntimeError(f"CLI failed: {r.stderr}")
            return r.stdout
        finally:
            if c and os.path.exists(c):
                os.remove(c)
