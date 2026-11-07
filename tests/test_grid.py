import unittest
from unittest.mock import patch

from dexel import DexelGrid, RevolvedTool


class MillingSegmentTests(unittest.TestCase):
    def test_vertical_move_reaches_exact_lowest_endpoint(self):
        for tool in (RevolvedTool.flat(1), RevolvedTool.ball(1)):
            for start_z, end_z in ((4, 2), (2, 4)):
                with self.subTest(flat=tool.is_flat, start_z=start_z):
                    grid = DexelGrid((0, 0, 0, 3, 3, 6), resolution=1)
                    grid.extract()
                    changed = grid.cut_segment(
                        tool, 7, (1.5, 1.5, start_z), (1.5, 1.5, end_z))
                    self.assertGreater(changed, 0)
                    for j in range(grid.ny):
                        for i in range(grid.nx):
                            radius = ((i - 1) ** 2 + (j - 1) ** 2) ** 0.5
                            c = j * grid.nx + i
                            if radius <= tool.radius:
                                self.assertEqual(grid.hi[c], 2 + tool.bottom(radius))
                                self.assertEqual(grid.hi_id[c], 7)
                                self.assertEqual(grid.touch[c], 7)
                            else:
                                self.assertEqual(grid.hi[c], 6)
                    self.assertTrue(grid._dirty)
                    triangles, ids = grid.extract()
                    self.assertIn(7, ids)
                    self.assertIn(
                        2, [z for triangle in triangles for z in triangle[2::3]])

    def test_finite_tool_reaches_exact_upper_endpoint(self):
        for start_z, end_z in ((4, 2), (2, 4)):
            with self.subTest(start_z=start_z):
                grid = DexelGrid((0, 0, 0, 1, 1, 6), resolution=1)
                tool = RevolvedTool.flat(1, length=1)
                grid.cut_segment(tool, 7, (0.5, 0.5, start_z), (0.5, 0.5, end_z))
                self.assertEqual(grid.multi[0], [[0, 2, 0, 7], [5, 6, 7, 0]])
                self.assertEqual(grid.volume(), 3)

    def test_sloped_move_cuts_endpoints_only_at_their_xy_positions(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                grid = DexelGrid((0, 0, 0, 5, 1, 6), resolution=1)
                tool = RevolvedTool.flat(0.5, length=0.5)
                start, end = (0.5, 0.5, 2), (4.5, 0.5, 4)
                if reverse:
                    start, end = end, start
                grid.cut_segment(tool, 7, start, end)
                self.assertEqual(grid.multi[0][0], [0, 2, 0, 7])
                self.assertEqual(grid.multi[4][-1], [4.5, 6, 7, 0])
                self.assertGreater(grid.multi[2][0][1], 2)
                self.assertLess(grid.multi[2][-1][0], 4.5)

    def test_z_changing_move_keeps_midpoint_pieces(self):
        grid = DexelGrid((0, 0, 0, 1, 1, 6), resolution=1)
        tool = RevolvedTool.flat(1)
        with patch.object(grid, "_cut_piece", wraps=grid._cut_piece) as cut:
            changed = grid.cut_segment(tool, 7, (0.5, 0.5, 4), (0.5, 0.5, 2))
        self.assertEqual(cut.call_count, 10)
        heights = [call.args[-1] for call in cut.call_args_list]
        self.assertEqual(sorted(heights), [2] + [2.125 + i * 0.25 for i in range(8)] + [4])
        self.assertGreater(changed, 0)

    def test_constant_z_moves_do_not_add_endpoint_cuts(self):
        for end in ((0.5, 0.5, 2), (1.5, 0.5, 2)):
            with self.subTest(end=end):
                grid = DexelGrid((0, 0, 0, 2, 1, 6), resolution=1)
                tool = RevolvedTool.flat(1)
                with patch.object(grid, "_cut_piece", wraps=grid._cut_piece) as cut:
                    grid.cut_segment(tool, 7, (0.5, 0.5, 2), end)
                cut.assert_called_once_with(tool, 7, 0.5, 0.5, end[0], end[1], 2)


if __name__ == "__main__":
    unittest.main()
