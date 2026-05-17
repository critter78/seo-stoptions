"""Legacy entry — kept so old `streamlit run streamlit_app.py` invocations still work.

The real entry is `Home.py`. Use:
    streamlit run Home.py     # or ./run.sh
"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "Home.py"), run_name="__main__")
