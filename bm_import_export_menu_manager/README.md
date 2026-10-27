# BM Import & Export Menu Manager

Version 1.1.2 customizes Blender 5.2 LTS's **File > Import** and
**File > Export** menus independently.

Project home and support:
`https://github.com/Mjamfan22/Blender-Import-Export-Menu-Manager`

## Installation

1. Open **Edit > Preferences > Extensions**.
2. Open the menu in the upper-right and choose **Install from Disk**.
3. Select `BM_Import_Export_Menu_Manager_v1.1.2.zip`.
4. Enable **BM Import & Export Menu Manager** if Blender does not enable it
   automatically.

## Use

Open the add-on's preferences. Choose **Import** or **Export**, then:

- uncheck an entry to hide it;
- enter a custom readable label, or leave the field blank for its original
  label;
- press and hold the dotted handle on the left of an entry, drag it up or down,
  and release to place it within its group;
- read and edit each entry on one compact row, including its operator ID and
  assigned group;
- move across long lists in one drag instead of repeatedly clicking arrows;
- add, rename, remove, or reorder groups with the same dotted handles;
- use the arrow buttons as a one-step keyboard/mouse fallback;
- toggle whether each group starts with a separator and displays a heading;
- use the filter box to find an entry by label, operator, or source add-on;
- click **Refresh** after enabling another format add-on.

The manager also discovers new entries automatically whenever either File menu
is opened. Settings are stored in Blender's add-on preferences and survive
restarts when preferences are saved.

Drag up for an earlier position or down for a later position. Clear the entry
filter before reordering so hidden search results cannot make the destination
ambiguous.

## Safety and compatibility

The manager changes only menu presentation. It never unregisters import/export
operators and never edits Blender's installed scripts. For example, hiding
**FBX (.fbx) (Legacy)** under Import does not affect the FBX exporter.

Turn off **Customize File Import and Export Menus** to restore Blender's normal
menus while keeping the add-on enabled. Disabling or uninstalling the add-on
also restores the original menu callbacks, including callbacks registered by
other add-ons while the manager was active.

Unavailable entries are remembered so their settings return if their format
add-on is enabled again. Use **Forget Unavailable Entries** to remove those
saved settings permanently.

The add-on targets Blender 5.2 LTS and was verified with Blender 5.2.3 LTS.

## Limitations

- Menu callbacks that build entries from unusual context-sensitive UI code may
  appear only after they are available in the current Blender context.
- Unsupported third-party `UILayout` calls are reported in the add-on's
  preferences instead of being silently discarded.
- Groups are inline menu sections with optional separators and headings; they
  are not nested submenus.
- Saving preferences is governed by Blender's normal preference-saving setting.

See `LICENSE.txt` for licensing terms.
