import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def load_panel():
    util = SimpleNamespace()
    base = SimpleNamespace(Util=util)
    path = Path(__file__).resolve().parents[1] / "PathSimGui.py"
    spec = importlib.util.spec_from_file_location("test_sim_gui", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        "PySide": SimpleNamespace(QtGui=SimpleNamespace(), QtCore=SimpleNamespace()),
        "FreeCAD": SimpleNamespace(ActiveDocument=Mock()),
        "FreeCADGui": SimpleNamespace(Control=Mock()),
        "Mesh": SimpleNamespace(),
        "Path": SimpleNamespace(Base=base),
        "Path.Base": base,
        "Path.Base.Util": util,
        "PathSim": SimpleNamespace(),
        "PathSimTimelineGui": SimpleNamespace(),
    }):
        spec.loader.exec_module(module)
    return module


gui = load_panel()


class ToolShutdownTests(unittest.TestCase):
    def setUp(self):
        self.panel = gui.PathSimPanel.__new__(gui.PathSimPanel)
        self.panel._closing = False
        self.panel.tool = None
        self.document = Mock()
        self.document_patch = patch.object(gui.FreeCAD, "ActiveDocument", self.document)
        self.document_patch.start()
        self.addCleanup(self.document_patch.stop)

    def test_queued_tool_callback_after_quit_does_not_recreate_tool(self):
        self.panel.tool = SimpleNamespace(Name="Tool")
        self.panel.meshView = None
        self.panel.timeline = Mock()
        self.panel.sim = Mock()
        queued = []
        shape = object()
        self.panel.sim.wait.side_effect = lambda: queued.append(
            lambda: self.panel.loadTool(shape))
        self.panel.quit()
        self.document.removeObject.assert_called_once_with("Tool")
        self.assertIsNone(self.panel.tool)
        for callback in queued:
            callback()
        self.document.addObject.assert_not_called()
        self.assertIsNone(self.panel.tool)

    def test_closing_does_not_modify_existing_tool(self):
        original_shape = object()
        self.panel.tool = SimpleNamespace(Shape=original_shape)
        self.panel._closing = True
        self.panel.loadTool(object())
        self.assertIs(self.panel.tool.Shape, original_shape)
        self.document.assert_not_called()
        self.document.addObject.assert_not_called()

    def test_open_panel_creates_and_updates_tool(self):
        shape = object()
        self.panel.loadTool(shape)
        self.document.addObject.assert_called_once_with("Part::FeaturePython", "Tool")
        self.assertIs(self.panel.tool, self.document.addObject.return_value)
        self.assertEqual(self.panel.tool.ViewObject.Proxy, 0)
        self.assertIs(self.panel.tool.Shape, shape)
        replacement = object()
        self.panel.loadTool(replacement)
        self.document.addObject.assert_called_once()
        self.assertIs(self.panel.tool.Shape, replacement)


if __name__ == "__main__":
    unittest.main()
