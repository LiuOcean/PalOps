from paledit.box_plan import build_box_plan


def test_box_plan_has_14_unique_boxes_and_fits_capacity() -> None:
    plans = build_box_plan()
    assert len(plans) == 14
    assert len({plan.container_id for plan in plans}) == 14
    assert len({plan.label for plan in plans}) == 14
    assert all(plan.label.startswith("物资箱-") for plan in plans)
    assert all(0 < len(plan.items) <= 54 for plan in plans)
    assert sum(len(plan.items) for plan in plans) == 370

    by_label = {plan.label: dict(plan.items) for plan in plans}
    assert "WorldTreeOre" in by_label["物资箱-高级矿石"]
    assert {
        "Wood", "Stone", "Fiber", "Wool", "Cloth", "Leather", "Bone", "Horn",
        "Charcoal", "Gunpowder2", "MachineParts",
        "Bio_Battery", "Thermal_Core", "Wood_Fine", "Cloth2", "HighGrade_Processed_Wood",
        "Bio_Coolant", "Wood_WorldTree", "SkyislandIngot", "Corrosive_Solvent",
        "FireOrgan", "IceOrgan", "ElectricOrgan", "Venom", "PalFluid",
    } <= set(by_label["物资箱-加工材料"])
    assert {
        "PalSphere", "PalSphere_Mega", "PalSphere_Giga", "PalSphere_Tera", "PalSphere_Master",
        "PalSphere_Legend", "PalSphere_Ultimate", "PalSphere_Exotic", "PalSphere_Robbery",
        "PalSphere_Ancient_1", "PalSphere_Ancient_2",
    } <= set(by_label["物资箱-捕捉货币"])
    assert by_label["物资箱-捕捉货币"]["Money"] == 999999
    assert by_label["物资箱-捕捉货币"]["DogCoin"] == 999999
    assert len(by_label["物资箱-高级物品"]) == 54
    assert {
        "PalSummon_YakushimaBoss002", "PalSummon_YakushimaBoss002_2",
    } <= set(by_label["物资箱-Raid石板"])
    assert {
        "Cake", "Carbonara", "Cheeseburger_2", "Curry", "DeerLocoMoco", "Pizza",
        "Salad", "Yakisoba",
    } <= set(by_label["物资箱-高级物品"])


def test_box_plan_uses_only_unique_items() -> None:
    item_ids = [item_id for plan in build_box_plan() for item_id, _ in plan.items]
    assert len(item_ids) == len(set(item_ids))
