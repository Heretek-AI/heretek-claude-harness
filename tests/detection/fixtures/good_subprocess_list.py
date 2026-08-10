import subprocess


def run(cmd_list):
    return subprocess.run(cmd_list, capture_output=True, text=True, timeout=10).stdout
