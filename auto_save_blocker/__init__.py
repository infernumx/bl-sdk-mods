from typing import Any

from mods_base import (
    hook,
    keybind,
    build_mod,
    BoolOption,
    SliderOption,
    BaseOption,
    KeybindType,
    GroupedOption,
    HookType,
    Mod,
)
from mods_base.hook import PreHookRet
from ui_utils import show_hud_message
from unrealsdk import find_object, make_struct
from unrealsdk.unreal import (
    UObject,
    WrappedStruct,
    BoundFunction,
)
from unrealsdk.hooks import Block

__all__: tuple[str, ...] = ("hooks", "keybinds", "options")

save_block: bool = False
mod: Mod | None = None


@hook("WillowGame.WillowPlayerController:CanSaveGame")
def can_save_game(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> PreHookRet:
    if save_block is True:
        return (Block, False)
    return (Block, True)


@hook("WillowGame.WillowGameViewportClient:PostRender")
def post_render(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> PreHookRet:
    canvas = args.Canvas

    if canvas is None:
        return

    canvas.Font = find_object("Font", "UI_Fonts.Font_Willowbody_18pt")
    x = text_settings.children[4].value
    y = text_settings.children[5].value
    true_x = canvas.SizeX * (x / 1000)
    true_y = canvas.SizeX * (y / 1000)

    canvas.SetPos(true_x, true_y, 0)
    text = f"AutoSave Blocking: {save_block}"
    rgba = {col: opt.value for col, opt in zip("rgba", text_settings.children[:4])}
    color = make_struct("Color", **rgba)

    canvas.SetDrawColorStruct(color)
    canvas.DrawText(
        text,
        False,
        text_settings.children[6].value / 100,
        text_settings.children[6].value / 100,
    )


@keybind("Toggle AutoSave Blocker", key="F2")
def save_block_bind() -> None:
    global save_block
    save_block = not save_block
    show_hud_message("[AutoSave Blocker]", f"Set to {save_block}")


@BoolOption("Enable Text", value=True)
def enable_text(_: BoolOption, new_value: bool) -> None:
    if mod is None or not mod.is_enabled:
        return

    if new_value:
        post_render.enable()
    else:
        post_render.disable()


def on_mod_enable() -> None:
    post_render.enable()


def on_mod_disable() -> None:
    post_render.disable()


text_settings: GroupedOption = GroupedOption(
    "Text Settings",
    (
        SliderOption("Red", value=255, min_value=0, max_value=255),
        SliderOption("Green", value=0, min_value=0, max_value=255),
        SliderOption("Blue", value=0, min_value=0, max_value=255),
        SliderOption("Alpha", value=215, min_value=0, max_value=255),
        SliderOption("X", value=10, min_value=0, max_value=1000),
        SliderOption("Y", value=20, min_value=0, max_value=1000),
        SliderOption("Size", value=100, min_value=50, max_value=150),
    ),
)

hooks: tuple[HookType, ...] = (can_save_game, post_render)
keybinds: tuple[KeybindType, ...] = (save_block_bind,)
options: tuple[BaseOption, ...] = (enable_text, text_settings)

mod = build_mod(
    hooks=hooks,
    keybinds=keybinds,
    options=options,
    on_enable=on_mod_enable,
    on_disable=on_mod_disable,
)
