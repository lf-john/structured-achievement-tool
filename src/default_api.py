# This is a dummy file to allow patching of 'default_api' in tests.
# The actual default_api is provided by the Gemini CLI at runtime.

# Define dummy functions that will be mocked by pytest in conftest.py
def run_shell_command(*args, **kwargs):
    pass

def read_file(*args, **kwargs):
    pass

def write_file(*args, **kwargs):
    pass

def replace(*args, **kwargs):
    pass

def list_directory(*args, **kwargs):
    pass

def grep_search(*args, **kwargs):
    pass

def glob(*args, **kwargs):
    pass

def web_fetch(*args, **kwargs):
    pass

def save_memory(*args, **kwargs):
    pass

def google_web_search(*args, **kwargs):
    pass

def write_todos(*args, **kwargs):
    pass

def codebase_investigator(*args, **kwargs):
    pass

def cli_help(*args, **kwargs):
    pass

def activate_skill(*args, **kwargs):
    pass

