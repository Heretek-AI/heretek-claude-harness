import os


def run(cmd):
    return os.popen(cmd).read()  # forbidden: os.popen is older API
