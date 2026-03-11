# -*- coding: utf-8 -*-
"""
材料知识库

提供材料深度分析所需的背景知识，包括：
1. 黏土材料结构和性质
2. 酸体系特性
3. 质子传导机理知识
4. 经典文献结论

更新日期: 2026-01-26
"""

from typing import Dict, List, Optional, Any


# ============================================================
# 黏土材料详细信息
# ============================================================

CLAY_DETAILED_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "Sepiolite": {
        "chinese_name": "海泡石",
        "formula": "Mg8Si12O30(OH)4·8H2O",
        "crystal_system": "斜方晶系",
        "structure": {
            "description": "纤维状纳米管结构，由连续的四面体-八面体-四面体(TOT)层组成",
            "channel_dimension": "0.37×1.06 nm (椭圆形孔道)",
            "pore_type": "微孔+介孔双峰分布",
            "features": [
                "一维纳米孔道，直径约0.5 nm",
                "高比表面积（200-400 m²/g）",
                "大量硅羟基(Si-OH)和镁羟基(Mg-OH)",
                "可吸附水分子形成结构水",
            ]
        },
        "surface_chemistry": {
            "surface_groups": ["Si-OH (硅醇)", "Mg-OH (镁醇)", "结构水"],
            "surface_charge": "边缘带正电，基面带负电",
            "IEP_pH": 7.0,  # 等电点
            "CEC_meq_100g": 20,  # 阳离子交换容量
        },
        "physical_properties": {
            "pore_diameter_nm": 0.5,
            "surface_area_m2_g": 300,
            "pore_volume_cm3_g": 0.4,
            "density_g_cm3": 2.1,
            "thermal_stability_C": 400,
        },
        "confinement_effect": {
            "description": "强纳米限域效应",
            "mechanisms": [
                "孔道内分子运动受限",
                "氢键网络有序化",
                "水分子取向排列",
                "降低玻璃化转变温度",
            ],
            "proton_conduction": "有利于低温质子传导，通过packed-acid机制",
        },
        "literature_references": [
            "Wang et al., Adv. Mater. 2022 - AiCE系统",
            "Kreuer 2004, Chem. Rev. - 质子传导机理",
        ]
    },
    
    "Halloysite": {
        "chinese_name": "埃洛石",
        "formula": "Al2Si2O5(OH)4·nH2O",
        "crystal_system": "单斜晶系",
        "structure": {
            "description": "卷曲管状结构，由1:1型硅酸盐层卷曲形成",
            "channel_dimension": "内径10-30 nm，外径40-70 nm",
            "pore_type": "管内空腔+管间孔隙",
            "features": [
                "纳米管状形貌",
                "管内外化学性质不同",
                "管内Al-OH，管外Si-O-Si",
                "可通过负载改性",
            ]
        },
        "surface_chemistry": {
            "surface_groups": ["内表面Al-OH", "外表面Si-OH", "边缘Al-OH/Si-OH"],
            "surface_charge": "内正外负",
            "IEP_pH": 2.5,
            "CEC_meq_100g": 8,
        },
        "physical_properties": {
            "pore_diameter_nm": 15,
            "surface_area_m2_g": 50,
            "pore_volume_cm3_g": 0.2,
            "density_g_cm3": 2.5,
            "thermal_stability_C": 500,
        },
        "confinement_effect": {
            "description": "中等纳米限域效应",
            "mechanisms": [
                "管内客体分子限域",
                "可调控管内化学环境",
                "管壁-客体相互作用",
            ],
            "proton_conduction": "管内酸可形成连续质子通道",
        },
        "literature_references": [
            "埃洛石纳米管综述文献",
        ]
    },
    
    "Bentonite": {
        "chinese_name": "膨润土",
        "formula": "(Na,Ca)0.33(Al,Mg)2(Si4O10)(OH)2·nH2O",
        "crystal_system": "单斜晶系",
        "structure": {
            "description": "2:1型层状硅酸盐，具有可膨胀层间",
            "channel_dimension": "层间距0.96-2.0 nm (取决于水化程度)",
            "pore_type": "层间孔+边缘孔",
            "features": [
                "可插层膨胀",
                "高阳离子交换容量",
                "强吸水性",
                "层间离子可交换",
            ]
        },
        "surface_chemistry": {
            "surface_groups": ["层间水", "边缘Al-OH/Si-OH", "交换性阳离子"],
            "surface_charge": "层面负电，边缘pH依赖",
            "IEP_pH": 2.5,
            "CEC_meq_100g": 80,
        },
        "physical_properties": {
            "pore_diameter_nm": 1.2,
            "surface_area_m2_g": 80,
            "pore_volume_cm3_g": 0.15,
            "density_g_cm3": 2.35,
            "thermal_stability_C": 500,
        },
        "confinement_effect": {
            "description": "层间限域效应",
            "mechanisms": [
                "层间水分子限域",
                "离子水合层结构",
                "层间隙可调控",
            ],
            "proton_conduction": "层间质子传导，可能存在Vehicle机制",
        },
        "literature_references": [
            "蒙脱石/膨润土综述",
        ]
    },
    
    "Kaolin": {
        "chinese_name": "高岭土",
        "formula": "Al2Si2O5(OH)4",
        "crystal_system": "三斜晶系",
        "structure": {
            "description": "1:1型层状硅酸盐，层间氢键稳定",
            "channel_dimension": "层间距约0.7 nm (不膨胀)",
            "pore_type": "主要为晶粒间孔",
            "features": [
                "层间氢键强",
                "不膨胀",
                "化学稳定性好",
                "相对惰性",
            ]
        },
        "surface_chemistry": {
            "surface_groups": ["Si-OH", "Al-OH", "边缘羟基"],
            "surface_charge": "弱负电",
            "IEP_pH": 3.5,
            "CEC_meq_100g": 5,
        },
        "physical_properties": {
            "pore_diameter_nm": 0.7,
            "surface_area_m2_g": 20,
            "pore_volume_cm3_g": 0.05,
            "density_g_cm3": 2.6,
            "thermal_stability_C": 600,
        },
        "confinement_effect": {
            "description": "弱限域效应",
            "mechanisms": [
                "主要是表面吸附",
                "晶粒间限域",
            ],
            "proton_conduction": "主要依赖表面酸导电",
        },
        "literature_references": [
            "高岭石相关文献",
        ]
    },
}


# ============================================================
# 酸体系详细信息
# ============================================================

ACID_DETAILED_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "H3PO4": {
        "chinese_name": "磷酸",
        "formula": "H3PO4",
        "pKa_values": [2.15, 7.20, 12.35],
        "structure": {
            "description": "四面体结构，一个P原子与四个O原子配位",
            "hydrogen_bonding": "可形成多重氢键网络",
            "features": [
                "三元酸，可多级解离",
                "与水互溶",
                "粘度较高",
                "低蒸气压",
            ]
        },
        "proton_conduction": {
            "mechanisms": [
                "Grotthuss机制：质子沿氢键网络跳跃",
                "Vehicle机制：H3O+或H2PO4-整体迁移",
                "Packed-acid机制：酸-酸氢键链传导",
            ],
            "typical_Ea_eV": {
                "Grotthuss": "< 0.3 eV",
                "Vehicle": "> 0.4 eV",
                "Packed-acid": "0.2-0.4 eV",
            },
            "temperature_dependence": {
                "high_T": "Grotthuss主导，低Ea",
                "low_T": "氢键重排变慢，Ea升高；Vehicle可能被冻结",
            }
        },
        "confinement_behavior": {
            "description": "在纳米孔道中可形成有序的酸-酸链",
            "key_findings": [
                "Nature Chem 2012: 磷酸体系主要是Grotthuss机制",
                "Chem. Sci. 2014: Packed-acid机制，水不需要动",
                "AiCE: -82°C仍有导电，证明非Vehicle主导",
            ]
        },
        "literature_consensus": """
磷酸质子传导机理的最新共识（基于44篇2020-2025文献）:
1. 主要是Grotthuss机制，同位素效应显著
2. Packed-acid机制在高浓度/限域条件下有效
3. 低温时不是Vehicle主导，而是Grotthuss重排受限
""",
    },
    
    "H2SO4": {
        "chinese_name": "硫酸",
        "formula": "H2SO4",
        "pKa_values": [-3, 1.99],
        "structure": {
            "description": "四面体结构，S原子与四个O原子配位",
            "hydrogen_bonding": "强氢键能力",
            "features": [
                "强酸，几乎完全解离",
                "强吸水性",
                "粘度低于磷酸",
                "可能腐蚀某些基质",
            ]
        },
        "proton_conduction": {
            "mechanisms": [
                "解离生成大量H+",
                "HSO4-参与质子传导",
            ],
            "typical_Ea_eV": {
                "typical": "0.1-0.3 eV",
            },
            "temperature_dependence": {
                "high_T": "高离子浓度，导电性好",
                "low_T": "冻结后导电性急剧下降",
            }
        },
        "confinement_behavior": {
            "description": "在限域环境中可能降低腐蚀性",
            "key_findings": [
                "高离子浓度有利于传导",
                "需要关注对黏土结构的影响",
            ]
        },
        "literature_consensus": """
硫酸体系特点:
1. 强酸，离子浓度高
2. 但冻结点相对较高
3. 可能腐蚀铝硅酸盐结构
""",
    },
    
    "Phytic": {
        "chinese_name": "植酸",
        "formula": "C6H18O24P6",
        "pKa_values": [1.1, 2.4, 5.8, 6.3, 9.4, 12.0],  # 六个磷酸基团
        "structure": {
            "description": "环己六醇的六磷酸酯",
            "hydrogen_bonding": "六个磷酸基团可形成复杂氢键网络",
            "features": [
                "六元酸",
                "可形成交联网络",
                "与金属离子络合",
                "生物来源，绿色安全",
            ]
        },
        "proton_conduction": {
            "mechanisms": [
                "多磷酸基团协同传导",
                "可能形成三维质子网络",
            ],
            "typical_Ea_eV": {
                "typical": "0.2-0.5 eV",
            },
            "temperature_dependence": {
                "high_T": "网络灵活，传导好",
                "low_T": "网络刚化，传导下降",
            }
        },
        "confinement_behavior": {
            "description": "在孔道中可能形成有序排列",
            "key_findings": [
                "多磷酸基团提供多个质子源",
                "可与黏土表面相互作用",
            ]
        },
        "literature_consensus": """
植酸体系特点:
1. 多官能团酸，结构复杂
2. 可能形成独特的传导网络
3. 研究相对较少，机理待深入探索
""",
    },
}


# ============================================================
# 质子传导机理知识
# ============================================================

PROTON_MECHANISM_KNOWLEDGE: Dict[str, Any] = {
    "Grotthuss": {
        "chinese_name": "Grotthuss机制 / 结构扩散",
        "description": "质子通过氢键网络跳跃传导，不需要载体分子整体移动",
        "characteristics": [
            "典型Ea: < 0.3 eV（但低温可能更高）",
            "需要氢键网络存在",
            "不需要分子大位移",
            "H/D同位素效应显著",
        ],
        "conditions": [
            "氢键网络连续",
            "适当的氢键强度（不能太强或太弱）",
            "分子可旋转重定向",
        ],
        "temperature_effect": {
            "high_T": "氢键重排快，Ea低",
            "low_T": "氢键重排慢，Ea升高，但通道仍存在",
        },
    },
    
    "Vehicle": {
        "chinese_name": "Vehicle机制 / 载体扩散",
        "description": "质子随载体分子（如H3O+、H2PO4-）整体扩散",
        "characteristics": [
            "典型Ea: > 0.4 eV",
            "需要分子平移运动",
            "受粘度影响大",
            "低温下容易被冻结",
        ],
        "conditions": [
            "载体分子可自由移动",
            "介质粘度不能太高",
            "温度高于某个阈值",
        ],
        "temperature_effect": {
            "high_T": "载体分子可移动，Vehicle可行",
            "low_T": "载体分子冻结，Vehicle关闭",
        },
    },
    
    "Packed_acid": {
        "chinese_name": "Packed-acid机制",
        "description": "酸-酸氢键链上的质子传导，是Grotthuss的一种",
        "characteristics": [
            "典型Ea: 0.2-0.4 eV",
            "不需要水参与",
            "水可以不动",
            "在高酸浓度或限域条件下有效",
        ],
        "conditions": [
            "高酸浓度",
            "酸-酸接触形成链",
            "限域空间有利于形成",
        ],
        "temperature_effect": {
            "high_T": "链重排快",
            "low_T": "链重排慢但仍可导电",
        },
        "evidence": [
            "²H NMR显示水分子静止但质子仍传导",
            "AiCE在-82°C仍有导电（σ=0.023 mS/cm）",
        ],
    },
}


# ============================================================
# EIS曲线形态知识
# ============================================================

EIS_MORPHOLOGY_KNOWLEDGE: Dict[str, Any] = {
    "semicircle": {
        "chinese_name": "半圆",
        "typical_cause": "电荷转移/界面电阻",
        "interpretation": [
            "高频半圆：晶界/界面电阻",
            "低频半圆：电极过程",
            "Rb可从半圆与实轴交点读取",
        ],
        "temperature_trend": "低温时半圆变大（电阻增加）",
    },
    
    "linear_tail": {
        "chinese_name": "直线尾",
        "typical_cause": "Warburg扩散/离子扩散受限",
        "interpretation": [
            "45°倾斜：经典Warburg扩散",
            "陡峭（>45°）：受限扩散",
            "低频出现",
        ],
        "temperature_trend": "高温时更明显（扩散控制）",
    },
    
    "nearly_linear": {
        "chinese_name": "类直线（室温）",
        "typical_cause": "电阻很小，扩散控制主导",
        "interpretation": [
            "Rb很小，半圆被压缩",
            "高电导率样品常见",
            "可能是好性能的标志",
        ],
        "temperature_trend": "室温/高温常见",
    },
    
    "semicircle_plus_tail": {
        "chinese_name": "半圆+直线（低温）",
        "typical_cause": "电阻增大，电荷转移和扩散都可见",
        "interpretation": [
            "低温时电阻增加，半圆显现",
            "Rb从半圆读取",
            "扩散过程仍存在",
        ],
        "temperature_trend": "低温时常见",
    },
}


# ============================================================
# Arrhenius分段解释
# ============================================================

ARRHENIUS_SEGMENTATION_KNOWLEDGE: Dict[str, Any] = {
    "single_segment": {
        "interpretation": "单一传导机制主导全温区",
        "typical_materials": "简单体系，机制单一",
        "notes": "较少见于复杂限域体系",
    },
    
    "two_segments": {
        "interpretation": "高温和低温存在不同主导机制",
        "possible_causes": [
            "机制转变（如Grotthuss→限域Grotthuss）",
            "相变（如水结晶）",
            "玻璃化转变",
        ],
        "breakpoint_meaning": "转变温度，具有物理意义",
    },
    
    "multiple_segments": {
        "interpretation": "多个温区存在不同行为",
        "possible_causes": [
            "多重机制/相转变",
            "界面效应",
            "多孔结构贡献",
        ],
        "notes": "需要仔细分析每个拐点的物理意义",
    },
    
    "Ea_increase_on_cooling": {
        "interpretation": "低温Ea升高",
        "possible_causes": [
            "氢键重排能垒升高（Grotthuss减速）",
            "但不一定是Vehicle主导",
            "限域环境中packed-acid机制可能接管",
        ],
        "caution": "不要机械套用'高Ea=Vehicle'",
    },
    
    "Ea_decrease_on_cooling": {
        "interpretation": "低温Ea降低（较少见）",
        "possible_causes": [
            "可能是量子效应",
            "隧穿贡献",
            "数据质量问题",
        ],
        "notes": "需要仔细验证数据",
    },
}


# ============================================================
# 辅助函数
# ============================================================

def get_clay_knowledge(clay_type: str) -> Dict[str, Any]:
    """获取黏土材料知识"""
    return CLAY_DETAILED_KNOWLEDGE.get(clay_type, {})


def get_acid_knowledge(acid_type: str) -> Dict[str, Any]:
    """获取酸体系知识"""
    return ACID_DETAILED_KNOWLEDGE.get(acid_type, {})


def get_mechanism_knowledge(mechanism: str) -> Dict[str, Any]:
    """获取传导机理知识"""
    return PROTON_MECHANISM_KNOWLEDGE.get(mechanism, {})


def build_knowledge_prompt_section(material_id: str, clay_type: str, acid_type: str) -> str:
    """
    构建知识库提示词段落
    
    用于材料深度分析的背景知识注入
    """
    clay_info = get_clay_knowledge(clay_type)
    acid_info = get_acid_knowledge(acid_type)
    
    lines = [
        "## 材料知识背景（用于机理分析参考）",
        "",
        f"### 黏土基材: {clay_type} ({clay_info.get('chinese_name', '')})",
        f"- 分子式: {clay_info.get('formula', 'N/A')}",
    ]
    
    # 结构信息
    structure = clay_info.get('structure', {})
    if structure:
        lines.append(f"- 结构描述: {structure.get('description', 'N/A')}")
        lines.append(f"- 孔道尺寸: {structure.get('channel_dimension', 'N/A')}")
        if structure.get('features'):
            lines.append("- 结构特点:")
            for f in structure['features']:
                lines.append(f"  - {f}")
    
    # 物理性质
    phys = clay_info.get('physical_properties', {})
    if phys:
        lines.append(f"- 孔径: {phys.get('pore_diameter_nm', 'N/A')} nm")
        lines.append(f"- 比表面积: {phys.get('surface_area_m2_g', 'N/A')} m²/g")
    
    # 限域效应
    confinement = clay_info.get('confinement_effect', {})
    if confinement:
        lines.append(f"- 限域效应: {confinement.get('description', 'N/A')}")
        lines.append(f"- 质子传导: {confinement.get('proton_conduction', 'N/A')}")
    
    lines.append("")
    lines.append(f"### 酸体系: {acid_type} ({acid_info.get('chinese_name', '')})")
    lines.append(f"- 分子式: {acid_info.get('formula', 'N/A')}")
    
    # 质子传导
    pc = acid_info.get('proton_conduction', {})
    if pc:
        lines.append("- 传导机制:")
        for m in pc.get('mechanisms', []):
            lines.append(f"  - {m}")
    
    # 限域行为
    cb = acid_info.get('confinement_behavior', {})
    if cb:
        lines.append(f"- 限域行为: {cb.get('description', 'N/A')}")
    
    # 文献共识
    consensus = acid_info.get('literature_consensus', '')
    if consensus:
        lines.append("")
        lines.append("### 文献共识")
        lines.append(consensus.strip())
    
    return "\n".join(lines)


# 测试
if __name__ == "__main__":
    # 测试知识库提示词生成
    prompt_section = build_knowledge_prompt_section("S8", "Sepiolite", "H3PO4")
    print(prompt_section)
