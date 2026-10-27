"""Runtime discovery and non-destructive menu interception."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Callable, Iterable

import bpy


PACKAGE_NAME = __package__
IMPORT = "IMPORT"
EXPORT = "EXPORT"
UNGROUPED = "__UNGROUPED__"


def _preferences(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(PACKAGE_NAME)
    return addon.preferences if addon else None


def _menu_type(menu_kind: str):
    if menu_kind == IMPORT:
        return bpy.types.TOPBAR_MT_file_import
    return bpy.types.TOPBAR_MT_file_export


def _function_identity(callback: Callable) -> str:
    module = getattr(callback, "__module__", "unknown")
    qualname = getattr(callback, "__qualname__", getattr(callback, "__name__", "callback"))
    # Named callbacks keep the same identity if an add-on update moves their
    # source code. Lambdas/local closures need a line suffix to avoid collisions.
    if "<lambda>" in qualname or "<locals>" in qualname:
        code = getattr(callback, "__code__", None)
        line = getattr(code, "co_firstlineno", 0)
        return f"{module}:{qualname}:{line}"
    return f"{module}:{qualname}"


@dataclass
class RuntimeEntry:
    key: str
    menu_kind: str
    callback_id: str
    method: str
    action_id: str
    argument: str = ""
    default_label: str = ""
    kwargs: dict[str, Any] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)
    operator_context: str = "INVOKE_REGION_WIN"


class _OperatorPropertiesRecorder:
    __slots__ = ("_entry",)

    def __init__(self, entry: RuntimeEntry):
        object.__setattr__(self, "_entry", entry)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self._entry.properties[name] = value

    def __getattr__(self, name):
        return self._entry.properties.get(name)


class _RecordingLayout:
    """Small UILayout stand-in used to inspect menu callbacks safely."""

    _ACTION_METHODS = {
        "operator",
        "operator_menu_enum",
        "operator_enum",
        "operator_menu_hold",
        "menu",
    }

    def __init__(
        self,
        records: list[RuntimeEntry],
        menu_kind: str,
        callback_id: str,
        unsupported_calls: set[str] | None = None,
    ):
        object.__setattr__(self, "_records", records)
        object.__setattr__(self, "_menu_kind", menu_kind)
        object.__setattr__(self, "_callback_id", callback_id)
        object.__setattr__(
            self,
            "_unsupported_calls",
            unsupported_calls if unsupported_calls is not None else set(),
        )
        object.__setattr__(self, "operator_context", "INVOKE_REGION_WIN")
        object.__setattr__(self, "enabled", True)
        object.__setattr__(self, "active", True)
        object.__setattr__(self, "alert", False)
        object.__setattr__(self, "alignment", "EXPAND")
        object.__setattr__(self, "scale_x", 1.0)
        object.__setattr__(self, "scale_y", 1.0)
        object.__setattr__(self, "use_property_split", False)
        object.__setattr__(self, "use_property_decorate", True)

    def _child(self):
        child = _RecordingLayout(
            self._records,
            self._menu_kind,
            self._callback_id,
            self._unsupported_calls,
        )
        child.operator_context = self.operator_context
        child.enabled = self.enabled
        child.active = self.active
        return child

    def row(self, *args, **kwargs):
        return self._child()

    def column(self, *args, **kwargs):
        return self._child()

    def column_flow(self, *args, **kwargs):
        return self._child()

    def grid_flow(self, *args, **kwargs):
        return self._child()

    def box(self, *args, **kwargs):
        return self._child()

    def split(self, *args, **kwargs):
        return self._child()

    def menu_pie(self, *args, **kwargs):
        return self._child()

    def _record_action(self, method: str, action_id: str, argument: str, kwargs):
        same_action = sum(
            1
            for record in self._records
            if record.callback_id == self._callback_id
            and record.method == method
            and record.action_id == action_id
        )
        raw_key = (
            f"{self._menu_kind}|{self._callback_id}|{method}|"
            f"{action_id}|{argument}|{same_action}"
        )
        key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]
        entry = RuntimeEntry(
            key=key,
            menu_kind=self._menu_kind,
            callback_id=self._callback_id,
            method=method,
            action_id=action_id,
            argument=argument,
            default_label=_label_from_action(method, action_id, kwargs.get("text")),
            kwargs=dict(kwargs),
            operator_context=self.operator_context,
        )
        self._records.append(entry)
        return _OperatorPropertiesRecorder(entry)

    def operator(self, operator, *args, **kwargs):
        return self._record_action("operator", operator, "", kwargs)

    def operator_menu_enum(self, operator, property, *args, **kwargs):
        return self._record_action("operator_menu_enum", operator, property, kwargs)

    def operator_enum(self, operator, property, *args, **kwargs):
        # UILayout.operator_enum expands one operator into a button for every
        # enum value. Record each value separately so visibility, labels, and
        # ordering remain independently configurable.
        try:
            category, name = operator.split(".", 1)
            operator_rna = getattr(getattr(bpy.ops, category), name).get_rna_type()
            enum_property = operator_rna.properties[property]
            enum_items = tuple(enum_property.enum_items)
        except (AttributeError, KeyError, TypeError, ValueError):
            enum_items = ()

        if not enum_items:
            self._unsupported_calls.add(f"operator_enum:{operator}.{property}")
            return self._record_action("operator_enum", operator, property, kwargs)

        for enum_item in enum_items:
            identifier = str(enum_item.identifier)
            if not identifier:
                continue
            item_kwargs = dict(kwargs)
            item_kwargs.setdefault("text", str(enum_item.name))
            try:
                icon_value = int(getattr(enum_item, "icon", 0) or 0)
            except (TypeError, ValueError):
                icon_value = 0
            if icon_value:
                item_kwargs.setdefault("icon_value", icon_value)
            proxy = self._record_action(
                "operator_enum_item",
                operator,
                f"{property}:{identifier}",
                item_kwargs,
            )
            setattr(proxy, property, identifier)
        return None

    def operator_menu_hold(self, operator, menu, *args, **kwargs):
        return self._record_action("operator_menu_hold", operator, menu, kwargs)

    def menu(self, menu, *args, **kwargs):
        self._record_action("menu", menu, "", kwargs)

    def separator(self, *args, **kwargs):
        return None

    def separator_spacer(self, *args, **kwargs):
        return None

    def label(self, *args, **kwargs):
        self._unsupported_calls.add("label")
        return None

    def prop(self, *args, **kwargs):
        self._unsupported_calls.add("prop")
        return None

    def __getattr__(self, name):
        # Do not fail a complete menu because one add-on uses an unfamiliar
        # layout call, but surface the omission in Preferences instead of
        # silently losing UI.
        def ignored(*args, **kwargs):
            self._unsupported_calls.add(name)
            return self._child()

        return ignored


class _MenuRecorder:
    bl_owner_use_filter = False

    def __init__(self, layout):
        self.layout = layout


class _ManagedDrawList(list):
    """Store real callbacks while exposing only our renderer to Blender.

    Blender add-ons can continue to append, prepend, and remove their original
    functions normally because the underlying list is left intact. Iteration is
    the only behavior changed: Blender's dynamic menu wrapper sees one manager
    callback. Disabling this add-on swaps the ordinary callback list back in.
    """

    _bm_menu_manager = True

    def __init__(self, callbacks: Iterable[Callable], manager: Callable):
        super().__init__(callbacks)
        self.manager = manager

    def __iter__(self):
        return iter((self.manager,))

    def raw_callbacks(self) -> list[Callable]:
        return list(list.__iter__(self))


_RUNTIME_ENTRIES: dict[str, dict[str, RuntimeEntry]] = {IMPORT: {}, EXPORT: {}}
_DISCOVERY_ERRORS: dict[str, list[str]] = {IMPORT: [], EXPORT: []}


def _label_from_action(method: str, action_id: str, explicit_text) -> str:
    if explicit_text:
        return str(explicit_text)
    try:
        if method == "menu":
            menu_cls = getattr(bpy.types, action_id, None)
            return str(getattr(menu_cls, "bl_label", action_id))
        category, name = action_id.split(".", 1)
        return str(getattr(getattr(bpy.ops, category), name).get_rna_type().name)
    except Exception:
        return action_id


def _raw_callbacks(menu_kind: str) -> list[Callable]:
    draw = _menu_type(menu_kind).draw
    callbacks = getattr(draw, "_draw_funcs", None)
    if getattr(callbacks, "_bm_menu_manager", False):
        return callbacks.raw_callbacks()
    if callbacks is None:
        return [draw]
    return list(callbacks)


def _find_setting(prefs, key: str):
    for setting in prefs.entries:
        if setting.key == key:
            return setting
    return None


def synchronize(menu_kind: str, context=None):
    """Discover current callbacks and update persistent entry metadata."""
    prefs = _preferences(context)
    if prefs is None:
        return

    for setting in prefs.entries:
        if setting.menu_kind == menu_kind:
            setting.available = False
            setting.discovery_error = ""

    records: list[RuntimeEntry] = []
    errors: list[str] = []
    for callback in _raw_callbacks(menu_kind):
        callback_id = _function_identity(callback)
        unsupported_calls: set[str] = set()
        layout = _RecordingLayout(records, menu_kind, callback_id, unsupported_calls)
        try:
            callback(_MenuRecorder(layout), context or bpy.context)
        except Exception as exc:
            errors.append(f"{callback_id}: {type(exc).__name__}: {exc}")
        if unsupported_calls:
            calls = ", ".join(sorted(unsupported_calls))
            errors.append(f"{callback_id}: unsupported UILayout call(s): {calls}")

    runtime = {}
    for default_index, record in enumerate(records):
        runtime[record.key] = record
        setting = _find_setting(prefs, record.key)
        if setting is None:
            setting = prefs.entries.add()
            setting.key = record.key
            setting.menu_kind = menu_kind
            setting.visible = True
            setting.group_id = UNGROUPED
            setting.order = default_index * 10
            setting.order_customized = False
        elif not setting.order_customized:
            setting.order = default_index * 10
        setting.entry_kind = record.method
        setting.action_id = record.action_id
        setting.callback_id = record.callback_id
        setting.default_label = record.default_label
        setting.default_order = default_index * 10
        setting.available = True

    _RUNTIME_ENTRIES[menu_kind] = runtime
    _DISCOVERY_ERRORS[menu_kind] = errors


def synchronize_all(context=None):
    synchronize(IMPORT, context)
    synchronize(EXPORT, context)


def discovery_errors(menu_kind: str) -> tuple[str, ...]:
    return tuple(_DISCOVERY_ERRORS[menu_kind])


def _group_order(prefs, menu_kind: str) -> dict[str, int]:
    groups = sorted(
        (group for group in prefs.groups if group.menu_kind == menu_kind),
        key=lambda group: (group.order, group.uid),
    )
    return {group.uid: index for index, group in enumerate(groups)}


def sorted_settings(prefs, menu_kind: str, include_unavailable=False):
    group_order = _group_order(prefs, menu_kind)

    def sort_key(setting):
        if setting.group_id == UNGROUPED:
            group_rank = -1
        else:
            group_rank = group_order.get(setting.group_id, len(group_order) + 1)
        return (group_rank, setting.order, setting.default_order, setting.key)

    return sorted(
        (
            setting
            for setting in prefs.entries
            if setting.menu_kind == menu_kind
            and (include_unavailable or setting.available)
        ),
        key=sort_key,
    )


def _replay(layout, runtime_entry: RuntimeEntry, custom_label: str):
    kwargs = dict(runtime_entry.kwargs)
    if custom_label:
        kwargs["text"] = custom_label
    previous_context = layout.operator_context
    layout.operator_context = runtime_entry.operator_context
    try:
        if runtime_entry.method in {"operator", "operator_enum_item"}:
            props = layout.operator(runtime_entry.action_id, **kwargs)
        elif runtime_entry.method == "operator_menu_enum":
            props = layout.operator_menu_enum(
                runtime_entry.action_id, runtime_entry.argument, **kwargs
            )
        elif runtime_entry.method == "operator_enum":
            layout.operator_enum(runtime_entry.action_id, runtime_entry.argument)
            return
        elif runtime_entry.method == "operator_menu_hold":
            props = layout.operator_menu_hold(
                runtime_entry.action_id, runtime_entry.argument, **kwargs
            )
        elif runtime_entry.method == "menu":
            layout.menu(runtime_entry.action_id, **kwargs)
            return
        else:
            return
        for name, value in runtime_entry.properties.items():
            try:
                setattr(props, name, value)
            except (AttributeError, TypeError):
                pass
    finally:
        layout.operator_context = previous_context


def _draw_managed(menu_self, context, menu_kind: str):
    prefs = _preferences(context)
    if prefs is None:
        for callback in _raw_callbacks(menu_kind):
            callback(menu_self, context)
        return

    synchronize(menu_kind, context)
    runtime = _RUNTIME_ENTRIES[menu_kind]
    settings = [
        setting
        for setting in sorted_settings(prefs, menu_kind)
        if setting.visible and setting.key in runtime
    ]
    groups = {
        group.uid: group
        for group in prefs.groups
        if group.menu_kind == menu_kind
    }

    previous_group = None
    drew_anything = False
    for setting in settings:
        group_id = setting.group_id if setting.group_id in groups else UNGROUPED
        if group_id != previous_group and group_id != UNGROUPED:
            group = groups[group_id]
            if group.separator_before and drew_anything:
                menu_self.layout.separator()
            if group.show_header and group.name.strip():
                menu_self.layout.label(text=group.name.strip())
        runtime_entry = runtime[setting.key]
        try:
            _replay(menu_self.layout, runtime_entry, setting.custom_label.strip())
            drew_anything = True
        except Exception as exc:
            setting.discovery_error = f"{type(exc).__name__}: {exc}"
        previous_group = group_id


def _draw_import(menu_self, context):
    _draw_managed(menu_self, context, IMPORT)


def _draw_export(menu_self, context):
    _draw_managed(menu_self, context, EXPORT)


_MANAGERS = {IMPORT: _draw_import, EXPORT: _draw_export}


def activate():
    for menu_kind, manager in _MANAGERS.items():
        menu_cls = _menu_type(menu_kind)
        callbacks = menu_cls._dyn_ui_initialize()
        if getattr(callbacks, "_bm_menu_manager", False):
            callbacks.manager = manager
            continue
        menu_cls.draw._draw_funcs = _ManagedDrawList(callbacks, manager)
    synchronize_all()


def deactivate():
    for menu_kind in (IMPORT, EXPORT):
        menu_cls = _menu_type(menu_kind)
        callbacks = getattr(menu_cls.draw, "_draw_funcs", None)
        if getattr(callbacks, "_bm_menu_manager", False):
            menu_cls.draw._draw_funcs = callbacks.raw_callbacks()


def is_active() -> bool:
    for menu_kind in (IMPORT, EXPORT):
        callbacks = getattr(_menu_type(menu_kind).draw, "_draw_funcs", None)
        if not getattr(callbacks, "_bm_menu_manager", False):
            return False
    return True


def set_enabled(enabled: bool):
    if enabled:
        activate()
    else:
        deactivate()


def register():
    prefs = _preferences()
    set_enabled(bool(prefs and prefs.enabled))


def unregister():
    deactivate()
    _RUNTIME_ENTRIES[IMPORT].clear()
    _RUNTIME_ENTRIES[EXPORT].clear()
    _DISCOVERY_ERRORS[IMPORT].clear()
    _DISCOVERY_ERRORS[EXPORT].clear()
