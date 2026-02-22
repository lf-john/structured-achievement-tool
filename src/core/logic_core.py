import subprocess, os, shlex
class LogicCore:
    def __init__(self, p): self.p = p
    def generate_text(self, prompt, model, system_prompt=None):
        c, C = None, self.p
        try:
            q, s = shlex.quote(prompt), f"claude -p {shlex.quote(prompt)} --model {model} --dangerously-skip-permissions"
            if system_prompt:
                t = os.path.join(self.p, ".tmp_sdt"); os.makedirs(t, exist_ok=True)
                c = os.path.join(t, "CLAUDE.md"); open(c, "w").write(system_prompt); C=t
            r = subprocess.run(s, shell=True, executable='/bin/bash', cwd=C, capture_output=True, text=True, timeout=600, env=os.environ.copy())
            if r.returncode != 0: raise RuntimeError(f"CLI failed: {r.stderr}")
            return r.stdout
        finally:
            if c and os.path.exists(c): os.remove(c); [os.rmdir(os.path.dirname(c)) for _ in [0] if not os.listdir(os.path.dirname(c))]
