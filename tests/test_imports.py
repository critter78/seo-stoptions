"""Cheap import-only smoke test — verifies the whole package wires up."""
from __future__ import annotations

import sys
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestImports(unittest.TestCase):
    def test_tools_import(self):
        from tools import ALL_TOOLS
        self.assertGreaterEqual(len(ALL_TOOLS), 10)

    def test_app_config_import(self):
        from app.config import status_summary
        s = status_summary()
        self.assertIn("Anthropic API", s)

    def test_agents_module_imports(self):
        # Only import the modules — don't instantiate the LLM (no API key in CI).
        import agents.researcher  # noqa
        import agents.analyst  # noqa
        import agents.marketer  # noqa
        from agents.graph import build_graph  # noqa

    def test_streamlit_app_imports(self):
        # Importing streamlit_app under no Streamlit runtime would crash because it
        # calls st.set_page_config — so we only check the file parses.
        import py_compile
        py_compile.compile(str(ROOT / "streamlit_app.py"), doraise=True)


if __name__ == "__main__":
    unittest.main()
