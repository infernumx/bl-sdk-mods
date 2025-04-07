from typing import Any  # type:ignore

from mods_base import (
    hook,
    keybind,
    build_mod,
    BoolOption,
    SliderOption,
    BaseOption,
    NestedOption,
    KeybindOption,
    HookType,
)  # type:ignore
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


@hook("WillowGame.WillowPlayerController:CanSaveGame")
def can_save_game(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> tuple[type[Block], bool] | bool:
    if save_block is True:
        return (Block, False)
    return True


@hook("WillowGame.WillowGameViewportClient:PostRender")
def post_render(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> bool:
    canvas = args.Canvas

    if not canvas:
        return True

    canvas.Font = find_object("Font", "UI_Fonts.Font_Willowbody_18pt")
    x = text_position.children[0].value
    y = text_position.children[1].value
    true_x = canvas.SizeX * (x / 1000)
    true_y = canvas.SizeX * (y / 1000)

    canvas.SetPos(true_x, true_y, 0)
    text = f"AutoSave Blocking: {save_block}"
    rgba = {col: opt.value for col, opt in zip("rgba", color_option.children)}
    color = make_struct("Color", **rgba)

    canvas.SetDrawColorStruct(color)
    canvas.DrawText(text, False, text_size.value / 100, text_size.value / 100)
    return True


@keybind("Toggle AutoSave Blocker", key="F2")
def save_block_bind() -> None:
    global save_block
    save_block = not save_block
    show_hud_message("[AutoSave Blocker]", f"Set to {save_block}")


def on_enable_text_toggled(option: BoolOption, value: bool) -> None:
    if value is True:
        post_render.enable()
    else:
        post_render.disable()


enable_text: BoolOption = BoolOption(
    "Enable Text", value=True, on_change=on_enable_text_toggled
)

color_option: NestedOption = NestedOption(
    "Text Color",
    [
        SliderOption("Red", value=255, min_value=0, max_value=255),
        SliderOption("Green", value=0, min_value=0, max_value=255),
        SliderOption("Blue", value=0, min_value=0, max_value=255),
        SliderOption("Alpha", value=215, min_value=0, max_value=255),
    ],
)

text_position: NestedOption = NestedOption(
    "Text Position",
    [
        SliderOption("X", value=10, min_value=0, max_value=1000),
        SliderOption("Y", value=20, min_value=0, max_value=1000),
    ],
)

text_size: SliderOption = SliderOption(
    "Text Size", value=100, min_value=50, max_value=150
)

hooks: tuple[HookType, ...] = (can_save_game, post_render)
keybinds: tuple[KeybindOption, ...] = (save_block_bind,)
options: tuple[BaseOption, ...] = (enable_text, color_option, text_position, text_size)

build_mod(hooks=hooks, keybinds=keybinds, options=options)
