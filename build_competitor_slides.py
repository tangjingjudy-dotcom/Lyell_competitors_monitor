# -*- coding: utf-8 -*-
"""
8页: zamto-cel(2)/KITE-753(2)/M9140(2)/IM96(2)
设计原则: 大图表·公司左·绝不重叠·大幅留白·纯手动矩形
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import OrderedDict
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from ppt_helpers import *

prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
pg = [0]
def fn(slide, section):
    pg[0] += 1
    add_footer(slide, section, pg[0])

# ═══ 布局常量: 所有元素在此范围内, 确保永无重叠 ═══
# 标题: y=0.33-1.35  |  KPI: y=1.55-2.15  |  内容: y=2.45-6.50  |  注释: y=6.70-7.00
COMPANY_LEFT  = Inches(0.50)   # 公司介绍左侧
COMPANY_W     = Inches(4.0)    # 公司介绍宽度
CHART_LEFT    = Inches(4.85)   # 图表区左侧
CHART_W       = Inches(7.8)    # 图表区宽度
CONTENT_TOP   = Inches(2.45)
CONTENT_BOT   = Inches(6.45)
CONTENT_H     = Inches(4.0)    # 主内容区高度
KPI_TOP       = Inches(1.55)
KPI_H         = Inches(0.58)

# ═══ 纯手绘条形图 (单组) ═══
def simple_bar(slide, x, y, w, h, bars, max_val=None, font_size=10):
    """bars: [(label, value, color)]  粗条 + 数值标签在右侧"""
    n = len(bars)
    gap = Inches(0.24)
    row_h = (h - gap * (n - 1)) / n
    lw = Inches(2.0)
    bw = w - lw - Inches(1.0)  # 条形区宽度
    if max_val is None:
        max_val = max(v for _, v, _ in bars) * 1.25 if bars else 100
    for i, (lb, val, clr) in enumerate(bars):
        ry = y + i * (row_h + gap)
        add_text(slide, x, ry, lw, row_h, lb, size=font_size, color=NAVY,
                 align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0)
        rect_w = max(Inches(0.02), bw * (val / max_val))
        add_rect(slide, x + lw + Inches(0.1), ry + row_h * 0.22, rect_w, row_h * 0.56, clr)
        add_text(slide, x + lw + Inches(0.15) + rect_w, ry + Inches(0.03), Inches(1.3), row_h,
                 f"{val:.1f}", size=font_size + 1, color=clr, bold=True,
                 anchor=MSO_ANCHOR.MIDDLE)

# ═══ 纯手绘分组条形图 ═══
def simple_grouped(slide, x, y, w, h, groups, series_dict, colors=None, max_val=None, fz=10):
    """
    groups: ["label1", "label2"]
    series_dict: OrderedDict(name->[val1,val2,...])
    纵向排列 group, 每个 group 内横向排列多系列 bar
    """
    ng = len(groups)
    ns = len(series_dict)
    gh = h / ng
    lw = Inches(2.0)
    area_w = w - lw
    s_keys = list(series_dict.keys())
    all_vals = [v for vs in series_dict.values() for v in vs]
    if max_val is None:
        max_val = max(all_vals) * 1.25 if all_vals else 100
    for gi, glb in enumerate(groups):
        gy_base = y + gi * gh
        add_text(slide, x, gy_base + gh * 0.1, lw, gh * 0.8, glb,
                 size=fz, color=NAVY, align=PP_ALIGN.RIGHT,
                 anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0)
        inner_h = gh / (ns + 1)
        inner_w = area_w * 0.8 / ns
        for si in range(ns):
            val = series_dict[s_keys[si]][gi]
            clr = (colors or [ACCENT, ACCENT_BLUE, ACCENT_RED, GRAY_SERIES])[si % 4]
            sx = x + lw + Inches(0.08) + si * (area_w / ns)
            rect_w = max(Inches(0.02), inner_w * (val / max_val))
            add_rect(slide, sx, gy_base + (si + 1) * inner_h + inner_h * 0.15,
                     rect_w, inner_h * 0.5, clr)
            add_text(slide, sx + rect_w + Inches(0.04), gy_base + (si + 1) * inner_h + inner_h * 0.1,
                     Inches(0.9), inner_h * 0.6, f"{val:.1f}", size=fz - 0.5, color=clr,
                     bold=True, anchor=MSO_ANCHOR.MIDDLE)

# ═══ 左侧公司介绍块 ═══
def company_block(slide, y, title, lines):
    """返回该块的底部 y"""
    add_text(slide, Inches(0.56), y, COMPANY_W - Inches(0.3), Inches(0.28),
             title, size=13, color=ACCENT, bold=True)
    add_rect(slide, Inches(0.56), y + Inches(0.30), Inches(2.5), Pt(1.5), ACCENT)
    body = "\n".join(lines)
    add_text(slide, Inches(0.56), y + Inches(0.42), COMPANY_W - Inches(0.3), Inches(2.0),
             body, size=10.5, color=GRAY_TEXT, line_spacing=1.28)
    return y + Inches(2.55)

# ═══ 右侧图表区标题 + 背景 ═══
def chart_section(slide, y, title_text):
    """画背景矩形, 返回可用区域的 (x,y,w,h) = 图表内部起始"""
    section_h = Inches(3.8)
    add_rect(slide, CHART_LEFT - Inches(0.05), y, CHART_W + Inches(0.1), section_h, BG_LIGHT)
    add_text(slide, CHART_LEFT, y + Inches(0.08), CHART_W, Inches(0.28),
             title_text, size=12, color=NAVY, bold=True)
    add_rect(slide, CHART_LEFT, y + Inches(0.38), CHART_W - Inches(0.2), Pt(1), BORDER_GRAY)
    return (CHART_LEFT + Inches(0.15), y + Inches(0.52), CHART_W - Inches(0.5), section_h - Inches(0.65))

# ═══ 右上角小标签 ═══
def tag_label(slide, x, y, text, color):
    add_rect(slide, x, y, Inches(0.06), Inches(0.22), color)
    add_text(slide, x + Inches(0.12), y, Inches(3.0), Inches(0.22),
             text, size=9.5, color=color, bold=True, anchor=MSO_ANCHOR.MIDDLE)


# ═══════════════════════════════════════════════════════════════
#  S1: zamto-cel 数据页
# ═══════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6]); slide_bg(s)
add_content_title(s, "zamto-cel (Miltenyi Biomedicine)  —  ronde-cel 主要竞品",
                  "tandem CD20-CD19 非冷冻 CAR-T  ·  DALY 2-EU 阳性随机 Ph2 (NCT04844866)  ·  2L LBCL 移植不适合人群")

add_kpi_cards(s, Inches(0.55), KPI_TOP, Inches(12.2), KPI_H,
              [("72%  ORR", "ITT (n=82)"), ("54%  CRR", ""),
               ("6.2月  EFS", "vs 2.5月化疗"), ("HR 0.39", "p<0.0001")],
              n_cols=4, gap=0.2, num_size=16, label_size=10, bg=BG_LIGHT)

# 左侧: 公司介绍
company_block(s, CONTENT_TOP,
              "Miltenyi Biomedicine",
              ["Miltenyi Biotec 旗下专注于细胞与基因治疗的子公司",
               "产品线覆盖血液瘤 CAR-T 和实体瘤",
               "zamto-cel 是其核心产品: 首个 tandem CD20-CD19 非冷冻 CAR-T",
               "",
               "核心技术特征:",
               "· 非冷冻新鲜输注, 12天制造, 14-16天 vein-to-vein",
               "· 双靶 (CD19+CD20) 降低抗原逃逸风险",
               "· DALY 2-EU 中位 74 岁, 67% III/IV 期, 均不适合移植"])

# 右侧: 柱状图对比 (两个纵向排列的 chart)
# Chart 区上半: ORR/CRR grouped bar
cx, cy, cw, ch = chart_section(s, CONTENT_TOP, "DALY 2-EU ITT 疗效对比")
h1 = (ch - Inches(0.3)) * 0.50
h2 = (ch - Inches(0.3)) * 0.42
add_text(s, cx, cy, cw * 0.7, Inches(0.2), "ORR / CRR (%)", size=10, color=NAVY, bold=True)
simple_grouped(s, cx, cy + Inches(0.22), cw * 0.7, h1 - Inches(0.22),
               ["ORR", "CRR"],
               OrderedDict([("zamto-cel", [72, 54]), ("R-GemOx", [45, 14]),
                            ("ronde-cel*", [65, 42])]),
               colors=[ACCENT, GRAY_SERIES, ACCENT_BLUE], max_val=100, fz=9.5)
add_note(s, cx, cy + h1 + Inches(0.04), cw * 0.7, Inches(0.12),
         "* ronde-cel 3L+ 非头对头, 仅供参考")

# Chart 区下半: EFS/PFS + 安全性
add_text(s, CHART_LEFT + Inches(0.15), cy + h1 + Inches(0.22), cw, Inches(0.2),
         "生存终点  ·  安全性", size=10, color=NAVY, bold=True)
bars_bottom = [
    ("EFS (月)", 6.2, ACCENT),
    ("PFS (月)", 8.5, ACCENT),
    ("Gr>=3 CRS (%)", 5.3, ACCENT_RED),
    ("Gr3 ICANS (%)", 1.3, ACCENT_RED),
]
simple_bar(s, cx, cy + h1 + Inches(0.45), cw, h2 - Inches(0.1),
           bars_bottom, max_val=12, font_size=9)
fn(s, "zamto-cel")


# ═══════════════════════════════════════════════════════════════
#  S2: zamto-cel 监管页
# ═══════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6]); slide_bg(s)
add_content_title(s, "zamto-cel: 监管进展与竞争位势",
                  "MAA 已提交 EMA  ·  计划提交其他监管机构  ·  2027H1 审评决定预期")

add_kpi_cards(s, Inches(0.55), KPI_TOP, Inches(12.2), KPI_H,
              [("EMA 审评中", "MAA 2025底提交"), ("2027 H1", "审评决定预期"),
               ("计划中", "其他监管机构"), ("首个", "CD19/CD20 双靶获批?")],
              n_cols=4, gap=0.2, num_size=16, label_size=10)

# 三个并排大卡片
cw = Inches(3.85)
cards = [
    ("1  前期成果", ACCENT_RED,
     "DALY 2-EU 达到主要终点 EFS\n"
     "EFS: 6.2 vs 2.5 月 (HR 0.39)\n"
     "PFS: 8.5 vs 3.3 月 (HR 0.43)\n"
     "ORR 72% · CRR 54%\n"
     "Gr>=3 CRS 5.3% · ICANS 1.3%\n"
     "中位年龄 74 岁 · IPI>=3: 57%"),
    ("2  监管路径", ACCENT,
     "2025年底 MAA 提交至 EMA\n"
     "计划提交美国/亚洲监管机构\n"
     "若获批: 首个 2L 老年高危\n"
     "LBCL 的 CAR-T 疗法\n"
     "对 ronde-cel 构成上市前\n"
     "直接竞争压力"),
    ("3  vs ronde-cel", ACCENT_BLUE,
     "ronde-cel PiNACLE Ph2\n"
     "数据预期: 2026Q4\n"
     "H2H Ph3 vs Yescarta\n"
     "进展预期: 2026Q4\n"
     "zamto-cel 可能先于 ronde-cel\n"
     "获批 2L LBCL"),
]
for i, (ttl, clr, bdy) in enumerate(cards):
    cx2 = Inches(0.45) + i * (cw + Inches(0.25))
    add_rect(s, cx2, CONTENT_TOP, cw, Inches(3.9), BG_LIGHT)
    add_rect(s, cx2, CONTENT_TOP, cw, Pt(3.5), clr)
    add_text(s, cx2 + Inches(0.15), CONTENT_TOP + Inches(0.1), cw - Inches(0.3), Inches(0.28),
             ttl, size=12, color=clr, bold=True)
    add_text(s, cx2 + Inches(0.15), CONTENT_TOP + Inches(0.45), cw - Inches(0.35), Inches(3.2),
             bdy, size=10, color=GRAY_TEXT, line_spacing=1.3)

# 底部时间线
add_rect(s, Inches(0.55), Inches(6.58), Inches(12.2), Pt(1), BORDER_GRAY)
add_text(s, Inches(0.55), Inches(6.68), Inches(12.2), Inches(0.35),
         "zamto-cel: DALY 2-EU数据(ASH 2025)  ▶  MAA提交(2025底)  ▶  EMA审评(H1 2027)  ▶  其他机构计划中\n"
         "Lyell: PiNACLE Ph2(2026Q4)  ▶  H2H Ph3进展(2026Q4)  ▶  PiNACLE关键读出(2027H1)  ▶  BLA(2027H2)",
         size=9.5, color=GRAY_LIGHT, line_spacing=1.4)
fn(s, "zamto-cel")


# ═══════════════════════════════════════════════════════════════
#  S3: KITE-753 数据页
# ═══════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6]); slide_bg(s)
add_content_title(s, "KITE-753 (Gilead/Kite)  —  ronde-cel 主要竞品",
                  "双靶 CD19/CD20 · 双共刺激域 CD28+4-1BB · KITE DuoCore 平台 · ASH 2025 口头报告(摘要#265)")

add_kpi_cards(s, Inches(0.55), KPI_TOP, Inches(12.2), KPI_H,
              [("79%  CR", "DL3 CAR-naive(n=14)"), ("0%", "Gr>=3 CRS/ICANS"),
               ("4.0月 FU", "中位随访"), ("Yescarta", "已上市2L CAR-T")],
              n_cols=4, gap=0.2, num_size=16, label_size=10)

company_block(s, CONTENT_TOP, "Gilead/Kite  —  CAR-T 在位者",
              ["已上市 CD19 CAR-T 产品:",
               "· Yescarta (axi-cel): LBCL 2L+ 获批",
               "· Tecartus (brexu-cel): MCL/ALL 获批",
               "",
               "KITE-753 新一代双靶 (CD19+CD20) 自体 CAR-T:",
               "· KITE DuoCore™: 两个独立CAR协同, 减少抗原逃逸",
               "· 新型制造工艺: 保留T细胞干性, 极低剂量强扩增",
               "· 同时开发 KITE-363 和 753 两种双靶候选",
               "· 753 仅用 1/10 剂量取得 79% CR + 0% 神经毒性"])

cx, cy, cw, ch = chart_section(s, CONTENT_TOP, "ASH 2025 Ph1: KITE-753 DL3 (0.2x10^6/kg)")
# 上半: CR/安全性
h1 = (ch - Inches(0.3)) * 0.55
simple_bar(s, cx, cy + Inches(0.05), cw, h1,
           [("CR 率", 79, ACCENT_RED),
            ("无 Gr>=3 CRS (全剂量)(%)", 97, ACCENT),
            ("无 Gr>=3 ICANS (全剂量)(%)", 100, ACCENT)],
           max_val=100, font_size=10)
add_note(s, cx, cy + h1 - Inches(0.05), cw, Inches(0.12),
         "注: Gr>=3 CRS 全剂量仅1例(1/30), 0例 Gr>=4 ;  桥接仅限激素+放疗, 输注时均有活动性疾病")

# 下半: KITE-753 vs KITE-363 对比
add_text(s, CHART_LEFT + Inches(0.15), cy + h1 + Inches(0.1), cw, Inches(0.2),
         "KITE-753 vs KITE-363 选择逻辑", size=10, color=NAVY, bold=True)
bars_compare = [
    ("KITE-753 DL3 CR (%)", 79, ACCENT_RED),
    ("KITE-363 最高剂量 CR (%)", 70, ACCENT_BLUE),
    ("KITE-753 剂量 (x10^6/kg)", 0.2, GRAY_SERIES),
    ("KITE-363 剂量 (x10^6/kg)", 2.0, GRAY_SERIES),
]
simple_bar(s, cx, cy + h1 + Inches(0.34), cw, ch - h1 - Inches(0.5), bars_compare, max_val=100, font_size=9)
fn(s, "KITE-753")


# ═══════════════════════════════════════════════════════════════
#  S4: KITE-753 Ph3 页
# ═══════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6]); slide_bg(s)
add_content_title(s, "KITE-753: Ph3 头对头试验与后续计划",
                  "NCT07479797  ·  vs Yescarta (axi-cel)  ·  1L 后 R/R LBCL  ·  2026-05-22 首例入组")

add_kpi_cards(s, Inches(0.55), KPI_TOP, Inches(12.2), KPI_H,
              [("2026-05-22", "Ph3 首例入组"), ("vs axi-cel", "头对头随机"),
               ("2027H2", "中期分析预期"), ("R/R LBCL", "1L 治疗后人群")],
              n_cols=4, gap=0.2, num_size=16, label_size=10)

cw = Inches(3.85)
cards = [
    ("1  前期选择过程", ACCENT_RED,
     "Ph1 伞式试验: 30例 753 + 37例 363\n"
     "KITE-753 DL3: CR 79% (11/14)\n"
     "全剂量 CAR-naive: CR 14/20\n"
     "KITE-363 最高剂量: >70% CR 持续\n"
     "17.5 月随访, CR 持久\n"
     "结论: 753 更低剂量+更好安全性"),
    ("2  Ph3 试验设计", ACCENT,
     "NCT07479797 · 2026-05-22 启动\n"
     "随机开放 · 753 vs axi-cel\n"
     "1L 后 R/R LBCL\n"
     "主要终点: PFS / CR\n"
     "目标: 证明优于现有标准\n"
     "Kite 是唯一在位者开发\n"
     "双靶竞品"),
    ("3  竞争位势分析", ACCENT_BLUE,
     "对 ronde-cel 的双重威胁:\n"
     "1) Yescarta (已上市单靶)\n"
     "2) KITE-753 (新一代双靶)\n"
     "在位者优势: 渠道/品牌/数据\n"
     "2027H2 中期读出是关键\n"
     "催化剂, 将决定市场格局"),
]
for i, (ttl, clr, bdy) in enumerate(cards):
    cx2 = Inches(0.45) + i * (cw + Inches(0.25))
    add_rect(s, cx2, CONTENT_TOP, cw, Inches(3.9), BG_LIGHT)
    add_rect(s, cx2, CONTENT_TOP, cw, Pt(3.5), clr)
    add_text(s, cx2 + Inches(0.15), CONTENT_TOP + Inches(0.1), cw - Inches(0.3), Inches(0.28),
             ttl, size=12, color=clr, bold=True)
    add_text(s, cx2 + Inches(0.15), CONTENT_TOP + Inches(0.45), cw - Inches(0.35), Inches(3.2),
             bdy, size=10, color=GRAY_TEXT, line_spacing=1.3)

add_rect(s, Inches(0.55), Inches(6.58), Inches(12.2), Pt(1), BORDER_GRAY)
add_text(s, Inches(0.55), Inches(6.68), Inches(12.2), Inches(0.32),
         "KITE-753: Ph1 ASH2025  ▶  Ph3 启动(2026.05)  ▶  中期分析(2027H2)  ▶  若积极则加速监管\n"
         "Lyell: PiNACLE Ph2(2026Q4)  ▶  H2H Ph3进展(2026Q4)  ▶  关键读出(2027H1)  ▶  BLA(2027H2)",
         size=9.5, color=GRAY_LIGHT, line_spacing=1.4)
fn(s, "KITE-753")


# ═══════════════════════════════════════════════════════════════
#  S5: M9140 数据页
# ═══════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6]); slide_bg(s)
add_content_title(s, "Precemtabart Tocentecan (Merck KGaA)  —  LYL273 主要竞品",
                  "全球首个 CEACAM5 ADC  ·  exatecan payload  ·  PROCEADE 系列试验")

add_kpi_cards(s, Inches(0.55), KPI_TOP, Inches(12.2), KPI_H,
              [("20.7%  cORR", "Ph1 (n=29)"), ("6.9月  mPFS", ""),
               ("NR  mOS", "中位FU 13.1月"), ("~90%", "mCRC CEACAM5+")],
              n_cols=4, gap=0.2, num_size=16, label_size=10)

company_block(s, CONTENT_TOP, "Merck KGaA  —  全球科技公司",
              ["拥有超过 350 年历史的全球科技企业",
               "医疗健康是核心业务板块之一",
               "CRC 领域 20+ 年研发经验",
               "",
               "CEACAM5: mCRC 理想靶点",
               "· ~90% mCRC 过表达 CEACAM5",
               "· 健康组织几乎不表达, 高选择性治疗窗口",
               "· 无需生物标记筛选 (universal approach)",
               "· M9140 是首个临床中的 CEACAM5 ADC"])

cx, cy, cw, ch = chart_section(s, CONTENT_TOP, "Ph1 PROCEADE-CRC-01: 疗效 vs LYL273 DL2 (非头对头)")
h1 = (ch - Inches(0.3)) * 0.48
# ORR / mPFS grouped
simple_grouped(s, cx, cy, cw * 0.7, h1,
               ["ORR (%)", "mPFS (月)"],
               OrderedDict([("M9140 Ph1", [20.7, 6.9]),
                            ("LYL273 DL2", [67, 7.8]),
                            ("TAS-102+Bev", [6, 5.6])]),
               colors=[ACCENT_RED, ACCENT_BLUE, GRAY_SERIES], max_val=100, fz=9.5)
add_note(s, cx, cy + h1, cw * 0.7, Inches(0.12),
         "M9140(ADC) vs LYL273(CAR-T) 机制不同, 非头对头 ·  标准疗法 TAS-102+Bev 作为背景参照")

# 下半: 安全性
add_text(s, CHART_LEFT + Inches(0.15), cy + h1 + Inches(0.16), cw, Inches(0.2),
         "Ph1 安全性 (100+ 例)", size=10, color=NAVY, bold=True)
bars_safety = [
    ("推荐剂量 2.8mg/kg Q3W", 0, ACCENT_RED),  # will draw as label
    ("中位随访 13.1 月", 0, ACCENT),
]
simple_bar(s, cx, cy + h1 + Inches(0.4), cw, ch - h1 - Inches(0.5),
           [("可预测可控安全性", 100, ACCENT),
            ("血液学毒性 (exatecan类)", 80, ACCENT_BLUE),
            ("mOS 未达到", 100, ACCENT_RED)],
           max_val=110, font_size=9)
fn(s, "M9140")


# ═══════════════════════════════════════════════════════════════
#  S6: M9140 Ph3 页
# ═══════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6]); slide_bg(s)
add_content_title(s, "M9140: PROCEADE-CRC-03 3期试验与市场影响",
                  "Precemtabart Tocentecan +- Bev vs TAS-102+Bev  ·  mCRC 后线全球注册")

add_kpi_cards(s, Inches(0.55), KPI_TOP, Inches(12.2), KPI_H,
              [("2026-05-06", "Ph3 首例给药"), ("~1020 例", "全球入组"),
               ("165 中心", "20 个国家"), ("2028H2", "关键读出预期")],
              n_cols=4, gap=0.2, num_size=16, label_size=10)

cw = Inches(3.85)
cards = [
    ("1  Ph3 试验设计", ACCENT_RED,
     "PROCEADE-CRC-03 (NCT07549412)\n"
     "随机开放: Precem-TcT +- Bev\n"
     "vs TAS-102 + Bev (标准疗法)\n"
     "mCRC 后线治疗\n"
     "~1020 例 · 165 中心 · 20 国\n"
     "2026-05-06 启动 · 主要终点: PFS"),
    ("2  vs LYL273", ACCENT,
     "M9140 优势:\n"
     "· ADC 静脉给药, 无需细胞制备\n"
     "· 标准化生产, 易于大规模推广\n"
     "· 90% mCRC 均适用\n"
     "LYL273 优势:\n"
     "· 可能更高 ORR\n"
     "· 一次输注, 持久缓解\n"
     "两者将在 mCRC 后线直接竞争"),
    ("3  时间线与影响", ACCENT_BLUE,
     "2026-2027: 全球入组推进\n"
     "2028H2: 关键数据读出\n"
     "若积极: M9140 可能先于\n"
     "LYL273 获批 mCRC 后线\n"
     "对 Lyell 影响:\n"
     "LYL273 需在 2027-2028 展示\n"
     "差异化疗效, 抢占先机"),
]
for i, (ttl, clr, bdy) in enumerate(cards):
    cx2 = Inches(0.45) + i * (cw + Inches(0.25))
    add_rect(s, cx2, CONTENT_TOP, cw, Inches(3.9), BG_LIGHT)
    add_rect(s, cx2, CONTENT_TOP, cw, Pt(3.5), clr)
    add_text(s, cx2 + Inches(0.15), CONTENT_TOP + Inches(0.1), cw - Inches(0.3), Inches(0.28),
             ttl, size=12, color=clr, bold=True)
    add_text(s, cx2 + Inches(0.15), CONTENT_TOP + Inches(0.45), cw - Inches(0.35), Inches(3.2),
             bdy, size=10, color=GRAY_TEXT, line_spacing=1.3)

add_rect(s, Inches(0.55), Inches(6.58), Inches(12.2), Pt(1), BORDER_GRAY)
add_text(s, Inches(0.55), Inches(6.68), Inches(12.2), Inches(0.32),
         "M9140: Ph1 PROCEADE-CRC-01  ▶  Ph3启动(2026-05-06)  ▶  全球入组(2026-2028)  ▶  关键读出(2028H2)\n"
         "Lyell: LYL273 DL3数据(2026Q4)  ▶  关键试验启动(2027H1)  ▶  TBD",
         size=9.5, color=GRAY_LIGHT, line_spacing=1.4)
fn(s, "M9140")


# ═══════════════════════════════════════════════════════════════
#  S7: IM96 数据页
# ═══════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6]); slide_bg(s)
add_content_title(s, "IM96 (Immunochina/艺妙神州)  —  LYL273 主要竞品",
                  "GUCY2C 靶向 CAR-T  ·  晚期消化道肿瘤  ·  已发表 JCO  ·  全球同靶点唯一竞品")

add_kpi_cards(s, Inches(0.55), KPI_TOP, Inches(12.2), KPI_H,
              [("26.3%  ORR", "全组 20 例"), ("40%  ORR", "最佳剂量 DL3"),
               ("JCO 已发表", "爬坡数据"), ("2024.12.15", "新 Ph1 启动")],
              n_cols=4, gap=0.2, num_size=16, label_size=10)

company_block(s, CONTENT_TOP, "Immunochina/北京艺妙神州",
              ["中国领先 CAR-T 研发企业, 专注实体瘤",
               "IM96 是其核心候选产品",
               "",
               "GUCY2C: mCRC 特异性靶点",
               "· LYL273 与 IM96 是全球仅有的两个 GUCY2C CAR-T",
               "· 两者形成直接同靶点竞争关系",
               "· IM96 已发表 JCO 20 例爬坡数据",
               "· 正常组织仅表达于肠道上皮顶端, 安全性窗口良好"])

cx, cy, cw, ch = chart_section(s, CONTENT_TOP, "IM96 剂量爬坡 ORR vs LYL273 DL2 (非头对头)")
h1 = (ch - Inches(0.3)) * 0.50
simple_bar(s, cx, cy + Inches(0.05), cw, h1,
           [("IM96 全组 (20例)(%)", 26.3, ACCENT_BLUE),
            ("IM96 DL3 最佳(%)", 40, ACCENT),
            ("LYL273 DL2 (6例)(%)", 67, ACCENT_RED),
            ("LYL273 DL3 预期(%)", 50, ACCENT_RED)],
           max_val=80, font_size=10)
add_note(s, cx, cy + h1, cw, Inches(0.12),
         "IM96 JCO 已发表;  LYL273 DL3 数据待 2026Q4 披露")

# 下半: 试验概况
add_text(s, CHART_LEFT + Inches(0.15), cy + h1 + Inches(0.20), cw, Inches(0.2),
         "正在进行的临床试验", size=10, color=NAVY, bold=True)
bars_trials = [
    ("NCT06718738 爬坡启动 (自2024.12.15)", 80, ACCENT),
    ("NCT05287165 CRC队列入组中", 70, ACCENT_BLUE),
    ("预计2026-2027数据读出", 60, ACCENT_RED),
]
simple_bar(s, cx, cy + h1 + Inches(0.44), cw, ch - h1 - Inches(0.55),
           bars_trials, max_val=100, font_size=9)
fn(s, "IM96")


# ═══════════════════════════════════════════════════════════════
#  S8: IM96 试验详情页
# ═══════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6]); slide_bg(s)
add_content_title(s, "IM96: 临床试验设计与数据读出预期",
                  "双试验并行: NCT06718738 (3+3 爬坡)  +  NCT05287165 (CRC 专用队列)")

add_kpi_cards(s, Inches(0.55), KPI_TOP, Inches(12.2), KPI_H,
              [("2024-12-15", "新 Ph1 爬坡启动"), ("12/20x10^8", "两个剂量组"),
               ("6-12 例", "CRC 队列入组"), ("28 天", "DLT 观察期")],
              n_cols=4, gap=0.2, num_size=16, label_size=10)

cw = Inches(3.85)
cards = [
    ("1  NCT06718738 (3+3 爬坡)", ACCENT_RED,
     "2024-12-15 启动 · 单中心开放\n"
     "改良 3+3 设计 · 两个剂量组:\n"
     "DL1: 12x10^8 · DL2: 20x10^8 CAR-T\n"
     "每组 3-6 例 · DLT 观察 28 天\n"
     "主要终点: 安全性/耐受性\n"
     "次要终点: ORR · PFS · RP2D"),
    ("2  NCT05287165 (CRC 队列)", ACCENT,
     "评估 IM96 在晚期消化系统肿瘤\n"
     "安全性与疗效 · 开放单臂\n"
     "计划入组 6-12 例晚期 CRC\n"
     "主要终点: ORR · PFS\n"
     "探索性: OS · 长期随访\n"
     "补充爬坡以外的疗效数据"),
    ("3  与 LYL273 竞争格局", ACCENT_BLUE,
     "LYL273 DL2 (6例): ORR 67%\n"
     "mPFS 7.8 月 · 数据积极\n"
     "DL3 数据: 预计 2026Q4\n"
     "IM96 已发表 JCO · 双试验推进\n"
     "两者最终 Ph1 数据将决定\n"
     "GUCY2C CAR-T 竞争格局"),
]
for i, (ttl, clr, bdy) in enumerate(cards):
    cx2 = Inches(0.45) + i * (cw + Inches(0.25))
    add_rect(s, cx2, CONTENT_TOP, cw, Inches(3.9), BG_LIGHT)
    add_rect(s, cx2, CONTENT_TOP, cw, Pt(3.5), clr)
    add_text(s, cx2 + Inches(0.15), CONTENT_TOP + Inches(0.1), cw - Inches(0.3), Inches(0.28),
             ttl, size=12, color=clr, bold=True)
    add_text(s, cx2 + Inches(0.15), CONTENT_TOP + Inches(0.45), cw - Inches(0.35), Inches(3.2),
             bdy, size=10, color=GRAY_TEXT, line_spacing=1.3)

add_rect(s, Inches(0.55), Inches(6.58), Inches(12.2), Pt(1), BORDER_GRAY)
add_text(s, Inches(0.55), Inches(6.68), Inches(12.2), Inches(0.32),
         "IM96: JCO发表(2024)  ▶  NCT05287165入组中  ▶  NCT06718738爬坡(2024-12-15启动)  ▶  数据读出(2026-2027)\n"
         "Lyell: LYL273 DL3(2026Q4)  ▶  关键试验启动(2027H1)  ·  IM96 和 LYL273 为 GUCY2C CAR-T 全球唯一竞品对",
         size=9.5, color=GRAY_LIGHT, line_spacing=1.4)
fn(s, "IM96")


# ═══════════════════════════════════════════════════════════════
out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "Lyell_竞品详情_8页_v3.pptx")
prs.save(out)
print(f"已生成: {out}")
print(f"共 {pg[0]} 页")
