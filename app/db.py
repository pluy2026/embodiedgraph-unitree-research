from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.scoring import corroboration_points

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "mvp_snapshot.json"
DB_PATH = ROOT / "data" / "embodiedgraph.db"

RELATION_SEEDS = [
    ("hesai", "supplier", "confirmed", "双方确认", "e4"), ("robosense", "supplier", "probable", "测试验证", "e13"), ("wolong", "supplier", "unverified", "接触或送样", "e17"), ("orbbec", "supplier", "unverified", "接触或送样", "e18"), ("moons", "supplier", "unverified", "接触或送样", "e19"), ("inspire", "supplier", "confirmed", "双方确认", "e20"), ("livox", "supplier", "probable", "测试验证", "e23"),
    ("speedikon", "customer", "confirmed", "双方确认", "e2"), ("cctv", "customer", "confirmed", "双方确认", "e3"), ("geely", "customer", "confirmed", "测试验证", "e14"), ("eth-zurich", "customer", "confirmed", "测试验证", "e15"), ("ucsd", "customer", "confirmed", "测试验证", "e16"), ("cmu", "customer", "confirmed", "测试验证", "e21"), ("mit-csail", "customer", "confirmed", "测试验证", "e22"),
    ("nvidia", "partner", "confirmed", "双方确认", "e1"), ("sharpa", "partner", "confirmed", "双方确认", "e1"), ("robosense", "partner", "confirmed", "双方确认", "e13"), ("lightwheel", "partner", "probable", "测试验证", "e14"), ("gwm", "partner", "confirmed", "双方确认", "e24"), ("gmo-air", "partner", "confirmed", "双方确认", "e25"), ("star-plus", "partner", "confirmed", "双方确认", "e26"),
    ("meituan", "investor_or_investee", "confirmed", "双方确认", "e12"), ("jingshi", "investor_or_investee", "confirmed", "双方确认", "e12"), ("sourcecode", "investor_or_investee", "confirmed", "双方确认", "e12"), ("scvc", "investor_or_investee", "confirmed", "双方确认", "e12"), ("rongyi", "investor_or_investee", "confirmed", "双方确认", "e12"), ("dunhong", "investor_or_investee", "confirmed", "双方确认", "e12"), ("ciif", "investor_or_investee", "confirmed", "双方确认", "e12"),
    ("agibot", "peer", "probable", "市场传闻", "e6"), ("ubtech", "peer", "probable", "市场传闻", "e11"), ("fourier", "peer", "probable", "市场传闻", "e6"), ("figure", "peer", "probable", "市场传闻", "e6"), ("xiaomi", "peer", "probable", "市场传闻", "e8"), ("leju", "peer", "probable", "市场传闻", "e28"),
]

PUBLISHER_ALIASES = {
    "NVIDIA Newsroom": "NVIDIA",
    "NVIDIA Developer": "NVIDIA",
    "NVIDIA Blog": "NVIDIA",
}

# Multiple URLs can reproduce one underlying financing event or market report.
# Keep all citations visible, but do not turn repeated coverage into false
# corroboration in the confidence score.
EVIDENCE_ORIGIN_GROUPS = {
    "e12": "unitree-b2-financing-2024",
    "e29": "unitree-b2-financing-2024",
    "e30": "unitree-b2-financing-2024",
    "e31": "omdia-humanoid-shipments-2025",
    "e32": "omdia-humanoid-shipments-2025",
}

EXTRA_EVIDENCE_BY_RELATION = {
    ("investor_or_investee", "meituan"): ["e29", "e30", "e34"],
    ("investor_or_investee", "jingshi"): ["e29", "e30", "e35"],
    ("investor_or_investee", "sourcecode"): ["e29", "e30"],
    ("investor_or_investee", "scvc"): ["e29"],
    ("investor_or_investee", "rongyi"): ["e29"],
    ("investor_or_investee", "dunhong"): ["e29"],
    ("investor_or_investee", "ciif"): ["e29"],
    ("peer", "agibot"): ["e31", "e32"],
    ("peer", "ubtech"): ["e31", "e32"],
    ("peer", "fourier"): ["e32"],
    ("peer", "figure"): ["e33"],
}

# This snapshot studies public industrial relationships, but it must not blur
# the difference between a listed issuer, an affiliate of a listed issuer and
# an independent fund manager.  In particular, a disclosed financing event is
# not automatically proof that the investor itself is a listed company.
INVESTMENT_SCOPE_CLASSES = {
    "meituan": "listed_issuer_or_group",
    "jingshi": "listed_group_affiliate",
    "sourcecode": "nonlisted_capital_record",
    "scvc": "nonlisted_capital_record",
    "rongyi": "nonlisted_capital_record",
    "dunhong": "nonlisted_capital_record",
    "ciif": "nonlisted_capital_record",
}

INVESTMENT_SCOPE_NOTES = {
    "meituan": "上市公司/集团关联口径：美团（3690.HK）关联主体的历史融资记录；可用于“关联上市公司”覆盖。",
    "jingshi": "上市公司关联口径：实际投资主体为中信金石/金石成长基金，中信金石是中信证券全资私募基金子公司；可作为“中信证券关联投资主体”呈现，不能表述为中信证券直接出资。",
    "sourcecode": "非上市资本结构记录：源码资本是投资机构；保留其历史融资事实，但不计入“关联上市公司”覆盖。",
    "scvc": "非上市资本结构记录：深创投是国有创投集团，不因国资背景而视为上市公司；不计入“关联上市公司”覆盖。",
    "rongyi": "非上市资本结构记录：容亿相关基金/管理人未获得上市主体识别；不计入“关联上市公司”覆盖。",
    "dunhong": "非上市资本结构记录：敦鸿资产为资产管理/投资机构；不计入“关联上市公司”覆盖。",
    "ciif": "非上市资本结构记录：中国互联网投资基金为基金主体；不计入“关联上市公司”覆盖。",
}

# The product interface is Chinese.  Locator labels describe where to look in
# the original source, so keep them concise and consistent while leaving the
# source title and quoted excerpt in their original language where appropriate.
LOCATOR_LABELS = {
    "e1": "新闻摘要，第 1 条", "e2": "开篇段落", "e3": "2025 年事件条目",
    "e4": "宇树客户披露段落", "e5": "合作机器人列表", "e6": "出货量比较段落",
    "e7": "正文", "e8": "产品集合页", "e9": "国际消费电子展合作伙伴名单", "e10": "证据缺口记录",
    "e11": "产品介绍", "e12": "2024 年 2 月融资与股东变更段落", "e13": "具身智能业务章节",
    "e14": "核心结论", "e15": "机器人平台与岗位描述", "e16": "研究系统说明",
    "e17": "客户与订单章节", "e18": "奥比中光与宇树科技段落", "e19": "供应链与空心杯电机段落",
    "e20": "第 2 步：安装因时灵巧手", "e21": "机器人页面：数量与项目", "e22": "可用机器人与设备",
    "e23": "硬件设置章节", "e24": "战略合作公告", "e25": "授权经销协议章节",
    "e26": "全球战略合作说明", "e28": "人形机器人商业化比较表", "e29": "开篇融资段落",
    "e30": "宇树 B2 轮融资段落", "e31": "中国厂商中的领先企业段落", "e32": "第 2.2 节：人形机器人",
    "e33": "自然行走介绍",
    "e34": "股东关联关系与一致行动说明",
    "e35": "关于金石：全资私募基金子公司说明",
}


def canonical_publisher(name: str) -> str:
    return PUBLISHER_ALIASES.get(name, name)


def access_status(evidence: dict) -> str:
    """Normalize a human access note into a reviewer-visible permission state."""
    note = str(evidence.get("access", "")).lower()
    if "no login" in note or "without login" in note or note.startswith("public"):
        return "public"
    if "login required" in note or "requires login" in note:
        return "login_required_excluded"
    if "paywall" in note or "paid subscription" in note:
        return "paywalled_excluded"
    if not evidence.get("url") or "not an external source" in note:
        return "not_external_source"
    return "public"

def seed_relationships() -> list[dict]:
    relationships = []
    for index, (other, relation_type, status, maturity, evidence_id) in enumerate(RELATION_SEEDS, 1):
        confirmed = status == "confirmed"
        authority = 2 if evidence_id == "e10" else 15 if evidence_id in {"e17", "e18", "e19"} else 32
        # Cross-validation is calculated after evidence records are assembled.
        # A seed starts with one cited record and therefore receives no bonus.
        score = {"source_authority": authority, "directness": 22 if confirmed else 12, "cross_validation": 0, "recency": 10, "entity_accuracy": 9, "conflict_penalty": 0 if confirmed else 8}
        is_investor = relation_type == "investor_or_investee"
        supplemental = evidence_id in {"e20", "e21", "e22", "e23", "e24", "e25", "e26", "e27", "e28"}
        scope_class = INVESTMENT_SCOPE_CLASSES.get(other, "general") if is_investor else "general"
        scope_note = INVESTMENT_SCOPE_NOTES.get(other, "") if is_investor else ""
        relationships.append({"id": f"rel-{index:02d}", "from": other if relation_type in {"supplier", "customer", "investor_or_investee"} else "unitree", "to": "unitree" if relation_type in {"supplier", "customer", "investor_or_investee"} else other, "type": relation_type, "status": status, "maturity": maturity, "title": f"{'历史融资' if is_investor else relation_type}: {other} 与宇树科技", "summary": "宇树官网公开资料记录的 2024 年融资事件。" if is_investor else "离线研究快照中的可追溯关系记录；请以证据详情与状态边界为准。", "startDate": "2024-02-01" if is_investor else None if supplemental else "2024-01-01", "endDate": None, "updatedAt": "2026-08-31" if supplemental else "2026-08-29", "uncertainty": (("此条只确认历史融资或跟投事实；不据此推断当前持股比例、董事席位或后续轮次。" + (" " + scope_note if scope_note else "")) if is_investor else "该公开页面确认了特定产品或研究平台的使用；不据此推断采购规模、排他性或长期合同。" if supplemental and confirmed else "非 confirmed 记录不能外推为合同、股权或长期稳定关系。"), "scopeClass": scope_class, "score": score, "evidenceIds": [evidence_id]})
    # RoboSense appears in two distinct analytical roles. The filing supports broad
    # collaboration, but does not prove an OEM supply contract or a competitive relationship.
    for relationship in relationships:
        if "robosense" not in {relationship["from"], relationship["to"]}:
            continue
        if relationship["type"] == "supplier":
            relationship["summary"] = "速腾聚创披露与宇树等人形机器人企业存在紧密合作；本快照将其保守列为激光雷达供应候选，而非已确认供货商。"
            relationship["uncertainty"] = "同一交易所文件也支持双方存在广义合作关系，因此另有合作伙伴记录；两条记录分别表达“供应候选”和“公开合作”，不构成竞争关系或已签供货合同的断言。"
        elif relationship["type"] == "partner":
            relationship["summary"] = "速腾聚创在交易所文件中披露与宇树等头部人形机器人企业的紧密合作；本条仅表达公开合作关系。"
            relationship["uncertainty"] = "速腾聚创同时被保守列为供应候选，用于记录可能的激光雷达供给；该双重角色来自同一公开合作披露，不应外推为排他合作、合同金额或长期供货。"
    # Livox is a third-party single-device configuration record, not a statement
    # by either commercial party about an OEM supply relationship.
    for relationship in relationships:
        if "livox" not in {relationship["from"], relationship["to"]}:
            continue
        relationship["summary"] = "加州理工的 SHIELD 论文记录一台 Unitree G1 使用 Livox Mid-360；本条仅作为第三方设备配置中的供应候选。"
        relationship["uncertainty"] = "这是一份第三方研究部署记录，不是宇树或览沃的供货声明；不据此确认双方存在 OEM 供货、长期采购或排他关系。"
    for relationship in relationships:
        if relationship["evidenceIds"] == ["e6"]:
            relationship["uncertainty"] = "同源说明：本条与智元机器人、傅利叶智能、Figure AI 的同业判断同引自一篇 Associated Press 报道。该文章可分别支持行业并列判断，但只计为 1 个来源，互证分固定为 0。"
    for relationship in relationships:
        other = relationship["from"] if relationship["to"] == "unitree" else relationship["to"]
        relationship["evidenceIds"].extend(
            EXTRA_EVIDENCE_BY_RELATION.get((relationship["type"], other), [])
        )
        if relationship["type"] == "investor_or_investee":
            relationship["uncertainty"] += " 另有两篇媒体报道复述同一轮融资名单；它们属于同一融资事件，不增加互证分。"
        elif relationship["type"] == "peer":
            relationship["uncertainty"] += " 另附行业报告或公司公开产品页，用于说明同一人形机器人市场赛道；这不是双方的直接竞争声明，也不增加互证分。"
    return relationships

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, as_of TEXT NOT NULL, created_at TEXT NOT NULL, license TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS companies (id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, aliases TEXT NOT NULL, description TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, publisher TEXT NOT NULL, title TEXT NOT NULL, url TEXT, published_at TEXT, retrieved_at TEXT NOT NULL, locator TEXT NOT NULL, excerpt TEXT NOT NULL, access_note TEXT NOT NULL, availability TEXT NOT NULL, access_status TEXT NOT NULL DEFAULT 'public');
CREATE TABLE IF NOT EXISTS relationships (
 id TEXT PRIMARY KEY, from_company_id TEXT NOT NULL REFERENCES companies(id), to_company_id TEXT NOT NULL REFERENCES companies(id), relationship_type TEXT NOT NULL,
 status TEXT NOT NULL, maturity TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL, start_date TEXT, end_date TEXT, updated_at TEXT NOT NULL,
 uncertainty TEXT NOT NULL, scope_class TEXT NOT NULL DEFAULT 'general', source_authority INTEGER NOT NULL, directness INTEGER NOT NULL, cross_validation INTEGER NOT NULL, recency INTEGER NOT NULL, entity_accuracy INTEGER NOT NULL, conflict_penalty INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS relationship_evidence (relationship_id TEXT NOT NULL REFERENCES relationships(id), evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY (relationship_id, evidence_id));
"""


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def load_snapshot(snapshot_path: Path = DATA_PATH, db_path: Path = DB_PATH) -> None:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    verified_investors = [
        {"id": "meituan", "name": "美团", "kind": "listed_company", "aliases": ["Meituan", "3690.HK"], "description": "上市公司/集团关联的 2024 B2 轮投资方"},
        {"id": "jingshi", "name": "中信金石（中信证券关联）", "kind": "listed_group_affiliate", "aliases": ["金石投资", "Jingshi Investment", "中信证券"], "description": "中信证券全资私募基金子公司；记录的是关联投资主体而非中信证券直接出资"},
        {"id": "sourcecode", "name": "源码资本", "kind": "investment_fund", "aliases": ["Source Code Capital"], "description": "非上市投资机构；保留历史融资事实，不计入关联上市公司覆盖"},
        {"id": "scvc", "name": "深创投", "kind": "investment_fund", "aliases": ["深圳市创新资本投资有限公司"], "description": "国有创投集团而非上市主体；保留历史融资事实，不计入关联上市公司覆盖"},
        {"id": "rongyi", "name": "容亿投资", "kind": "investment_fund", "aliases": ["容亿"], "description": "非上市基金/管理人；保留历史融资事实，不计入关联上市公司覆盖"},
        {"id": "dunhong", "name": "敦鸿资产", "kind": "investment_fund", "aliases": ["敦鸿"], "description": "非上市资产管理/投资机构；保留历史融资事实，不计入关联上市公司覆盖"},
    ]
    verified_partners = [
        {"id": "lightwheel", "name": "Lightwheel", "kind": "company", "aliases": [], "description": "NVIDIA 客户案例中的仿真与部署平台方"},
        {"id": "eth-zurich", "name": "苏黎世联邦理工学院", "kind": "university", "aliases": ["ETH Zurich"], "description": "公开招聘信息披露 Unitree G1 研究平台"},
        {"id": "ucsd", "name": "加州大学圣地亚哥分校", "kind": "university", "aliases": ["UC San Diego"], "description": "官方新闻披露 Unitree G1 医疗机器人研究"},
        {"id": "wolong", "name": "卧龙电驱", "kind": "company", "aliases": ["Wolong Electric Drive"], "description": "公开二级资料提及的力矩电机供应候选"},
        {"id": "orbbec", "name": "奥比中光", "kind": "company", "aliases": ["Orbbec"], "description": "公开行业报道提及的 3D 视觉感知供应候选"},
        {"id": "moons", "name": "鸣志电器", "kind": "company", "aliases": ["MOONS'"], "description": "公开行业研究资料提及的空心杯电机供应候选"},
        {"id": "inspire", "name": "因时机器人", "kind": "company", "aliases": ["Inspire Robots", "北京因时机器人科技有限公司"], "description": "宇树官方安装手册提及的灵巧手供应商"},
        {"id": "cmu", "name": "卡内基梅隆大学", "kind": "university", "aliases": ["Carnegie Mellon University", "CMU"], "description": "公开实验室页面记录 Unitree G1 研究平台"},
        {"id": "mit-csail", "name": "麻省理工学院 CSAIL", "kind": "university", "aliases": ["MIT CSAIL"], "description": "公开 Living Lab 设备清单记录 Unitree G1"},
        {"id": "livox", "name": "览沃科技", "kind": "company", "aliases": ["Livox"], "description": "公开学术论文提及的 Unitree G1 激光雷达供应候选"},
        {"id": "gwm", "name": "长城汽车", "kind": "company", "aliases": ["Great Wall Motor", "GWM"], "description": "官网披露与宇树科技的战略合作"},
        {"id": "gmo-air", "name": "GMO AI & Robotics", "kind": "company", "aliases": ["GMO AIR"], "description": "日本市场宇树授权经销与落地合作方"},
        {"id": "star-plus", "name": "巨星传奇", "kind": "company", "aliases": ["Star Plus Legend"], "description": "官网披露与宇树科技的全球战略合作方"},
        {"id": "ciif", "name": "中国互联网投资基金", "kind": "investment_fund", "aliases": ["中网投", "China Internet Investment Fund"], "description": "非上市基金主体；保留历史融资事实，不计入关联上市公司覆盖"},
        {"id": "leju", "name": "乐聚机器人", "kind": "company", "aliases": ["Leju Robotics"], "description": "公开行业材料并列的中国人形机器人厂商"},
    ]
    known_companies = {item["id"] for item in data["companies"]}
    data["companies"].extend(item for item in verified_investors if item["id"] not in known_companies)
    known_companies = {item["id"] for item in data["companies"]}
    data["companies"].extend(item for item in verified_partners if item["id"] not in known_companies)
    if not any(item["id"] == "e11" for item in data["evidence"]):
        data["evidence"].append({"id": "e11", "publisher": "UBTECH Robotics", "title": "Walker S2 official product page", "url": "https://www.ubtrobot.com/cn/humanoid/products/walker-s2", "publishedAt": "2026-01-01", "retrievedAt": "2026-08-29", "locator": "Product introduction", "excerpt": "UBTECH presents Walker S2 as an industrial humanoid robot.", "access": "Public official page", "availability": "available"})
    if not any(item["id"] == "e12" for item in data["evidence"]):
        data["evidence"].append({"id": "e12", "publisher": "Unitree Robotics", "title": "Company information and development history", "url": "https://www.unitree.com/operate/company/", "publishedAt": "2024-02-01", "retrievedAt": "2026-08-29", "locator": "2024 年 2 月融资与股东变更段落", "excerpt": "宇树官网披露 B2 轮投资方包括美团、金石投资、源码资本，老股东深创投、中网投、容亿、敦鸿和米达钧石跟投。", "access": "Public official page; no login", "availability": "available"})
    if not any(item["id"] == "e13" for item in data["evidence"]):
        data["evidence"].append({"id": "e13", "publisher": "RoboSense Technology", "title": "2025 interim report", "url": "https://www.hkexnews.hk/listedco/listconews/sehk/2025/0926/2025092600733.pdf", "publishedAt": "2025-09-26", "retrievedAt": "2026-08-29", "locator": "Embodied intelligence business section", "excerpt": "RoboSense reports close collaboration with leading global humanoid-robot companies including Unitree. This supports public collaboration, but does not itself prove an OEM supply contract.", "access": "Public exchange filing", "availability": "available"})
    if not any(item["id"] == "e14" for item in data["evidence"]):
        data["evidence"].append({"id": "e14", "publisher": "NVIDIA", "title": "Lightwheel customer story", "url": "https://www.nvidia.com/en-gb/case-studies/lightwheel/", "publishedAt": "2026-01-01", "retrievedAt": "2026-08-29", "locator": "Key Takeaways", "excerpt": "NVIDIA records deployment of GR00T models in Geely's production environment with Unitree H1 humanoid robots.", "access": "Public official case study", "availability": "available"})
    if not any(item["id"] == "e15" for item in data["evidence"]):
        data["evidence"].append({"id": "e15", "publisher": "ETH Zurich", "title": "Postdoctoral Researcher in Robot Learning", "url": "https://jobs.ethz.ch/job/view/JOPG_ethz_alg2qWYFVN3912xBxI", "publishedAt": "2026-01-01", "retrievedAt": "2026-08-29", "locator": "Robot platforms and job description", "excerpt": "ETH's Mobile Robotics Lab states it investigates on a Unitree G1 humanoid and calls it the lab's humanoid platform.", "access": "Public university page", "availability": "available"})
    if not any(item["id"] == "e16" for item in data["evidence"]):
        data["evidence"].append({"id": "e16", "publisher": "University of California San Diego", "title": "The Robot Will See You Now", "url": "https://today.ucsd.edu/story/the-robot-will-see-you-now", "publishedAt": "2025-01-01", "retrievedAt": "2026-08-29", "locator": "Research system description", "excerpt": "UC San Diego reports evaluation of a bimanual teleoperation system for the Unitree G1 humanoid robot across medical procedures.", "access": "Public university news page", "availability": "available"})
    if not any(item["id"] == "e17" for item in data["evidence"]):
        data["evidence"].append({"id": "e17", "publisher": "iNEWS", "title": "Humanoid-robot supply-chain report", "url": "https://inf.news/en/economy/9686b5825acf3bd729cbccaa930e2d12.html/2", "publishedAt": "2026-08-28", "retrievedAt": "2026-08-29", "locator": "Customers and orders section", "excerpt": "Secondary report states Wolong supplies frameless torque motors to Unitree and UBTECH; no primary company filing is retained in this snapshot.", "access": "Public secondary source", "availability": "available"})
    if not any(item["id"] == "e18" for item in data["evidence"]):
        data["evidence"].append({"id": "e18", "publisher": "Industry Sourcing", "title": "Listed companies expand into 3D vision sensing", "url": "https://www.industrysourcing.cn/article/466184", "publishedAt": "2025-03-27", "retrievedAt": "2026-08-31", "locator": "奥比中光与宇树科技段落", "excerpt": "Industry report states that Orbbec supplies vision-camera products to Unitree and also mentions lidar and structured-light sensors. No direct supplier statement or contract is retained in this snapshot.", "access": "Public secondary industry report", "availability": "available"})
    if not any(item["id"] == "e19" for item in data["evidence"]):
        data["evidence"].append({"id": "e19", "publisher": "Big-Bit Motor Summit", "title": "Representative humanoid-robot manufacturer analysis: Unitree", "url": "https://res.big-bit.com/meeting/2025MotorSummit/static_32/pdf/03-C9a4Udm9.pdf", "publishedAt": "2025-06-01", "retrievedAt": "2026-08-31", "locator": "供应链与空心杯电机段落", "excerpt": "Industry presentation identifies MOONS' as a hollow-cup-motor supplier for Unitree. The claim is not independently confirmed by a Unitree or MOONS' disclosure in this snapshot.", "access": "Public secondary industry presentation", "availability": "available"})
    supplemental_evidence = [
        {"id": "e20", "publisher": "Unitree Robotics", "title": "G1 Flagship C End Dexterous Hand Disassembly and Assembly Guide", "url": "https://www.unitree.com/images/G1-Flagship%20Version%20C%20End%20Dexterous%20Hand%20Disassembly%20and%20Assembly%20Guide%20Manual.pdf", "publishedAt": "2025-01-01", "retrievedAt": "2026-08-31", "locator": "Step 2: Install the INSPIRE Dexterous Hand", "excerpt": "Unitree's G1 assembly guide instructs users to install the INSPIRE Dexterous Hand.", "access": "Public official manual", "availability": "available"},
        {"id": "e21", "publisher": "Carnegie Mellon University", "title": "Unitree G1 robot", "url": "https://icontrol.ri.cmu.edu/robot/g1.html", "publishedAt": None, "retrievedAt": "2026-08-31", "locator": "Robot page, quantity and projects", "excerpt": "CMU's iControl Lab lists one Unitree G1 and associated robot-learning projects.", "access": "Public university page", "availability": "available"},
        {"id": "e22", "publisher": "MIT CSAIL", "title": "CSAIL Living Lab", "url": "https://www.csail.mit.edu/csail-living-lab", "publishedAt": None, "retrievedAt": "2026-08-31", "locator": "Available robots and equipment", "excerpt": "MIT CSAIL lists two Unitree G1 Ultimate B humanoid robots in its Living Lab equipment.", "access": "Public university page", "availability": "available"},
        {"id": "e23", "publisher": "California Institute of Technology", "title": "SHIELD thesis hardware setup", "url": "https://thesis.caltech.edu/17351/1/RKC_Thesis-7-compressed.pdf", "publishedAt": None, "retrievedAt": "2026-08-31", "locator": "Hardware Setup section", "excerpt": "A third-party Caltech thesis records one Unitree G1 equipped with a Livox Mid-360 LiDAR. It is not a supply statement by Unitree or Livox and does not establish an OEM-wide supply contract.", "access": "Public university thesis", "availability": "available"},
        {"id": "e24", "publisher": "Great Wall Motor", "title": "Great Wall Motor and Unitree Robotics form strategic cooperation", "url": "https://www.gwm.com.cn/news/3403667.html", "publishedAt": "2025-04-09", "retrievedAt": "2026-08-31", "locator": "Strategic cooperation announcement", "excerpt": "Great Wall Motor states that it formally signed a strategic cooperation agreement with Unitree covering robot R&D, intelligent manufacturing and vehicle innovation.", "access": "Public company announcement", "availability": "available"},
        {"id": "e25", "publisher": "GMO AI & Robotics", "title": "Authorized distributor agreement for Unitree in Japan", "url": "https://ai-robotics.gmo/en/news/article/gmo-unitree/", "publishedAt": None, "retrievedAt": "2026-08-31", "locator": "Authorized distributor agreement section", "excerpt": "GMO AIR states that it concluded an authorized distributor agreement with Unitree Robotics for Japan.", "access": "Public company announcement", "availability": "available"},
        {"id": "e26", "publisher": "Star Plus Legend", "title": "Robotics business", "url": "https://www.splegend.com/en/business/robot.html", "publishedAt": None, "retrievedAt": "2026-08-31", "locator": "Global strategic partnership statement", "excerpt": "Star Plus Legend states that it and Unitree Robotics entered into a global strategic partnership for robotics commercialization.", "access": "Public company page", "availability": "available"},
        {"id": "e28", "publisher": "Hong Kong Exchange filing", "title": "Humanoid-robot commercialization comparison", "url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0622/2026062201645_c.pdf", "publishedAt": "2026-06-22", "retrievedAt": "2026-08-31", "locator": "Industry commercialization comparison table", "excerpt": "The exchange filing compares Unitree and Leju Robotics among Chinese humanoid-robot makers; it supports a peer inference, not a bilateral competitive statement.", "access": "Public exchange filing", "availability": "available"},
        {"id": "e29", "publisher": "National Business Daily", "title": "Unitree completes nearly RMB 1 billion B2 financing round", "url": "https://www.nbd.com.cn/articles/2024-02-23/3253893.html", "publishedAt": "2024-02-23", "retrievedAt": "2026-08-31", "locator": "Opening financing paragraph", "excerpt": "National Business Daily reported that Unitree's B2 round included Meituan, Jingshi Investment and Source Code Capital, with existing investors including SCVC, China Internet Investment Fund, Rongyi and Dunhong following on.", "access": "Public news report", "availability": "available"},
        {"id": "e30", "publisher": "China Securities Journal", "title": "Capital pursues humanoid robotics", "url": "https://epaper.cs.com.cn/zgzqb/images/2024-02/28/A04/zqDB1128.pdf", "publishedAt": "2024-02-28", "retrievedAt": "2026-08-31", "locator": "Unitree B2 financing paragraph", "excerpt": "China Securities Journal reported that Unitree announced a nearly RMB 1 billion B2 round and named Meituan, Jingshi and Source Code Capital among its investors.", "access": "Public newspaper PDF", "availability": "available"},
        {"id": "e31", "publisher": "Associated Press", "title": "Humanoid robots show off their language and boxing skills in Hong Kong", "url": "https://apnews.com/article/robots-humanoid-hong-kong-china-5669f3e8147f2795ec352d9811619a7b", "publishedAt": "2026-04-14", "retrievedAt": "2026-08-31", "locator": "Chinese manufacturers among leading players", "excerpt": "AP reports Omdia ranked AGIBOT, Unitree Robotics and UBTECH as the only first-tier vendors in its global assessment by shipment numbers. This supports an industry-positioning inference only.", "access": "Public news report", "availability": "available"},
        {"id": "e32", "publisher": "Longone Securities", "title": "Embodied-intelligence robot companies at CES 2026", "url": "https://www.longone.com.cn/upload/newdhyj/20260116/209171.pdf", "publishedAt": "2026-01-16", "retrievedAt": "2026-08-31", "locator": "Section 2.2, humanoid robots", "excerpt": "The industry report lists Unitree, AGIBOT and Fourier among Chinese embodied-intelligence robot companies showing representative products, and separately discusses Omdia's shipment ranking. It supports sector classification, not a bilateral competitive claim.", "access": "Public securities research PDF", "availability": "available"},
        {"id": "e33", "publisher": "Figure", "title": "Natural Humanoid Walk Using Reinforcement Learning", "url": "https://www.figure.ai/news/reinforcement-learning-walking", "publishedAt": "2025-03-25", "retrievedAt": "2026-08-31", "locator": "Introducing Learned Natural Walking", "excerpt": "Figure's official article describes its Figure 02 humanoid robot and locomotion research. It supports Figure's inclusion in the humanoid-robot peer set, not a direct relationship with Unitree.", "access": "Public company article", "availability": "available"},
        {"id": "e34", "publisher": "Shanghai Stock Exchange filing", "title": "Unitree Robotics prospectus", "url": "https://static.sse.com.cn/stock/disclosure/announcement/c/202603/002178_20260320_QY8F.pdf", "publishedAt": "2026-03-20", "retrievedAt": "2026-09-01", "locator": "股东关联关系与一致行动说明", "excerpt": "The prospectus states that Hanhai Information, Chengdu Longzhu and Galaxy Z are affiliated with Meituan (3690.HK). It supports group-level entity resolution, not an inference about current shareholding beyond the filing date.", "access": "Public exchange filing", "availability": "available"},
        {"id": "e35", "publisher": "CITIC Goldstone Investment", "title": "About CITIC Goldstone", "url": "https://www.goldstone-investment.com/", "publishedAt": None, "retrievedAt": "2026-09-01", "locator": "关于金石：全资私募基金子公司说明", "excerpt": "CITIC Goldstone states that it is a private-equity fund subsidiary wholly established by CITIC Securities. It supports listed-group affiliation, not a claim that CITIC Securities directly invested in Unitree.", "access": "Public official page", "availability": "available"},
    ]
    known_evidence = {item["id"] for item in data["evidence"]}
    data["evidence"].extend(item for item in supplemental_evidence if item["id"] not in known_evidence)
    for evidence in data["evidence"]:
        evidence["publisher"] = canonical_publisher(evidence["publisher"])
        evidence["locator"] = LOCATOR_LABELS.get(evidence["id"], evidence["locator"])
    if not data["relationships"]:
        data["relationships"] = seed_relationships()
    evidence_urls = {item["id"]: item.get("url") for item in data["evidence"]}
    evidence_by_id = {item["id"]: item for item in data["evidence"]}
    for relationship in data["relationships"]:
        corroboration_keys = [
            EVIDENCE_ORIGIN_GROUPS.get(evidence_id, evidence_urls.get(evidence_id))
            for evidence_id in relationship["evidenceIds"]
        ]
        relationship["score"]["cross_validation"] = corroboration_points(corroboration_keys)
        if relationship["type"] == "peer":
            # Peer labels are market-positioning inferences, not bilateral facts.
            # More sources increase traceability but cannot upgrade certainty alone.
            relationship["score"]["cross_validation"] = 0
        # Missing publication date is not treated as "latest". Retrieval date preserves
        # reproducibility, while recency is conservatively capped at 5/15.
        cited = [evidence_by_id[evidence_id] for evidence_id in relationship["evidenceIds"] if evidence_id in evidence_by_id]
        if cited and any(not item.get("publishedAt") for item in cited):
            relationship["score"]["recency"] = 5
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(SCHEMA)
        relationship_columns = {row[1] for row in connection.execute("PRAGMA table_info(relationships)")}
        if "scope_class" not in relationship_columns:
            connection.execute("ALTER TABLE relationships ADD COLUMN scope_class TEXT NOT NULL DEFAULT 'general'")
        evidence_columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence)")}
        if "access_status" not in evidence_columns:
            connection.execute("ALTER TABLE evidence ADD COLUMN access_status TEXT NOT NULL DEFAULT 'public'")
        for table in ("relationship_evidence", "relationships", "evidence", "companies", "snapshots"):
            connection.execute(f"DELETE FROM {table}")
        snap = data["snapshot"]
        connection.execute("INSERT INTO snapshots VALUES (:id, :asOf, :createdAt, :license)", snap)
        connection.executemany("INSERT INTO companies VALUES (:id, :name, :kind, :aliases, :description)", [
            {**company, "aliases": json.dumps(company.get("aliases", []), ensure_ascii=False), "description": company.get("description", "")} for company in data["companies"]
        ])
        connection.executemany("""INSERT INTO evidence (
            id, publisher, title, url, published_at, retrieved_at, locator, excerpt, access_note, availability, access_status
        ) VALUES (
            :id, :publisher, :title, :url, :publishedAt, :retrievedAt, :locator, :excerpt, :access, :availability, :access_status
        )""", [{**item, "access_status": access_status(item)} for item in data["evidence"]])
        for relationship in data["relationships"]:
            score = relationship["score"]
            connection.execute("""INSERT INTO relationships (
                id, from_company_id, to_company_id, relationship_type, status, maturity, title, summary,
                start_date, end_date, updated_at, uncertainty, scope_class, source_authority, directness,
                cross_validation, recency, entity_accuracy, conflict_penalty
            ) VALUES (
                :id,:from,:to,:type,:status,:maturity,:title,:summary,:startDate,:endDate,:updatedAt,
                :uncertainty,:scopeClass,:source_authority,:directness,:cross_validation,:recency,
                :entity_accuracy,:conflict_penalty
            )""", {**relationship, **score, "type": relationship["type"]})
            connection.executemany("INSERT INTO relationship_evidence VALUES (?, ?)", [(relationship["id"], evidence_id) for evidence_id in relationship["evidenceIds"]])
        connection.commit()
    finally:
        connection.close()


def ensure_loaded() -> None:
    if not DB_PATH.exists():
        load_snapshot()
