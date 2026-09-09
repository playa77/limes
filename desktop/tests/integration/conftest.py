# desktop/tests/integration/conftest.py | v0.1.0 | expose the root suite's Neo4j fixture
"""The desktop integration flow reuses the root suite's session-scoped
disposable Neo4j container (`tests/integration/conftest.py`) and its graph
fixtures. Pytest collects fixtures from conftest.py files by path, not by
package name, so the root fixture is re-exported here under the same name.
"""

import importlib.util
import os
import sys

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
_ROOT_CONFTEST = os.path.join(_REPO_ROOT, "tests", "integration", "conftest.py")

_spec = importlib.util.spec_from_file_location(
    "limes_root_integration_conftest", _ROOT_CONFTEST
)
_root = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("limes_root_integration_conftest", _root)
_spec.loader.exec_module(_root)

neo4j_instance = _root.neo4j_instance  # re-export: same session-scoped container
