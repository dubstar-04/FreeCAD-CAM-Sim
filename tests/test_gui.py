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
        self.document = Mock(Objects=[])
        self.panel.document = self.document
        self.document_patch = patch.object(gui.FreeCAD, "ActiveDocument", self.document)
        self.document_patch.start()
        self.addCleanup(self.document_patch.stop)

    def test_queued_tool_callback_after_quit_does_not_recreate_tool(self):
        self.panel.tool = SimpleNamespace(Name="Simulation_Tool", PathSimObject="Tool")
        self.document.Objects.append(self.panel.tool)
        self.panel.meshView = None
        self.panel.timeline = Mock()
        self.panel.sim = Mock()
        queued = []
        shape = object()
        self.panel.sim.wait.side_effect = lambda: queued.append(
            lambda: self.panel.loadTool(shape))
        self.panel.quit()
        self.document.removeObject.assert_called_once_with("Simulation_Tool")
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
        self.document.addObject.assert_called_once_with("Part::FeaturePython", "Simulation_Tool")
        self.assertIs(self.panel.tool, self.document.addObject.return_value)
        self.assertEqual(self.panel.tool.Label, "Simulation-Tool")
        self.assertEqual(self.panel.tool.PathSimObject, "Tool")
        self.assertEqual(self.panel.tool.ViewObject.Proxy, 0)
        self.assertIs(self.panel.tool.Shape, shape)
        replacement = object()
        self.panel.loadTool(replacement)
        self.document.addObject.assert_called_once()
        self.assertIs(self.panel.tool.Shape, replacement)


class SeekFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.panel = gui.PathSimPanel.__new__(gui.PathSimPanel)
        self.panel.tool = None
        self.panel.meshView = None
        self.panel.operations = [SimpleNamespace(Name="operation")]
        self.panel.getOperations = Mock(return_value=self.panel.operations)
        self.panel.onPathReady = Mock()
        self.panel.form = Mock()
        self.panel.timeline = Mock(progress=0)
        self.panel.timeline.setProgress.side_effect = lambda progress: setattr(
            self.panel.timeline, "progress", progress)
        self.panel.sim = Mock(initialised=False)
        self.panel.sim.isRunning.return_value = False
        self.panel.sim.setupEngine.return_value = True
        self.panel.sim.engine.showInitialStock = False
        self.marker_at_start = []
        self.panel.startWorker = Mock(side_effect=lambda: self.marker_at_start.append(
            self.panel.timeline.progress))
        self.panel.document = Mock(Objects=[])
        self.document_patch = patch.object(gui.FreeCAD, "ActiveDocument", self.panel.document)
        self.document_patch.start()
        self.addCleanup(self.document_patch.stop)

    def assert_first_seek_feedback(self, progress):
        self.panel.timeline.progress = progress
        self.panel.simSeek(progress)
        self.panel.sim.setupEngine.assert_called_once()
        self.panel.sim.skipTo.assert_called_once_with(progress)
        self.assertEqual(
            [call.args[0] for call in self.panel.timeline.setProgress.call_args_list],
            [0, progress])
        self.assertEqual(self.marker_at_start, [progress])

    def test_first_seek_restores_marker_before_starting_reconstruction(self):
        self.assert_first_seek_feedback(0.6)

    def test_first_jump_to_end_restores_marker_before_starting_reconstruction(self):
        self.assert_first_seek_feedback(1)

    def test_seek_during_playback_updates_marker_without_preparing_or_restarting(self):
        self.panel.sim.isRunning.return_value = True
        self.panel.prepareSimulation = Mock()
        self.panel.simSeek(0.6)
        self.panel.prepareSimulation.assert_not_called()
        self.panel.startWorker.assert_not_called()
        self.panel.sim.skipTo.assert_called_once_with(0.6)
        self.assertEqual(self.panel.timeline.progress, 0.6)

    def test_failed_preparation_does_not_submit_seek(self):
        self.panel.prepareSimulation = Mock(return_value=False)
        self.panel.simSeek(0.6)
        self.panel.sim.skipTo.assert_not_called()
        self.panel.startWorker.assert_not_called()
        self.panel.timeline.setProgress.assert_not_called()


class Document:
    def __init__(self):
        self.Objects = []
        self.removed = []

    def addObject(self, type_id, name):
        existing = {obj.Name for obj in self.Objects}
        base = name
        suffix = 1
        while name in existing:
            name = "{}{:03d}".format(base, suffix)
            suffix += 1
        obj = SimpleNamespace(
            Name=name, Label=name, TypeId=type_id, ViewObject=SimpleNamespace(),
            addProperty=Mock())
        self.Objects.append(obj)
        return obj

    def removeObject(self, name):
        obj = next(obj for obj in self.Objects if obj.Name == name)
        self.Objects.remove(obj)
        self.removed.append(name)


class SimulationObjectTests(unittest.TestCase):
    def setUp(self):
        self.document = Document()
        self.document_patch = patch.object(gui.FreeCAD, "ActiveDocument", self.document)
        self.document_patch.start()
        self.addCleanup(self.document_patch.stop)

    def add_simulation_objects(self):
        stock = self.document.addObject("Mesh::Feature", "Simulation_Cutshape")
        stock.PathSimObject = "Cutshape"
        tool = self.document.addObject("Part::FeaturePython", "Simulation_Tool")
        tool.PathSimObject = "Tool"
        return stock, tool

    def open_panel(self):
        with patch.object(gui.FreeCADGui, "PySideUic", SimpleNamespace(
                loadUi=lambda path: Mock()), create=True), \
                patch.object(gui.FreeCAD, "ParamGet", return_value=Mock(), create=True), \
                patch.object(gui.PathSim, "PathSim", return_value=Mock(), create=True), \
                patch.object(gui.PathSimTimelineGui, "timeline", return_value=Mock(), create=True), \
                patch.object(gui.PathSimPanel, "setupUi"):
            return gui.PathSimPanel()

    def test_opening_removes_only_identifiable_simulation_objects(self):
        legacy_stock = self.document.addObject("Mesh::Feature", "cutshape")
        legacy_tool = self.document.addObject("Part::FeaturePython", "Tool")
        unrelated = self.document.addObject("Part::Feature", "Simulation_Cutshape")
        self.add_simulation_objects()
        self.add_simulation_objects()
        panel = self.open_panel()
        self.assertEqual(self.document.Objects, [legacy_stock, legacy_tool, unrelated])
        self.assertEqual(len(self.document.removed), 4)
        self.assertIsNone(panel.tool)
        self.assertIsNone(panel.meshView)

    def test_preparation_creates_named_marked_stock_and_cleans_stale_objects(self):
        panel = self.open_panel()
        self.add_simulation_objects()
        panel.sim.initialised = False
        panel.sim.engine.showInitialStock = False
        panel.getOperations = Mock(return_value=[object()])
        panel.updateTimeline = Mock()
        self.assertTrue(panel.prepareSimulation())
        self.assertEqual(self.document.Objects, [panel.meshView])
        self.assertEqual(panel.meshView.Name, "Simulation_Cutshape")
        self.assertEqual(panel.meshView.Label, "Simulation-Cutshape")
        self.assertEqual(panel.meshView.PathSimObject, "Cutshape")
        panel.meshView.addProperty.assert_called_once_with(
            "App::PropertyString", "PathSimObject", "PathSim")
        panel.loadTool(object())
        self.assertEqual(panel.tool.Name, "Simulation_Tool")
        self.assertEqual(panel.tool.Label, "Simulation-Tool")
        self.assertEqual(panel.tool.PathSimObject, "Tool")
        panel.quit()
        self.assertEqual(self.document.Objects, [])
        self.assertIsNone(panel.tool)
        self.assertIsNone(panel.meshView)

    def test_closing_cleans_original_document_even_if_references_are_missing(self):
        panel = self.open_panel()
        self.add_simulation_objects()
        other_document = Document()
        other_stock = other_document.addObject("Mesh::Feature", "Simulation_Cutshape")
        other_stock.PathSimObject = "Cutshape"
        with patch.object(gui.FreeCAD, "ActiveDocument", other_document):
            panel.quit()
        self.assertEqual(self.document.Objects, [])
        self.assertEqual(other_document.Objects, [other_stock])
        panel.cleanup()
        self.assertEqual(len(self.document.removed), 2)

    def test_cleanup_tolerates_objects_already_deleted_from_document(self):
        panel = self.open_panel()
        panel.meshView, panel.tool = self.add_simulation_objects()
        self.document.removeObject(panel.meshView.Name)
        self.document.removeObject(panel.tool.Name)
        panel.cleanup()
        self.assertIsNone(panel.meshView)
        self.assertIsNone(panel.tool)
        self.assertEqual(len(self.document.removed), 2)


if __name__ == "__main__":
    unittest.main()
