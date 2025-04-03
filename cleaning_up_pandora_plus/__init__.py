from typing import Any  # type:ignore

from unrealsdk import find_object, construct_object, make_struct
from mods_base import (
    get_pc,
    hook,
    keybind,
    build_mod,
    KeybindOption,
    HookType,
    BaseOption,
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
can_swap: bool = True


@keybind("Sell Keybind")
def sell_bind() -> None:
    pc = get_pc()
    if is_client(pc):
        return

    seen_item = pc.CurrentSeenPickupable

    # Filter out unsellable items
    if seen_item.Inventory.Class.Name in ("WillowUsableItem", "WillowMissionItem"):
        return

    if seen_item.bPickupable is True:
        inventory_manager = pc.GetPawnInventoryManager()
        item_value = seen_item.Inventory.MonetaryValue
        seen_item.SetPickupability(False)  # Disable user's ability to pick up item
        seen_item.PickupShrinkDuration = 0.5
        seen_item.BeginShrinking()  # Delete item
        pc.PlayerSoldItem(0, item_value)  # Add money of sold item to player
        inventory_manager.ClientConditionalIncrementPickupStats(
            seen_item.Inventory
        )  # Increase BAR pickup stats
        _update_buyback(inventory_manager, seen_item.Inventory)
        _play_sell_sound(pc)
        show_hud_message("Cleaning Up Pandora+", f"Sold for ${item_value}")


def is_client(pc: UObject) -> bool:
    # List of all roles and their enums
    # 0 - None
    # 1 - SimulatedProxy
    # 2 - AutonomousProxy
    # 3 - Authority
    # 4 - MAX
    return pc.Role < 3


def keep_alive(obj: UObject) -> None:
    obj.ObjectFlags |= 0x4000


def _play_sell_sound(pc: UObject) -> None:
    global VENDOR_SELL_AUDIO
    if VENDOR_SELL_AUDIO is None:
        VENDOR_SELL_AUDIO = find_object(
            "AkEvent", "Ake_UI.UI_Vending.Ak_Play_UI_Vending_Sell"
        )
        keep_alive(VENDOR_SELL_AUDIO)
    pc.Pawn.PlayAkEvent(VENDOR_SELL_AUDIO)


def _update_buyback(inventory_manager, sold_item) -> None:
    buyback = [entry for entry in inventory_manager.BuyBackInventory]
    # Clones the item we just sold and puts it in buyback inventory
    buyback.append(
        sold_item.CreateClone()
    ) 
    if len(buyback) > 20:
        buyback.pop(0)

    inventory_manager.BuyBackInventory = buyback


@hook("WillowGame.WillowPlayerController:SawPickupable")
def on_seen_item(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> bool:
    global can_swap
    base_icon = find_object(
        "InteractionIconDefinition", "GD_InteractionIcons.Default.Icon_DefaultUse"
    )
    icon = construct_object(
        "InteractionIconDefinition",
        base_icon.Outer,
        name="SecondaryUse",
        flags=0x4000,
        template_obj=base_icon,
    )

    icon.Icon = 4  # Dollar sign icon
    icon.Action = ""
    icon.Text = f"[{sell_bind.key}] SELL ITEM"

    InteractionIconWithOverrides = make_struct(
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

    seen_item_type = args.Pickup.Inventory.Class.Name

    # Checks the type of item the player is looking at to make sure its something sellable
    if seen_item_type in ("WillowUsableItem", "WillowMissionItem"):
        return True

    hudMovie = obj.GetHUDMovie()
    # This fixes an error that is caused when looking at a pickupable directly after closing the inventory
    if hudMovie is None:
        return True

    hudMovie.ShowToolTip(InteractionIconWithOverrides, 1)  # Show the tooltip in the hud
    if obj.PlayerInput.bUsingGamepad is True:
        # Because the Secondary Use Key on controller is the same as swap weapons, we need to restrict the ability to swap when looking at a pickupable object
        can_swap = False
    return True


@hook("WillowGame.StatusMenuInventoryPanelGFxObject:NormalInputKey")
def on_use_backpack(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> bool:
    pc = get_pc()
    inventory_manager = pc.GetPawnInventoryManager()

    if pc.PlayerInput.bUsingGamepad is False:
        if args.ukey != sell_bind.key:
            return True
    elif "Start" not in str(args.ukey):
        return True

    if args.Uevent == 0:
        selected_item = obj.GetSelectedThing()

        # Plays an error sound if player tries to sell an item that is either equipped or favorited
        if (
            (selected_item is None)
            or (obj.bInEquippedView is True)
            or (selected_item.GetMark() == 2)
        ):
            obj.ParentMovie.PlayUISound("ResultFailure")

        item_value = selected_item.GetMonetaryValue()

        obj.BackpackPanel.SaveState()  # Saves the current index of the item you are hovering
        pc.PlayerSoldItem(0, item_value)
        inventory_manager.RemoveInventoryFromBackpack(selected_item)
        show_hud_message("Cleaning Up Pandora+", f"Sold for ${item_value}")
        _update_buyback(
            inventory_manager, selected_item
        )  # Updates vendor buyback inventory
        _play_sell_sound(pc)

    return True


_pending_final_tooltip: str = ""


@hook("WillowGame.StatusMenuInventoryPanelGFxObject:set_tooltip_text")
def set_tooltip_text(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> str:
    global _pending_final_tooltip
    pc = get_pc()
    _pending_final_tooltip = ""
    bind_key = ""

    # Only show updated tooltip when looking at the backpack as you cannot delete items that are equipped
    if obj.bInEquippedView is True:
        return True

    # Use user-set bind key if the user is not on console
    if pc.PlayerInput.bUsingGamepad is False and sell_bind.key is not None:
        bind_key = f"[{sell_bind.key}]"
    elif pc.PlayerInput.bUsingGamepad is True:
        bind_key = "<IMG src='xbox360_Start' vspace='-3'>"

    if bind_key != "":
        _pending_final_tooltip = f"{bind_key} Sell Item"
        adjust_tooltip.enable()


@hook(
    "WillowGame.StatusMenuInventoryPanelGFxObject:set_tooltip_text",
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
    original_markup: str
    if ret is Unset:
        with prevent_hooking_direct_calls():
            original_markup = func(args)
    else:
        original_markup = ret

    with prevent_hooking_direct_calls():
        final_sell_markup: str = func(_pending_final_tooltip)

    # If another function added it's own tooltips to a new line, just add ours on the end
    if "\n" in original_markup:
        return Block, original_markup + "    " + final_sell_markup

    return Block, original_markup + "\n" + final_sell_markup


@hook("WillowGame.WillowPlayerController:ClearSeenPickupable")
def on_lookaway(*_: Any) -> bool:
    global can_swap
    can_swap = (
        True  # Allows the player to swap weapons after looking away from a pickupable
    )
    return True


@hook("WillowGame.WillowPlayerController:NextWeapon")
def on_swap(*_: Any) -> bool:
    return can_swap  # Controls the players ability to swap weapons


hooks: tuple[HookType, ...] = (
    on_swap,
    on_lookaway,
    set_tooltip_text,
    on_use_backpack,
    on_seen_item,
)
keybinds: tuple[KeybindOption, ...] = (sell_bind,)

build_mod(hooks=hooks, keybinds=keybinds)
