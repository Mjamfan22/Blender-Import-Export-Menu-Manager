"""Persistent settings and focused preferences UI."""

from __future__ import annotations

import uuid

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import AddonPreferences, Operator, PropertyGroup

from . import runtime


PACKAGE_NAME = __package__
_ENUM_STRING_POOL: dict[str, str] = {}
_GROUP_ENUM_CACHE: dict[str, tuple[tuple, tuple]] = {}


def _enum_string(value: str) -> str:
    """Keep dynamic enum strings alive for Blender's RNA pointer lifetime."""
    value = str(value)
    return _ENUM_STRING_POOL.setdefault(value, value)


def get_preferences(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(PACKAGE_NAME)
    return addon.preferences if addon else None


def _group_items(entry, context):
    prefs = get_preferences(context)
    menu_kind = getattr(entry, "menu_kind", runtime.IMPORT)
    groups = []
    if prefs:
        groups = list(sorted(
            (group for group in prefs.groups if group.menu_kind == menu_kind),
            key=lambda group: (group.order, group.uid),
        ))
    signature = tuple((group.uid, group.name, group.order) for group in groups)
    cached = _GROUP_ENUM_CACHE.get(menu_kind)
    if cached and cached[0] == signature:
        return cached[1]

    items = [
        (
            _enum_string(runtime.UNGROUPED),
            _enum_string("Ungrouped"),
            _enum_string("Show directly in the menu"),
        )
    ]
    items.extend(
        (
            _enum_string(group.uid),
            _enum_string(group.name),
            _enum_string(f"Place under {group.name}"),
        )
        for group in groups
    )
    stable_items = tuple(items)
    _GROUP_ENUM_CACHE[menu_kind] = (signature, stable_items)
    return stable_items


def _enabled_update(preferences, context):
    runtime.set_enabled(preferences.enabled)


def _entry_group_update(entry, context):
    prefs = get_preferences(context)
    if prefs is None or not entry.key:
        return
    peer_orders = [
        peer.order
        for peer in prefs.entries
        if peer.key != entry.key
        and peer.menu_kind == entry.menu_kind
        and peer.group_id == entry.group_id
    ]
    entry.order = max(peer_orders, default=-10) + 10
    entry.order_customized = True


def _ordered_groups(preferences, menu_kind):
    return sorted(
        (group for group in preferences.groups if group.menu_kind == menu_kind),
        key=lambda group: (group.order, group.uid),
    )


def _ordered_entry_peers(preferences, target):
    return sorted(
        (
            entry
            for entry in preferences.entries
            if entry.menu_kind == target.menu_kind
            and entry.group_id == target.group_id
            and entry.available
        ),
        key=lambda entry: (entry.order, entry.default_order, entry.key),
    )


def _move_ordered_item(ordered, target, direction, *, customize_entries=False):
    """Move an item one visual position and keep order values deterministic."""
    if target not in ordered or direction not in {-1, 1}:
        return False
    index = ordered.index(target)
    other_index = index + direction
    if not 0 <= other_index < len(ordered):
        return False

    # Older saved preferences can contain duplicate order values. Normalize
    # before swapping so dragging can never appear to do nothing.
    if len({item.order for item in ordered}) != len(ordered):
        for normalized_index, item in enumerate(ordered):
            item.order = normalized_index * 10

    other = ordered[other_index]
    target.order, other.order = other.order, target.order
    if customize_entries:
        target.order_customized = True
        other.order_customized = True
    return True


def _move_group_step(preferences, target, direction):
    return _move_ordered_item(
        _ordered_groups(preferences, target.menu_kind),
        target,
        direction,
    )


def _move_entry_step(preferences, target, direction):
    return _move_ordered_item(
        _ordered_entry_peers(preferences, target),
        target,
        direction,
        customize_entries=True,
    )


def _position_in(ordered, target, identity):
    target_id = identity(target)
    return next(
        (index for index, item in enumerate(ordered) if identity(item) == target_id),
        -1,
    )


def _move_to_position(ordered, target, value, move_step, identity):
    """Move an item to a one-based position."""
    current = _position_in(ordered, target, identity)
    if current < 0 or len(ordered) < 2:
        return
    requested = max(0, min(len(ordered) - 1, int(value) - 1))
    direction = -1 if requested < current else 1
    for _ in range(abs(requested - current)):
        if not move_step(target, direction):
            break


def _drag_handle_get(_item):
    return False


def _drag_handle_set(_item, _value):
    # A property button reports its owner here as soon as Blender activates it.
    # The window-level listener consumes that owner on the next mouse-move.
    global _DRAG_HANDLE_TARGET
    _DRAG_HANDLE_TARGET = _item


class BMIMEM_PG_group(PropertyGroup):
    uid: StringProperty(name="ID")
    menu_kind: EnumProperty(
        name="Menu",
        items=((runtime.IMPORT, "Import", ""), (runtime.EXPORT, "Export", "")),
    )
    name: StringProperty(name="Group name", default="New Group")
    separator_before: BoolProperty(
        name="Separator",
        description="Draw a separator before this group",
        default=True,
    )
    show_header: BoolProperty(
        name="Heading",
        description="Draw the group name as a menu heading",
        default=True,
    )
    order: IntProperty(name="Order", default=0)
    drag_handle: BoolProperty(
        name="Drag to reorder",
        description="Press and hold, drag up or down, then release to place this group",
        get=_drag_handle_get,
        set=_drag_handle_set,
        options={"SKIP_SAVE"},
    )


class BMIMEM_PG_entry(PropertyGroup):
    key: StringProperty(name="Key")
    menu_kind: EnumProperty(
        name="Menu",
        items=((runtime.IMPORT, "Import", ""), (runtime.EXPORT, "Export", "")),
    )
    entry_kind: StringProperty(name="Entry type")
    action_id: StringProperty(name="Action")
    callback_id: StringProperty(name="Source")
    default_label: StringProperty(name="Default label")
    custom_label: StringProperty(
        name="Label",
        description="Custom menu label; leave blank to use the add-on's original label",
    )
    visible: BoolProperty(
        name="Visible",
        description="Show this entry in the File menu",
        default=True,
    )
    group_id: EnumProperty(name="Group", items=_group_items, update=_entry_group_update)
    order: IntProperty(name="Order", default=0)
    default_order: IntProperty(name="Default order", default=0)
    order_customized: BoolProperty(name="Custom order", default=False)
    available: BoolProperty(name="Available", default=False, options={"SKIP_SAVE"})
    discovery_error: StringProperty(name="Issue", options={"SKIP_SAVE"})
    drag_handle: BoolProperty(
        name="Drag to reorder",
        description="Press and hold, drag up or down, then release to place this entry",
        get=_drag_handle_get,
        set=_drag_handle_set,
        options={"SKIP_SAVE"},
    )


_DRAG_LISTENER_WINDOWS: set[int] = set()
_DRAG_LISTENER_ENABLED = False
_DRAG_LISTENER_GENERATION = 0
_DRAG_HANDLE_TARGET = None


def _resolve_hovered_drag_item(context):
    """Return (kind, item) when the pointer is over one of our grip props."""
    global _DRAG_HANDLE_TARGET
    owner = _DRAG_HANDLE_TARGET
    _DRAG_HANDLE_TARGET = None
    if isinstance(owner, BMIMEM_PG_group):
        return "GROUP", owner
    if isinstance(owner, BMIMEM_PG_entry):
        return "ENTRY", owner

    try:
        owner = context.button_pointer
        prop = context.button_prop
    except (AttributeError, RuntimeError):
        return None
    if owner is None or prop is None or prop.identifier != "drag_handle":
        return None
    if isinstance(owner, BMIMEM_PG_group):
        return "GROUP", owner
    if isinstance(owner, BMIMEM_PG_entry):
        return "ENTRY", owner
    return None


def _tag_window_redraw(window):
    if window and window.screen:
        for area in window.screen.areas:
            area.tag_redraw()


class BMIMEM_OT_hold_drag_listener(Operator):
    """Capture press/hold gestures on the dotted reorder handles."""

    bl_idname = "bm_menu_manager.hold_drag_listener"
    bl_label = "Menu Manager Drag Listener"
    bl_options = {"INTERNAL"}

    def _clear_drag(self, context, *, cancel=False):
        if cancel:
            prefs = get_preferences(context)
            if prefs is not None:
                collection = prefs.groups if self._drag_kind == "GROUP" else prefs.entries
                identity = "uid" if self._drag_kind == "GROUP" else "key"
                by_id = {getattr(item, identity): item for item in collection}
                for item_id, order in self._order_snapshot:
                    item = by_id.get(item_id)
                    if item is not None:
                        item.order = order
        if self._drag_kind:
            try:
                context.window.cursor_modal_restore()
            except RuntimeError:
                pass
        self._drag_kind = ""
        self._drag_id = ""
        self._order_snapshot = []
        self._mouse_down = False
        _tag_window_redraw(context.window)

    def _stop(self, context):
        self._clear_drag(context, cancel=True)
        _DRAG_LISTENER_WINDOWS.discard(self._window_pointer)
        return {"CANCELLED"}

    def _begin_drag(self, context, event, kind, item):
        prefs = get_preferences(context)
        if prefs is None or (kind == "ENTRY" and prefs.filter_text.strip()):
            return False
        if kind == "GROUP":
            ordered = _ordered_groups(prefs, item.menu_kind)
            identity = lambda value: value.uid
            row_height = 22.0
        else:
            ordered = _ordered_entry_peers(prefs, item)
            identity = lambda value: value.key
            row_height = 22.0
        start_index = _position_in(ordered, item, identity)
        if start_index < 0:
            return False

        self._drag_kind = kind
        self._drag_id = identity(item)
        self._start_index = start_index
        self._start_mouse_y = event.mouse_y
        self._row_height = row_height * max(0.5, context.preferences.system.ui_scale)
        self._order_snapshot = [(identity(value), value.order) for value in ordered]
        try:
            context.window.cursor_modal_set("SCROLL_Y")
        except RuntimeError:
            pass
        return True

    def _update_drag(self, context, event):
        prefs = get_preferences(context)
        if prefs is None:
            return
        if self._drag_kind == "GROUP":
            target = next((item for item in prefs.groups if item.uid == self._drag_id), None)
            if target is None:
                return
            ordered = _ordered_groups(prefs, target.menu_kind)
            move_step = lambda item, direction: _move_group_step(prefs, item, direction)
            identity = lambda item: item.uid
        else:
            target = next((item for item in prefs.entries if item.key == self._drag_id), None)
            if target is None:
                return
            ordered = _ordered_entry_peers(prefs, target)
            move_step = lambda item, direction: _move_entry_step(prefs, item, direction)
            identity = lambda item: item.key

        delta_rows = round((event.mouse_y - self._start_mouse_y) / self._row_height)
        requested = max(0, min(len(ordered) - 1, self._start_index - delta_rows))
        _move_to_position(ordered, target, requested + 1, move_step, identity)
        _tag_window_redraw(context.window)

    def invoke(self, context, event):
        self._window_pointer = context.window.as_pointer()
        if self._window_pointer in _DRAG_LISTENER_WINDOWS:
            return {"CANCELLED"}
        self._generation = _DRAG_LISTENER_GENERATION
        self._drag_kind = ""
        self._drag_id = ""
        self._order_snapshot = []
        self._mouse_down = False
        self._press_mouse_y = 0
        _DRAG_LISTENER_WINDOWS.add(self._window_pointer)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if not _DRAG_LISTENER_ENABLED or self._generation != _DRAG_LISTENER_GENERATION:
            return self._stop(context)

        if self._drag_kind:
            if event.type == "MOUSEMOVE":
                self._update_drag(context, event)
            elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
                self._clear_drag(context)
                # Let Blender's underlying handle button finish its own press cycle.
                return {"PASS_THROUGH"}
            elif event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
                self._clear_drag(context, cancel=True)
            return {"RUNNING_MODAL"}

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            global _DRAG_HANDLE_TARGET
            _DRAG_HANDLE_TARGET = None
            self._mouse_down = True
            self._press_mouse_y = event.mouse_y
            hovered = _resolve_hovered_drag_item(context)
            if hovered and self._begin_drag(context, event, *hovered):
                return {"RUNNING_MODAL"}
        elif event.type == "MOUSEMOVE" and self._mouse_down:
            hovered = _resolve_hovered_drag_item(context)
            if hovered and self._begin_drag(context, event, *hovered):
                self._start_mouse_y = self._press_mouse_y
                self._update_drag(context, event)
                return {"RUNNING_MODAL"}
        elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self._mouse_down = False
            _DRAG_HANDLE_TARGET = None
        return {"PASS_THROUGH"}


def _ensure_drag_listeners():
    if not _DRAG_LISTENER_ENABLED or bpy.app.background:
        return None
    window_manager = bpy.context.window_manager
    if window_manager is None:
        return 1.0

    live_windows = {window.as_pointer() for window in window_manager.windows}
    _DRAG_LISTENER_WINDOWS.intersection_update(live_windows)
    for window in window_manager.windows:
        if window.as_pointer() in _DRAG_LISTENER_WINDOWS or window.screen is None:
            continue
        area = next(iter(window.screen.areas), None)
        if area is None:
            continue
        region = next((value for value in area.regions if value.type == "WINDOW"), None)
        override = {"window": window, "area": area}
        if region is not None:
            override["region"] = region
        try:
            with bpy.context.temp_override(**override):
                bpy.ops.bm_menu_manager.hold_drag_listener("INVOKE_DEFAULT")
        except RuntimeError:
            continue
    return 1.0


class BMIMEM_OT_refresh(Operator):
    bl_idname = "bm_menu_manager.refresh"
    bl_label = "Refresh Menu Entries"
    bl_description = "Discover entries from currently registered import/export add-ons"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        runtime.synchronize_all(context)
        self.report({"INFO"}, "Import and export menu entries refreshed")
        return {"FINISHED"}


class BMIMEM_OT_add_group(Operator):
    bl_idname = "bm_menu_manager.add_group"
    bl_label = "Add Menu Group"
    bl_options = {"INTERNAL"}

    menu_kind: StringProperty(options={"HIDDEN"})
    group_name: StringProperty(name="Name", default="New Group")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = self.group_name.strip()
        if not name:
            self.report({"ERROR"}, "Group name cannot be empty")
            return {"CANCELLED"}
        prefs = get_preferences(context)
        same_menu = [group for group in prefs.groups if group.menu_kind == self.menu_kind]
        group = prefs.groups.add()
        group.uid = uuid.uuid4().hex
        group.menu_kind = self.menu_kind
        group.name = name
        group.order = (max((item.order for item in same_menu), default=-10) + 10)
        return {"FINISHED"}


class BMIMEM_OT_remove_group(Operator):
    bl_idname = "bm_menu_manager.remove_group"
    bl_label = "Remove Menu Group"
    bl_description = "Remove this group and return its entries to Ungrouped"
    bl_options = {"INTERNAL"}

    group_uid: StringProperty(options={"HIDDEN"})

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        prefs = get_preferences(context)
        for entry in prefs.entries:
            if entry.group_id == self.group_uid:
                entry.group_id = runtime.UNGROUPED
        for index in range(len(prefs.groups) - 1, -1, -1):
            if prefs.groups[index].uid == self.group_uid:
                prefs.groups.remove(index)
                return {"FINISHED"}
        return {"CANCELLED"}


class BMIMEM_OT_move_group(Operator):
    bl_idname = "bm_menu_manager.move_group"
    bl_label = "Move Menu Group"
    bl_options = {"INTERNAL"}

    group_uid: StringProperty(options={"HIDDEN"})
    direction: IntProperty(options={"HIDDEN"})

    def execute(self, context):
        prefs = get_preferences(context)
        target = next((group for group in prefs.groups if group.uid == self.group_uid), None)
        if target is None:
            return {"CANCELLED"}
        return {"FINISHED"} if _move_group_step(prefs, target, self.direction) else {"CANCELLED"}


class BMIMEM_OT_move_entry(Operator):
    bl_idname = "bm_menu_manager.move_entry"
    bl_label = "Move Menu Entry"
    bl_options = {"INTERNAL"}

    entry_key: StringProperty(options={"HIDDEN"})
    direction: IntProperty(options={"HIDDEN"})

    def execute(self, context):
        prefs = get_preferences(context)
        target = next((entry for entry in prefs.entries if entry.key == self.entry_key), None)
        if target is None:
            return {"CANCELLED"}
        return {"FINISHED"} if _move_entry_step(prefs, target, self.direction) else {"CANCELLED"}


class BMIMEM_OT_reset_menu(Operator):
    bl_idname = "bm_menu_manager.reset_menu"
    bl_label = "Reset Menu Customization"
    bl_description = "Reset visibility, labels, order, and groups for this menu"
    bl_options = {"INTERNAL"}

    menu_kind: StringProperty(options={"HIDDEN"})

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        prefs = get_preferences(context)
        for entry in prefs.entries:
            if entry.menu_kind == self.menu_kind:
                entry.visible = True
                entry.custom_label = ""
                entry.group_id = runtime.UNGROUPED
                entry.order = entry.default_order
                entry.order_customized = False
        for index in range(len(prefs.groups) - 1, -1, -1):
            if prefs.groups[index].menu_kind == self.menu_kind:
                prefs.groups.remove(index)
        return {"FINISHED"}


class BMIMEM_OT_forget_unavailable(Operator):
    bl_idname = "bm_menu_manager.forget_unavailable"
    bl_label = "Forget Unavailable Entries"
    bl_description = "Remove saved settings for entries whose add-ons are no longer registered"
    bl_options = {"INTERNAL"}

    menu_kind: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        prefs = get_preferences(context)
        removed = 0
        for index in range(len(prefs.entries) - 1, -1, -1):
            entry = prefs.entries[index]
            if entry.menu_kind == self.menu_kind and not entry.available:
                prefs.entries.remove(index)
                removed += 1
        self.report({"INFO"}, f"Forgot {removed} unavailable entr{'y' if removed == 1 else 'ies'}")
        return {"FINISHED"}


class BMIMEM_Preferences(AddonPreferences):
    bl_idname = PACKAGE_NAME

    enabled: BoolProperty(
        name="Customize File Import and Export Menus",
        description="Turn menu customization on or restore Blender's normal menus",
        default=True,
        update=_enabled_update,
    )
    selected_menu: EnumProperty(
        name="Menu",
        items=((runtime.IMPORT, "Import", ""), (runtime.EXPORT, "Export", "")),
        default=runtime.IMPORT,
    )
    filter_text: StringProperty(
        name="Filter",
        description="Filter by label, operator, or source add-on",
        options={"TEXTEDIT_UPDATE"},
    )
    show_unavailable: BoolProperty(
        name="Show unavailable",
        description="Show remembered entries from add-ons that are not currently registered",
        default=False,
    )
    entries: CollectionProperty(type=BMIMEM_PG_entry)
    groups: CollectionProperty(type=BMIMEM_PG_group)

    def draw(self, context):
        layout = self.layout
        header = layout.row(align=True)
        header.prop(self, "enabled")
        header.operator("bm_menu_manager.refresh", text="", icon="FILE_REFRESH")

        if self.enabled and not runtime.is_active():
            layout.label(text="Menu interception is not active; toggle the manager off and on.", icon="ERROR")

        tabs = layout.row(align=True)
        tabs.prop(self, "selected_menu", expand=True)
        menu_kind = self.selected_menu

        controls = layout.row(align=True)
        controls.prop(self, "filter_text", text="", icon="VIEWZOOM")
        controls.prop(self, "show_unavailable", text="Unavailable")
        reset = controls.operator("bm_menu_manager.reset_menu", text="Reset", icon="LOOP_BACK")
        reset.menu_kind = menu_kind

        layout.label(
            text="Press and hold a dotted handle, drag up or down, then release to place.",
            icon="MOUSE_LMB_DRAG",
        )

        group_box = layout.box()
        title = group_box.row(align=True)
        title.label(text="Groups", icon="OUTLINER_COLLECTION")
        add = title.operator("bm_menu_manager.add_group", text="Add", icon="ADD")
        add.menu_kind = menu_kind
        groups = sorted(
            (group for group in self.groups if group.menu_kind == menu_kind),
            key=lambda group: (group.order, group.uid),
        )
        if not groups:
            group_box.label(text="No groups. Entries are shown directly in the menu.", icon="INFO")
        for group in groups:
            row = group_box.row(align=True)
            split = row.split(factor=0.07, align=True)
            grip = split.row(align=True)
            grip.prop(group, "drag_handle", text="", icon="GRIP_V", emboss=False)
            row = split.row(align=True)
            row.prop(group, "name", text="")
            row.prop(group, "separator_before", text="", icon="REMOVE")
            row.prop(group, "show_header", text="", icon="FONT_DATA")
            up = row.operator("bm_menu_manager.move_group", text="", icon="TRIA_UP")
            up.group_uid, up.direction = group.uid, -1
            down = row.operator("bm_menu_manager.move_group", text="", icon="TRIA_DOWN")
            down.group_uid, down.direction = group.uid, 1
            remove = row.operator("bm_menu_manager.remove_group", text="", icon="X")
            remove.group_uid = group.uid

        entries_box = layout.box()
        available_count = sum(
            1 for entry in self.entries if entry.menu_kind == menu_kind and entry.available
        )
        entries_title = entries_box.row(align=True)
        entries_title.label(text=f"Entries ({available_count} available)", icon="PRESET")
        query = self.filter_text.casefold().strip()
        if query:
            entries_title.label(text="Clear the filter to reorder", icon="INFO")
        visible_entries = runtime.sorted_settings(
            self, menu_kind, include_unavailable=self.show_unavailable
        )
        visible_entries = [
            entry
            for entry in visible_entries
            if not query
            or query in entry.default_label.casefold()
            or query in entry.custom_label.casefold()
            or query in entry.action_id.casefold()
            or query in entry.callback_id.casefold()
        ]
        if not visible_entries:
            entries_box.label(text="No matching entries. Click Refresh after enabling a format add-on.", icon="INFO")
        for entry in visible_entries:
            row = entries_box.row(align=True)
            row.enabled = entry.available
            drag_slot = row.row(align=True)
            drag_slot.enabled = not query
            drag_slot.prop(entry, "drag_handle", text="", icon="GRIP_V", emboss=False)
            icon = "CHECKBOX_HLT" if entry.visible else "CHECKBOX_DEHLT"
            row.prop(entry, "visible", text="", icon=icon)
            row.prop(entry, "custom_label", text="", placeholder=entry.default_label)
            status = entry.action_id
            if not entry.available:
                status += " — unavailable"
            if entry.discovery_error:
                status += f" — {entry.discovery_error}"
            if entry.discovery_error:
                row.label(text=status, icon="ERROR")
            else:
                row.label(text=status)
            row.prop(entry, "group_id", text="")
            up = row.operator("bm_menu_manager.move_entry", text="", icon="TRIA_UP")
            up.entry_key, up.direction = entry.key, -1
            down = row.operator("bm_menu_manager.move_entry", text="", icon="TRIA_DOWN")
            down.entry_key, down.direction = entry.key, 1

        errors = runtime.discovery_errors(menu_kind)
        if errors:
            warning = layout.box()
            warning.label(text=f"{len(errors)} menu callback diagnostic(s)", icon="ERROR")
            for message in errors[:3]:
                warning.label(text=message)
        if any(
            entry.menu_kind == menu_kind and not entry.available for entry in self.entries
        ):
            forget = layout.row()
            operator = forget.operator("bm_menu_manager.forget_unavailable", icon="TRASH")
            operator.menu_kind = menu_kind


CLASSES = (
    BMIMEM_PG_group,
    BMIMEM_PG_entry,
    BMIMEM_OT_hold_drag_listener,
    BMIMEM_OT_refresh,
    BMIMEM_OT_add_group,
    BMIMEM_OT_remove_group,
    BMIMEM_OT_move_group,
    BMIMEM_OT_move_entry,
    BMIMEM_OT_reset_menu,
    BMIMEM_OT_forget_unavailable,
    BMIMEM_Preferences,
)


def register():
    global _DRAG_LISTENER_ENABLED, _DRAG_LISTENER_GENERATION
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    _DRAG_LISTENER_GENERATION += 1
    _DRAG_LISTENER_ENABLED = True
    if not bpy.app.background and not bpy.app.timers.is_registered(_ensure_drag_listeners):
        bpy.app.timers.register(_ensure_drag_listeners, first_interval=0.1, persistent=True)


def unregister():
    global _DRAG_LISTENER_ENABLED, _DRAG_LISTENER_GENERATION
    _DRAG_LISTENER_ENABLED = False
    _DRAG_LISTENER_GENERATION += 1
    if bpy.app.timers.is_registered(_ensure_drag_listeners):
        bpy.app.timers.unregister(_ensure_drag_listeners)
    _DRAG_LISTENER_WINDOWS.clear()
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
