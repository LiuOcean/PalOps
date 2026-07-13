from __future__ import annotations

from dataclasses import dataclass

from .items import load_item_index


@dataclass(frozen=True)
class BoxPlan:
    container_id: str
    label: str
    items: tuple[tuple[str, int], ...]


BOXES = (
    ("00000000-0000-0000-0000-000000000202", "物资箱-高级物品"),
    ("00000000-0000-0000-0000-000000000201", "物资箱-高级矿石"),
    ("00000000-0000-0000-0000-000000000203", "物资箱-加工材料"),
    ("00000000-0000-0000-0000-000000000204", "物资箱-捕捉货币"),
    ("00000000-0000-0000-0000-000000000205", "物资箱-通用培养"),
    ("00000000-0000-0000-0000-000000000206", "物资箱-战斗植入"),
    ("00000000-0000-0000-0000-000000000207", "物资箱-工作植入"),
    ("00000000-0000-0000-0000-000000000208", "物资箱-工作适性"),
    ("00000000-0000-0000-0000-000000000209", "物资箱-技能果实-AF"),
    ("00000000-0000-0000-0000-000000000210", "物资箱-技能果实-FR"),
    ("00000000-0000-0000-0000-000000000211", "物资箱-技能果实-RW"),
    ("00000000-0000-0000-0000-000000000212", "物资箱-Raid石板"),
    ("00000000-0000-0000-0000-000000000213", "物资箱-武器图纸"),
    ("00000000-0000-0000-0000-000000000214", "物资箱-防具扩展"),
)

HIGH_VALUE = (
    "WingGlider_Fuel", "LuxuryMedicines", "MindControlDrug", "Potion_Extreme",
    "Narcotic", "MushroomJuice", "StatusPointResetSan", "Supplement", "PalRevive",
    "Elixir_hp_02", "Elixir_stamina_02", "Elixir_attack_02", "Elixir_workspeed_02",
    "Elixir_weight_02", "Elixir_hp_Yakushima", "Homeward", "WorldTreeHolyWater",
    "TechnologyBook_G3", "AncientTechnologyBook_G1", "RepairKit", "AncientParts2",
    "PalCrystal_Ex", "PredatorCrystal", "MeteorDrop", "AncientParts3", "PalDarkParts",
    "BaconEggs", "BLT", "Cake", "Carbonara", "CheeseBurger", "Cheeseburger_2",
    "ChickenSaute", "Chowder", "Curry", "DeerLocoMoco", "DeerStew", "Eaglestew",
    "FriedChicken", "FriedKelpie", "GenghisKhan", "Gratin", "GrilledSheepHerbs",
    "Gyoza", "Hamburger_2", "HotDog_2", "MeatAndPotatoes", "Minestrone",
    "MushroomSoup", "MushroomStew", "OctopusGirl_Takoyaki2", "Pizza", "Salad",
    "Yakisoba",
)
ORES = (
    "CopperOre", "Coal", "Sulfur", "Quartz", "CrudeOil", "Chromium", "RainbowCrystal",
    "ManganeseOre", "SkyIslandOre", "NightStone", "WorldTreeOre",
)
PROCESSED = (
    "Wood", "Stone", "Fiber", "Wool", "Cloth", "Leather", "Bone", "Horn",
    "Charcoal", "Gunpowder2", "MachineParts",
    "CopperIngot", "IronIngot", "StealIngot", "Plastic", "StainlessSteel",
    "ManganeseIngot", "YakushimaIngot001", "WorldTreeIngot", "Polymer", "CarbonFiber",
    "MachineParts2", "Computer", "AIcore", "Cement", "PalOil", "Pal_crystal_S",
    "Bio_Battery", "Thermal_Core", "Wood_Fine", "Cloth2", "HighGrade_Processed_Wood",
    "Bio_Coolant", "Wood_WorldTree", "SkyislandIngot", "Corrosive_Solvent",
    "FireOrgan", "IceOrgan", "ElectricOrgan", "Venom", "PalFluid",
)
CAPTURE = (
    "PalSphere", "PalSphere_Mega", "PalSphere_Giga", "PalSphere_Tera", "PalSphere_Master",
    "PalSphere_Legend", "PalSphere_Ultimate", "PalSphere_Exotic", "PalSphere_Robbery",
    "PalSphere_Ancient_1", "PalSphere_Ancient_2", "DogCoin", "BattleTicket", "Money",
    "TreasureBoxKey01", "TreasureBoxKey02", "TreasureBoxKey03",
)
TRAINING = (
    "Rankup_Arbitrary", "PalUpgradeStone4", "ExpBoost_04", "AffectionFruit_01",
    "Fruit_hp_01", "Fruit_attack_01", "Fruit__defense_01", "PalGenderReverse",
)
COMBAT_IMPLANTS = (
    "PalPassiveSkillChange_Consumable_WorldTree_ATK_DEF",
    "PalPassiveSkillChange_Consumable_WorldTree_ATK",
    "PalPassiveSkillChange_Consumable_WorldTree_DEF",
    "PalPassiveSkillChange_Consumable_EternalFlame",
    "PalPassiveSkillChange_Consumable_Invader",
    "PalPassiveSkillChange_Consumable_Vampire",
    "PalPassiveSkillChange_Consumable_Witch",
    "PalPassiveSkillChange_Consumable_Salvation",
    "PalPassiveSkillChange_Consumable_MutationPal_Immortal",
    "PalPassiveSkillChange_Consumable_MutationPal_ExplosionResist",
    "PalPassiveSkillChange_Consumable_MutationPal_Mutant",
    "PalPassiveSkillChange_Consumable_Rare",
)
WORK_IMPLANTS = (
    "PalPassiveSkillChange_Consumable_WorldTree_MoveSpeed",
    "PalPassiveSkillChange_Consumable_Stamina_Up_3",
    "PalPassiveSkillChange_Consumable_RideJumpCount_Increase2",
    "PalPassiveSkillChange_Consumable_SwimSpeed_up_3",
    "PalPassiveSkillChange_Consumable_WorldTree_CraftSpeed",
    "PalPassiveSkillChange_Consumable_WorldTree_FullStomach",
    "PalPassiveSkillChange_Consumable_WorldTree_Sanity",
    "PalPassiveSkillChange_Consumable_MutationPal_Babysitter",
    "PalPassiveSkillChange_Consumable_Nushi",
)
WORK_TICKETS = (
    "WorkSuitability_AddTicket_Collection", "WorkSuitability_AddTicket_Cool",
    "WorkSuitability_AddTicket_Deforest", "WorkSuitability_AddTicket_EmitFlame",
    "WorkSuitability_AddTicket_GenerateElectricity", "WorkSuitability_AddTicket_Handcraft",
    "WorkSuitability_AddTicket_Mining", "WorkSuitability_AddTicket_MonsterFarm",
    "WorkSuitability_AddTicket_ProductMedicine", "WorkSuitability_AddTicket_Seeding",
    "WorkSuitability_AddTicket_Transport", "WorkSuitability_AddTicket_Watering",
)
RAID = (
    "PalSummon_NightLady", "PalSummon_NightLady_Parts", "PalSummon_NightLady_Dark",
    "PalSummon_NightLady_Dark_Parts", "PalSummon_NightLady_Dark_2",
    "PalSummon_NightLady_Dark_Parts_2", "PalSummon_KingBahamut_Dragon",
    "PalSummon_KingBahamut_Dragon_Parts", "PalSummon_KingBahamut_Dragon_2",
    "PalSummon_KingBahamut_Dragon_Parts_2", "PalSummon_DarkMechaDragon",
    "PalSummon_DarkMechaDragon_Parts", "PalSummon_DarkMechaDragon_2",
    "PalSummon_DarkMechaDragon_Parts_2", "PalSummon_LegendDeer",
    "PalSummon_LegendDeer_Parts", "PalSummon_LegendDeer_2", "PalSummon_LegendDeer_Parts_2",
    "PalSummon_YakushimaBoss002", "PalSummon_YakushimaBoss002_2",
)


def _blueprints(index: dict[str, dict[str, object]], terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(
        item_id for item_id in index
        if item_id.startswith("Blueprint_") and item_id.endswith("_5")
        and any(term in item_id for term in terms)
    ))[:54]


def build_box_plan() -> tuple[BoxPlan, ...]:
    index = {str(row["id"]): row for row in load_item_index()["items"]}
    skills = sorted(item_id for item_id in index if item_id.startswith("SkillCard_"))
    if len(skills) != 93:
        raise ValueError(f"技能果实数量已变化：预期 93，实际 {len(skills)}")
    weapons = _blueprints(index, (
        "Rifle", "Shotgun", "Gun", "Launcher", "Cannon", "Bow", "Sword", "Blade", "Spear",
    ))
    armor = _blueprints(index, ("Armor", "Helmet", "HeadEquip", "Accessory", "Shield"))
    groups = (
        HIGH_VALUE, ORES, PROCESSED, CAPTURE, TRAINING, COMBAT_IMPLANTS, WORK_IMPLANTS,
        WORK_TICKETS, tuple(skills[:31]), tuple(skills[31:62]), tuple(skills[62:]), RAID,
        weapons, armor,
    )
    missing = sorted({item_id for group in groups for item_id in group if item_id not in index})
    if missing:
        raise ValueError(f"计划包含未知道具：{', '.join(missing)}")
    return tuple(BoxPlan(container_id, label, tuple(
        (item_id, 999999 if item_id in {"Money", "DogCoin"} else
         99 if item_id.startswith(("SkillCard_", "Blueprint_")) else
         999 if item_id.startswith(("PalPassiveSkillChange_", "WorkSuitability_", "PalSummon_"))
         or item_id in {"AncientParts2", "PredatorCrystal", "MeteorDrop"} else 9999)
        for item_id in group
    )) for (container_id, label), group in zip(BOXES, groups, strict=True))
