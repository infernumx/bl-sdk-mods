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
slider_red = SliderOption("Red", value=255, min_value=0, max_value=255)
slider_green = SliderOption("Green", value=0, min_value=0, max_value=255)
slider_blue = SliderOption("Blue", value=0, min_value=0, max_value=255)
slider_alpha = SliderOption("Alpha", value=215, min_value=0, max_value=255)
slider_x = SliderOption("X", value=10, min_value=0, max_value=1000)
slider_y = SliderOption("Y", value=10, min_value=0, max_value=1000)
slider_size = SliderOption("Size", value=100, min_value=50, max_value=150)


@hook("WillowGame.WillowPlayerController:CanSaveGame")
def can_save_game(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> PreHookRet:
    if save_block is True:
        show_hud_message("AutoSave Blocker", "Attempted game-save blocked.")
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
    x = slider_x.value
    y = slider_y.value
    true_x = canvas.SizeX * (x / 1000)
    true_y = canvas.SizeX * (y / 1000)

    canvas.SetPos(true_x, true_y, 0)
    text = f"AutoSave Blocking: {save_block}"
    color = make_struct(
        "Color",
        r=slider_red.value,
        g=slider_green.value,
        b=slider_blue.value,
        a=slider_alpha.value,
    )

    canvas.SetDrawColorStruct(color)
    canvas.DrawText(
        text,
        False,
        slider_size.value / 100,
        slider_size.value / 100,
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
    # Workaround to disable text hook since it gets re-enabled regardless of the state of 'enable_text'
    if post_render.get_active_count() > 0 and enable_text.value is False:
        post_render.disable()
    elif enable_text.value is True:
        post_render.enable()


def on_mod_disable() -> None:
    post_render.disable()


text_settings = GroupedOption(
    "Text Settings",
    (
        slider_red,
        slider_green,
        slider_blue,
        slider_alpha,
        slider_x,
        slider_y,
        slider_size,
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
