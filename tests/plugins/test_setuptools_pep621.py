import pytest
from configupdater import ConfigUpdater

from cfg2toml.plugins.setuptools_pep621 import SetuptoolsPEP621, activate
from cfg2toml.processing import Transformer
from cfg2toml.toml_adapter import dumps, loads
from cfg2toml.translator import Translator


@pytest.fixture
def plugin():
    return SetuptoolsPEP621(Transformer())


@pytest.fixture
def translate():
    translator = Translator(plugins=[])
    translator["simple"]  # ensure profile exists
    return lambda text: translator.translate(text, "simple")


@pytest.fixture
def cfg2tomlobj(translate):
    return lambda text: loads(translate(text))


example_normalise_keys = """\
[metadata]
summary = Automatically translates .cfg/.ini files into TOML
author_email = example@example
license-file = LICENSE.txt
long_description_content_type = text/x-rst; charset=UTF-8
home_page = https://github.com/abravalheri/cfg2toml/
classifier = Development Status :: 4 - Beta
platform = any
"""
expected_normalise_keys = """\
[metadata]
description = Automatically translates .cfg/.ini files into TOML
author-email = example@example
license-files = LICENSE.txt
long-description-content-type = text/x-rst; charset=UTF-8
url = https://github.com/abravalheri/cfg2toml/
classifiers = Development Status :: 4 - Beta
platforms = any
"""


def test_normalise_keys(plugin):
    cfg = ConfigUpdater().read_string(example_normalise_keys)
    cfg = plugin.normalise_keys(cfg)
    assert str(cfg) == expected_normalise_keys


# ----


example_convert_directives = """\
[metadata]
version = "attr: mymodule.myfunc"
classifiers = "file: CLASSIFIERS.txt"
description = "file: README.txt"
[options]
entry-points = "file: ENTRYPOINTS.txt"
packages = "find_namespace:"
"""
expected_convert_directives = """\
[metadata]
version = {attr = "mymodule.myfunc"}
classifiers = {file = "CLASSIFIERS.txt"}
description = {file = "README.txt"}
[options]
entry-points = {file = "ENTRYPOINTS.txt"}
packages = {find_namespace = ""}
"""


def test_convert_directives(plugin):
    doc = loads(example_convert_directives)
    doc = plugin.convert_directives(ConfigUpdater(), doc)
    assert dumps(doc) == expected_convert_directives


# ----


example_apply_value_processing = """\
[metadata]
version = 5.3  # comment
classifiers =
    Development Status :: 4 - Beta
    Programming Language :: Python
keywords = python, module
[options]
zip-safe = False  # comment
package-dir =
    *=src # TODO: tomlkit/atoml bug with empty keys
install-requires =
    importlib-metadata; python_version<"3.8"
    configupdater>=3,<=4
[options.entry-points]
# For example:
pyscaffold.cli =
    # comment
    fibonacci = cfg2toml.skeleton:run # comment
    awesome = pyscaffoldext.awesome.extension:AwesomeExtension
"""
expected_apply_value_processing = """\
[metadata]
version = "5.3" # comment
classifiers = [
    "Development Status :: 4 - Beta", 
    "Programming Language :: Python", 
]
keywords = ["python", "module"]

[options]
zip-safe = false # comment
package-dir = {"*" = "src"} # TODO: tomlkit/atoml bug with empty keys
install-requires = [
    "importlib-metadata; python_version<\\"3.8\\"", 
    "configupdater>=3,<=4", 
]
[options.entry-points]
# For example:

[options.entry-points."pyscaffold.cli"]
# comment
fibonacci = "cfg2toml.skeleton:run" # comment
awesome = "pyscaffoldext.awesome.extension:AwesomeExtension"
"""


def test_apply_value_processing(cfg2tomlobj, plugin):
    cfg = ConfigUpdater().read_string(example_apply_value_processing)
    doc = cfg2tomlobj(example_apply_value_processing)
    doc = plugin.separate_subtables(cfg, doc)
    doc = plugin.apply_value_processing(cfg, doc)
    assert dumps(doc).strip() == expected_apply_value_processing.strip()


# ----


example_separate_subtables = """\
[options.packages.find]
where = src
[options.entry-points]
# For example:
"""

expected_separate_subtables = """\
[options]
[options.packages]
[options.packages.find]
where = "src"


[options.entry-points]
# For example:
"""  # TODO: unnecessary double newline


def test_separate_subtables(cfg2tomlobj, plugin):
    cfg = ConfigUpdater().read_string(example_separate_subtables.strip())
    doc = cfg2tomlobj(example_separate_subtables)
    doc = plugin.separate_subtables(cfg, doc)
    assert dumps(doc).strip() == expected_separate_subtables.strip()


# ----


example_fix_license = """\
[project]
license = { file = "LICENSE.txt", text = "MPL-2.0" }
"""

expected_fix_license = """\
[project]
license = { file = "LICENSE.txt",  }
"""  # TODO: unnecessary comma/space


def test_fix_license(plugin):
    doc = loads(example_fix_license.strip())
    doc = plugin.fix_license({}, doc)
    assert dumps(doc).strip() == expected_fix_license.strip()


# ----


example_fix_packages = """\
[tool.setuptools.packages]
find-namespace = ""
[tool.setuptools.packages.find]
where = "src"
exclude = ["tests"]
"""

expected_fix_packages = """\
[tool.setuptools.packages]

[tool.setuptools.packages.find-namespace]
where = "src"
exclude = ["tests"]
"""


def test_fix_packages(plugin):
    doc = loads(example_fix_packages.strip())
    doc = plugin.fix_packages({}, doc)
    assert dumps(doc).strip() == expected_fix_packages.strip()


# ----


example_fix_setup_requires = """\
[options]
setup_requires =
    setuptools>=46.1.0
    setuptools_scm>=5
"""

expected_fix_setup_requires = """\
[build-system]
requires = ["setuptools>=46.1.0", "setuptools_scm>=5", "wheel"]
build-backend = "setuptools.build_meta"
"""


def test_fix_setup_requires():
    translator = Translator(plugins=[activate])
    text = translator.translate(example_fix_setup_requires.strip(), "setup.cfg")
    print(text)
    assert text == expected_fix_setup_requires.strip()


# ----


def test_empty():
    translator = Translator(plugins=[activate])
    text = translator.translate("", "setup.cfg")
    doc = loads(text)
    assert "build-system" in doc