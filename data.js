// ============================================================
// Olive Asset Management · FCN 数据文件
// 此文件由后台编辑器导出，请勿手动编辑
// 最后更新: 2026-06-04
// ============================================================

window.OLIVE_DATA = {
  // 本周精选元信息
  meta: {
    week: "2026 · 第 23 周",
    theme: "AI 算力链回调机会",
    publishDate: "2026.06.03",
    nextUpdate: "2026.06.10",
    featuredIds: ["AVGO.US", "NVDA.US", "META.US", "9988.HK", "LLY.US"]
  },

  // 所有标的
  stocks: [
    {
      code: "AVGO.US",
      name: "博通",
      industry: "AI半导体",
      market: "US",
      coupon: 22.5,
      strike: 80,
      ki: 70,
      kiType: "欧式敲入",
      tenor: 6,
      score: 8.7,
      risk: "中",
      tag: "高 IV",
      highlights: [
        "Q2 AI 营收同比 +143%，FY27 路径锁定逾千亿美元",
        "盘后回调 12.6%，IV 升至历史 75 分位，溢价显著",
        "六大超大型客户锁定多 GW 算力订单"
      ],
      thesis: "博通 Q2 财报后盘后下跌 12.6%，本质是预期差修正而非基本面恶化。FY27 AI 营收逾千亿美元路径清晰，回调后 IV 溢价显著扩大，是构建 FCN 的极佳时机。建议 6 个月期、行权 80%、敲入 70% 欧式结构，可实现 22.5% 年化票息。\n\n标的当前 AI 半导体业务保持 100%+ 同比增速，长期客户合同覆盖 Google、Meta、Anthropic 等头部 AI 玩家，业绩可见度高。回调后 IV 升至历史 75 分位，提供了卖出波动率的极佳窗口。",
      risks: "若 AI 资本开支周期出现拐点，标的可能进一步下行。建议控制单一标的仓位 ≤ 5%。下一关键观察点为 Q3 财报与 7 月 AI 资本开支指引。"
    },
    {
      code: "NVDA.US",
      name: "英伟达",
      industry: "AI半导体",
      market: "US",
      coupon: 19.8,
      strike: 80,
      ki: 70,
      kiType: "欧式敲入",
      tenor: 6,
      score: 8.5,
      risk: "中",
      tag: "龙头",
      highlights: [
        "Blackwell Ultra 量产爬坡，Rubin 平台路线清晰",
        "技术面突破前期整理区间，量价配合良好",
        "IV 处于历史 40 分位，相对低估"
      ],
      thesis: "英伟达 Blackwell Ultra 进入量产爬坡期，下一代 Rubin 平台路线图清晰。技术面突破前期整理区间，量价配合良好。当前 IV 处于历史 40 分位，溢价合理。",
      risks: "关注 7 月 AI 资本开支指引与中国市场出口管制进展。"
    },
    {
      code: "TSLA.US",
      name: "特斯拉",
      industry: "新能源",
      market: "US",
      coupon: 28.5,
      strike: 80,
      ki: 70,
      kiType: "美式敲入",
      tenor: 6,
      score: 8.2,
      risk: "高",
      tag: "高收益",
      highlights: [
        "Robotaxi 催化预期升温",
        "IV 处于历史 85 分位，票息空间大",
        "适合风险偏好较高的客户"
      ],
      thesis: "特斯拉 Robotaxi 业务进入兑现期，FSD 订阅率持续上升。当前 IV 处于历史 85 分位，提供了超额票息空间，但高波属性意味着敲入风险也相对较高。",
      risks: "Robotaxi 落地节奏与监管不确定性较高。建议作为组合中的卫星仓位。"
    },
    {
      code: "META.US",
      name: "Meta",
      industry: "互联网",
      market: "US",
      coupon: 16.5,
      strike: 80,
      ki: 70,
      kiType: "欧式敲入",
      tenor: 6,
      score: 8.4,
      risk: "低",
      tag: "稳健",
      highlights: [
        "广告基本面稳健，高个位数增长",
        "与 Broadcom 合作开发自研 AI 芯片",
        "低波蓝筹，适合组合底仓"
      ],
      thesis: "Meta 与 Broadcom 合作开发自研 AI 芯片，长期算力成本下降利好。广告业务保持高个位数增长，估值修复仍有空间。低波属性适合作为组合中的稳健仓位。",
      risks: "监管风险与 Reality Labs 持续亏损。"
    },
    {
      code: "AAPL.US",
      name: "苹果",
      industry: "消费",
      market: "US",
      coupon: 13.2,
      strike: 80,
      ki: 70,
      kiType: "欧式敲入",
      tenor: 9,
      score: 8.1,
      risk: "低",
      tag: "保守",
      highlights: [
        "低波蓝筹，敲入概率极低",
        "Apple Intelligence 推动换机周期",
        "适合保守型客户配置底仓"
      ],
      thesis: "苹果作为低波蓝筹，敲入概率极低。Apple Intelligence 推动新一轮换机周期，服务业务保持双位数增长。适合保守型客户作为组合底仓。",
      risks: "中国市场销量与监管不确定性。"
    },
    {
      code: "9988.HK",
      name: "阿里巴巴",
      industry: "互联网",
      market: "HK",
      coupon: 21.0,
      strike: 80,
      ki: 70,
      kiType: "欧式敲入",
      tenor: 6,
      score: 8.3,
      risk: "中",
      tag: "估值修复",
      highlights: [
        "云业务在 AI 推理需求驱动下重回增长",
        "港股 IV 高于美股同业，票息更具吸引力",
        "回购计划持续提供下方支撑"
      ],
      thesis: "阿里云业务在 AI 推理需求驱动下重回增长，云业务估值有显著修复空间。港股 IV 整体高于美股同业，FCN 收益更具吸引力。",
      risks: "中美科技博弈与电商竞争格局变化。"
    },
    {
      code: "700.HK",
      name: "腾讯控股",
      industry: "互联网",
      market: "HK",
      coupon: 15.8,
      strike: 80,
      ki: 70,
      kiType: "欧式敲入",
      tenor: 6,
      score: 8.0,
      risk: "低",
      tag: "稳健",
      highlights: [
        "游戏业务复苏，递延收入持续增长",
        "千亿港元回购支撑股价",
        "微信生态变现加速"
      ],
      thesis: "腾讯游戏业务在新游与海外双轮驱动下持续复苏，千亿港元回购计划支撑股价下方。微信电商与广告变现加速。",
      risks: "监管政策变化与新游表现不及预期。"
    },
    {
      code: "JPM.US",
      name: "摩根大通",
      industry: "金融",
      market: "US",
      coupon: 12.8,
      strike: 80,
      ki: 70,
      kiType: "欧式敲入",
      tenor: 9,
      score: 7.9,
      risk: "低",
      tag: "稳健",
      highlights: [
        "银行业龙头，息差环境受益",
        "投行业务回暖",
        "IV 较低适合长期限结构"
      ],
      thesis: "摩根大通作为银行业龙头，在息差环境中持续受益。投行业务进入回暖周期。IV 较低，适合搭配 9 个月长期限结构降低再投资风险。",
      risks: "信贷质量恶化与息差收窄。"
    },
    {
      code: "LLY.US",
      name: "礼来",
      industry: "医药",
      market: "US",
      coupon: 17.5,
      strike: 80,
      ki: 70,
      kiType: "欧式敲入",
      tenor: 6,
      score: 8.1,
      risk: "中",
      tag: "成长",
      highlights: [
        "GLP-1 龙头地位稳固",
        "Mounjaro/Zepbound 销售超预期",
        "新适应症临床数据将陆续读出"
      ],
      thesis: "礼来 GLP-1 龙头地位稳固，Mounjaro/Zepbound 销售持续超预期。新适应症（阿尔茨海默症、肝病）临床数据将陆续读出，构成正向催化。",
      risks: "竞品 Novo Nordisk 新一代产品上市可能带来份额压力。"
    },
    {
      code: "BYD.HK",
      name: "比亚迪股份",
      industry: "新能源",
      market: "HK",
      coupon: 24.0,
      strike: 80,
      ki: 70,
      kiType: "美式敲入",
      tenor: 6,
      score: 7.8,
      risk: "中",
      tag: "高收益",
      highlights: [
        "海外销量超预期",
        "刀片电池与 DM-i 技术路线领先",
        "港股 IV 处于历史高位"
      ],
      thesis: "比亚迪海外销量持续超预期，技术路线（刀片电池、DM-i 5.0）保持领先。港股 IV 处于历史高位，提供超额票息空间。",
      risks: "海外贸易政策与国内价格战压力。"
    },
    {
      code: "600519.CN",
      name: "贵州茅台",
      industry: "消费",
      market: "CN",
      coupon: 14.5,
      strike: 80,
      ki: 70,
      kiType: "欧式敲入",
      tenor: 9,
      score: 7.7,
      risk: "低",
      tag: "低估",
      highlights: [
        "估值进入历史低位区间",
        "渠道库存压力缓解",
        "高分红低波属性"
      ],
      thesis: "茅台估值进入历史低位区间，渠道库存压力缓解。高分红低波属性适合保守型客户。",
      risks: "高端消费需求疲软与渠道改革进度。"
    },
    {
      code: "AMD.US",
      name: "AMD",
      industry: "AI半导体",
      market: "US",
      coupon: 25.5,
      strike: 80,
      ki: 70,
      kiType: "美式敲入",
      tenor: 6,
      score: 7.6,
      risk: "中",
      tag: "高 IV",
      highlights: [
        "MI400 系列即将量产",
        "AI 加速器份额持续提升",
        "IV 处于历史 80 分位"
      ],
      thesis: "AMD MI400 系列即将量产，在 AI 加速器市场份额持续提升。当前 IV 处于历史 80 分位，提供较好票息空间。",
      risks: "与英伟达竞争差距、新品交付节奏。"
    }
  ]
};
