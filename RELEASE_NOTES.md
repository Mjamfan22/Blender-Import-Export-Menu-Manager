# BM Import & Export Menu Manager 1.1.2

BM Import & Export Menu Manager makes Blender's growing format menus easier to
scan without disabling or modifying the underlying import/export add-ons.

## Highlights

- Build clean inline sections such as BeamNG, Rigs of Rods, Unreal Engine, or
  any workflow-specific category.
- Configure File → Import and File → Export independently.
- Press and hold a dotted handle to drag an entry or group into position.
- Use a compact one-line layout for quick editing of names, operator IDs, and
  group assignments.
- Hide unused entries without unregistering their Blender operators.
- Automatically discover menu entries supplied by other enabled add-ons.

## Installation

1. Download `BM_Import_Export_Menu_Manager_v1.1.2.zip` below.
2. Open Blender 5.2 LTS.
3. Go to **Edit → Preferences → Extensions**.
4. Choose **Install from Disk** and select the ZIP without extracting it.
5. Enable the add-on and confirm the master customization checkbox is on.

## Verification

This release was validated with Blender 5.2.3 LTS. The automated suite covers
menu discovery, independent Import/Export visibility, group headings and
separators, custom labels, drag ordering, registration persistence, restoration
of original menus, specialty add-on callbacks, and installation from the final
ZIP in a disposable Blender profile. Release packaging is reproducible across
Windows, Linux, and macOS, and GitHub verifies the checksum before publishing.

## Package integrity

- File: `BM_Import_Export_Menu_Manager_v1.1.2.zip`
- Size: 52,325 bytes
- SHA-256: `5a43303240c8a252932a594d15b2af9d9d319ec52ef011f7709a46db422f14dd`
