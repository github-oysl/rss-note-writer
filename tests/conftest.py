import sys
import os


def pytest_configure(config):
    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')
    src_path = os.path.abspath(src_path)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

