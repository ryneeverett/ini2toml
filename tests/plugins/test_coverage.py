from textwrap import dedent

from cfg2toml.plugins import coverage
from cfg2toml.translator import Translator


def test_coverage():
    example = """\
    # .coveragerc to control coverage.py
    [run]
    branch = True
    source = cfg2toml
    # omit = bad_file.py
    [paths]
    source =
        src/
        */site-packages/
    [report]
    # Regexes for lines to exclude from consideration
    exclude_lines =
        # Have to re-enable the standard pragma
        pragma: no cover
        # Don't complain about missing debug-only code
        def __repr__
        # Don't complain if tests don't hit defensive assertion code
        raise AssertionError
        raise NotImplementedError
        # Don't complain if non-runnable code isn't run
        if 0:
        if __name__ == .__main__.:
    """
    expected = """\
    # .coveragerc to control coverage.py

    [tool]
    [tool.coverage]

    [tool.coverage.run]
    branch = true
    source = ["cfg2toml"]
    # omit = bad_file.py

    [tool.coverage.paths]
    source = [
        "src/", 
        "*/site-packages/", 
    ]

    [tool.coverage.report]
    # Regexes for lines to exclude from consideration
    exclude_lines = [
        # Have to re-enable the standard pragma
        "pragma: no cover", 
        # Don't complain about missing debug-only code
        "def __repr__", 
        # Don't complain if tests don't hit defensive assertion code
        "raise AssertionError", 
        "raise NotImplementedError", 
        # Don't complain if non-runnable code isn't run
        "if 0:", 
        "if __name__ == .__main__.:", 
    ]
    """
    translator = Translator(plugins=[coverage.activate])
    out = translator.translate(dedent(example), ".coveragerc").strip()
    expected = dedent(expected).strip()
    print("expected=\n" + expected + "\n***")
    print("out=\n" + out)
    assert expected == out