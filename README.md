# FreeCAD Path Simulation
A FreeCAD CAM addon for previewing milling and turning tool paths, with optional
material-removal simulation.

## Features
* Milling and turning toolpath previews
* Material-removal simulation or tool-motion-only playback
* Operation selection and colour-coded machined surfaces
* Play, pause and jump-to-end controls
* Interactive timeline for moving forwards and backwards through a job
* Centreline drilling and turning across the spindle axis

## Screenshots
![Milling simulation with operation colours and timeline controls](Screenshots/milling_simulation.png)
![Turning simulation with operation colours and timeline controls](Screenshots/turning_simulation.png)

## Requirements
* FreeCAD with the CAM workbench (the legacy Path workbench is not supported)

## Installation
Clone or extract this repository into your [FreeCAD `Mod/` directory](https://www.freecadweb.org/wiki/Installing_more_workbenches),
then restart FreeCAD.

## Usage
1. Open a CAM job and select **CAM -> CAM Addons -> Path Simulator Next**.
2. Choose the operations and whether to simulate material removal or preview tool motion.
3. Use **Play**, **Pause**, or **Jump to end**. Click or drag the timeline to seek.

Tools need valid geometry, feeds and spindle speed. Turning currently supports
straight tool movements only.

## Feedback
Report bugs or share feedback on the [Path Forum](https://forum.freecadweb.org/viewforum.php?f=15).

## Disclaimer
This experimental tool is used at your own risk. Machine tools are dangerous;
the author is not responsible for damage or injury caused by incorrect machining
parameters.
