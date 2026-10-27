"""BM Import & Export Menu Manager for Blender 5.2 LTS."""

bl_info = {
    "name": "BM Import & Export Menu Manager",
    "author": "Mjamfan22",
    "version": (1, 1, 2),
    "blender": (5, 2, 0),
    "location": "Edit > Preferences > Add-ons",
    "description": "Show, hide, rename, reorder, and group File Import/Export entries",
    "warning": "",
    "doc_url": "",
    "category": "Import-Export",
}

from . import preferences, runtime


def register():
    preferences.register()
    runtime.register()


def unregister():
    runtime.unregister()
    preferences.unregister()


if __name__ == "__main__":
    register()
