import sys
import types
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch


def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load spec for {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_utils_module():
    root = Path(__file__).resolve().parents[1]
    zeekr_dir = root / "custom_components" / "zeekr_ev"

    # Create lightweight package stubs so relative imports in utils.py resolve.
    if "custom_components" not in sys.modules:
        custom_components_pkg = types.ModuleType("custom_components")
        custom_components_pkg.__path__ = [str(root / "custom_components")]
        sys.modules["custom_components"] = custom_components_pkg

    if "custom_components.zeekr_ev" not in sys.modules:
        zeekr_pkg = types.ModuleType("custom_components.zeekr_ev")
        zeekr_pkg.__path__ = [str(zeekr_dir)]
        sys.modules["custom_components.zeekr_ev"] = zeekr_pkg

    if "custom_components.zeekr_ev.const" not in sys.modules:
        _load_module_from_file("custom_components.zeekr_ev.const", zeekr_dir / "const.py")

    return _load_module_from_file("custom_components.zeekr_ev.utils", zeekr_dir / "utils.py")


utils = _load_utils_module()


def _client_with_module(module_name: str):
    client_cls = type("Client", (), {})
    client_cls.__module__ = module_name
    return client_cls()


class TestGetApiVersion(unittest.TestCase):
    def test_local_with_module_version(self):
        client = _client_with_module("custom_components.zeekr_ev_api.client")

        class _LocalModule:
            __version__ = "0.9.1"

        with patch.object(utils.importlib, "import_module", return_value=_LocalModule()):
            self.assertEqual(utils.get_api_version(client), "0.9.1 (local)")

    def test_local_without_module(self):
        client = _client_with_module("custom_components.zeekr_ev_api.client")

        with patch.object(utils.importlib, "import_module", side_effect=ImportError):
            self.assertEqual(utils.get_api_version(client), "local")

    def test_installed_package_version(self):
        client = _client_with_module("zeekr_ev_api.client")

        with patch.object(utils.metadata, "version", return_value="0.1.12"):
            self.assertEqual(utils.get_api_version(client), "0.1.12")

    def test_root_module_fallback_version(self):
        client = _client_with_module("some_api.client")

        class _RootModule:
            __version__ = "2.3.4"

        with patch.object(
            utils.metadata,
            "version",
            side_effect=utils.metadata.PackageNotFoundError("missing"),
        ):
            with patch.object(utils.importlib, "import_module", return_value=_RootModule()):
                self.assertEqual(utils.get_api_version(client), "2.3.4")

    def test_unresolvable_returns_none(self):
        client = _client_with_module("some_api.client")

        with patch.object(
            utils.metadata,
            "version",
            side_effect=utils.metadata.PackageNotFoundError("missing"),
        ):
            with patch.object(utils.importlib, "import_module", side_effect=ImportError):
                self.assertIsNone(utils.get_api_version(client))


if __name__ == "__main__":
    unittest.main()
