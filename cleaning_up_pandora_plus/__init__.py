from typing import Any  # type:ignore

from unrealsdk import find_object, construct_object, make_struct
from mods_base import (
    get_pc,
    hook,
    keybind,
    build_mod,
    KeybindOption,
    HookType,
)  # type:ignore
from ui_utils import show_hud_message
from unrealsdk.unreal import (
    UObject,
    WrappedStruct,
    BoundFunction,
)
from unrealsdk.hooks import (
    Block,
    Type,
    Unset,
    prevent_hooking_direct_calls,
)  # type:ignore


__all__: tuple[str, ...] = (
    "hooks",
    "keybinds",
)


VENDOR_SELL_AUDIO: UObject | None = None
_pending_final_tooltip: str = ""

type WillowInventory = UObject
type WillowInventoryManager = UObject
type WillowPlayerController = UObject


def _is_client(pc: WillowPlayerController) -> bool:
    # List of all roles and their enums
    # 0 - None
    # 1 - SimulatedProxy
    # 2 - AutonomousProxy
    # 3 - Authority
    # 4 - MAX
    return pc.Role < 3


def _play_sell_sound(pc: WillowPlayerController) -> None:
    global VENDOR_SELL_AUDIO
    if VENDOR_SELL_AUDIO is None:
        VENDOR_SELL_AUDIO = find_object(
            "AkEvent", "Ake_UI.UI_Vending.Ak_Play_UI_Vending_Sell"
        )
        VENDOR_SELL_AUDIO.ObjectFlags |= 0x4000  # Keep Alive flag
    pc.Pawn.PlayAkEvent(VENDOR_SELL_AUDIO)


def _get_sell_bind(pc: WillowPlayerController) -> str:
    if sell_bind.key is not None:
        return sell_bind.key

    # Use secondary action keybind as default if user has unset custom keybind
    return sell_bind.default_key


@hook("WillowGame.WillowPlayerController:SawPickupable")
def on_seen_item(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> bool:

    pc: WillowPlayerController = get_pc()
    base_icon: UObject = find_object(
        "InteractionIconDefinition", "GD_InteractionIcons.Default.Icon_DefaultUse"
    )
    icon: UObject = construct_object(
        "InteractionIconDefinition",
        base_icon.Outer,
        name="SecondaryUse",
        flags=0x4000,
        template_obj=base_icon,
    )

    icon.Icon = 4  # Dollar sign icon
    icon.Action = ""
    icon.Text = f"[{_get_sell_bind(pc)}] SELL ITEM"

    InteractionIconWithOverrides: UObject = make_struct(
        "InteractionIconWithOverrides",
        IconDef=icon,
        OverrideIconDef=None,
        bOverrideIcon=False,
        bOverrideAction=False,
        bOverrideText=False,
        bCostsToUse=0,
        CostsCurrencyType=0,
        CostsAmount=0,
    )

    seen_item_type: str = args.Pickup.Inventory.Class.Name

    # Checks the type of item the player is looking at to make sure its something sellable
    if seen_item_type in ("WillowUsableItem", "WillowMissionItem"):
        return True

    hudMovie = obj.GetHUDMovie()
    # This fixes an error that is caused when looking at a pickupable directly after closing the inventory
    if hudMovie is None:
        return True

    hudMovie.ShowToolTip(InteractionIconWithOverrides, 1)  # Show the tooltip in the hud
    return True


@hook("WillowGame.StatusMenuInventoryPanelGFxObject:SetTooltipText")
def set_tooltip_text(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> str:
    global _pending_final_tooltip

    pc: WillowPlayerController = get_pc()
    bind_key: str = ""

    # Reset any previous tooltip
    _pending_final_tooltip = ""

    # Only show updated tooltip when looking at the backpack as you cannot delete items that are equipped
    if obj.bInEquippedView is True:
        return True

    # Use user-set bind key if the user is not on console
    if pc.PlayerInput.bUsingGamepad is False:
        bind_key = f"[{_get_sell_bind(pc)}]"

    if bind_key != "":
        _pending_final_tooltip = f"{bind_key} Sell Item"
        adjust_tooltip.enable()


@hook(
    "WillowGame.StatusMenuInventoryPanelGFxObject:SetTooltipText",
    Type.POST_UNCONDITIONAL,
)
def stop_adjust_tooltip(*_: Any) -> None:
    adjust_tooltip.disable()


@hook("GFxUI.GFxMoviePlayer:ResolveDataStoreMarkup")
def adjust_tooltip(
    _obj: UObject,
    args: WrappedStruct,
    ret: Any,
    func: BoundFunction,
) -> tuple[type[Block], str]:
    global _pending_final_tooltip
    original_markup: str

    # Assuming some other UI markup is being ran unrelated to backpack tooltips
    if _pending_final_tooltip == "" and ret is not Unset:
        return Block, ret

    if ret is Unset:
        with prevent_hooking_direct_calls():
            original_markup = func(args)
    else:
        original_markup = ret

    with prevent_hooking_direct_calls():
        final_sell_markup: str = func(_pending_final_tooltip)
        _pending_final_tooltip = ""

    # If another function added it's own tooltips to a new line, just add ours on the end
    if "\n" in original_markup:
        return Block, original_markup + "    " + final_sell_markup

    return Block, original_markup + "\n" + final_sell_markup


@keybind("Sell Keybind", key="Backslash")
def sell_bind() -> None:
    pc: WillowPlayerController = get_pc()
    if _is_client(pc):
        return

    seen_item: WillowInventory = pc.CurrentSeenPickupable

    if seen_item is None:
        return

    # Filter out unsellable items
    if seen_item.Inventory.Class.Name in ("WillowUsableItem", "WillowMissionItem"):
        return

    if seen_item.bPickupable is True:
        inventory_manager: WillowInventoryManager = pc.GetPawnInventoryManager()
        item_inv: WillowInventory = seen_item.Inventory
        item_inv_cpy: WillowInventory = item_inv.CreateClone()
        item_value: int = item_inv.MonetaryValue

        # Slight workaround by throwing a temporary copy into the player's backpack and using it to 'sell' to update vendor buyback properly
        item_inv_cpy.Owner = inventory_manager.Owner
        inventory_manager.AddInventoryToBackpack(item_inv_cpy)
        inventory_manager.PlayerSoldItem(item_inv_cpy, 1)
        inventory_manager.UpdateBackpackInventoryCount()

        # Increase BAR pickup stats
        inventory_manager.ClientConditionalIncrementPickupStats(item_inv)

        seen_item.SetPickupability(False)
        seen_item.PickupShrinkDuration = 0.5
        seen_item.BeginShrinking()  # Delete item
        _play_sell_sound(pc)
        show_hud_message("Cleaning Up Pandora+", f"Sold for ${item_value:,}")


@hook("WillowGame.StatusMenuInventoryPanelGFxObject:NormalInputKey")
def on_use_backpack(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> bool:
    pc: WillowPlayerController = get_pc()
    inventory_manager: WillowInventoryManager = pc.GetPawnInventoryManager()

    # Filter out button non-keybind presses in backpack
    if pc.PlayerInput.bUsingGamepad is False:
        if args.ukey != _get_sell_bind(pc):
            return False

    # Only process on key press, uevent == 1 is key release
    if args.uevent == 0:
        selected_item: WillowInventory = obj.GetSelectedThing()
        print("on_use_backpack:", selected_item.GetMark())

        # Plays an error sound if player tries to sell an item that is either equipped or favorited
        if (
            (selected_item is None)
            or (obj.bInEquippedView is True)
            or (selected_item.GetMark() == 2)
        ):
            obj.ParentMovie.PlayUISound("ResultFailure")
            obj.FlourishEquip("Error: Item is favorited.")
            return False

        item_value: int = selected_item.GetMonetaryValue()

        obj.BackpackPanel.SaveState()  # Saves the current index of the item you are hovering
        inventory_manager.PlayerSoldItem(selected_item, 1)
        inventory_manager.UpdateBackpackInventoryCount()
        obj.ParentMovie.RefreshInventoryScreen(True)
        obj.BackpackPanel.RestoreState()
        obj.FlourishEquip(f"+${item_value:,}")
        _play_sell_sound(pc)

    return True


hooks: tuple[HookType, ...] = (
    set_tooltip_text,
    on_use_backpack,
    on_seen_item,
)
keybinds: tuple[KeybindOption, ...] = (sell_bind,)

build_mod(hooks=hooks, keybinds=keybinds)
