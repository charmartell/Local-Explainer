"""Keep packaging intermediates in the explicit workspace scratch directory."""
import os
from pathlib import Path
from setuptools import setup
from setuptools.command.egg_info import egg_info
from setuptools.command.build_py import build_py

import json
repo = Path(__file__).resolve().parent
local_file = repo/'.local-paths.json'
local = json.loads(local_file.read_text(encoding='utf-8-sig')) if local_file.exists() else {}
root=Path(os.environ.get('LOCAL_EXPLAINER_SCRATCH',local.get('scratch',str(repo/'data'/'scratch'))))/'packaging'
root.mkdir(parents=True,exist_ok=True)

class ScratchEggInfo(egg_info):
    def initialize_options(self):
        super().initialize_options()
        self.egg_base=str(root)

class ScratchBuildPy(build_py):
    def finalize_options(self):
        super().finalize_options()
        self.build_lib=str(root/'lib')

setup(cmdclass={'egg_info':ScratchEggInfo,'build_py':ScratchBuildPy})
