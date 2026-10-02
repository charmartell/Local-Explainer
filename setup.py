"""Keep packaging intermediates in the explicit workspace scratch directory."""
import os
from pathlib import Path
from setuptools import setup
from setuptools.command.egg_info import egg_info
from setuptools.command.build_py import build_py

root=Path(os.environ.get('LOCAL_EXPLAINER_SCRATCH',r'C:\Dev\_scratch\Local-Explainer'))/'packaging'
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
