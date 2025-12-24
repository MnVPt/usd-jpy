"""
预警系统组件 - 整合所有预警逻辑并展示
"""

import streamlit as st
from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class AlertLevel(Enum):
    """预警级别枚举"""
    SAFE = "safe"
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"
    CRITICAL = "critical"


@dataclass
class Alert:
    """预警数据类"""
    level: AlertLevel
    category: str
    message: str
    color: str
    value: float = 0.0
    threshold: float = 0.0


# 预警级别优先级
LEVEL_PRIORITY = {
    AlertLevel.CRITICAL: 0,
    AlertLevel.DANGER: 1,
    AlertLevel.WARNING: 2,
    AlertLevel.INFO: 3,
    AlertLevel.SAFE: 4,
}

# 预警级别颜色
LEVEL_COLORS = {
    AlertLevel.SAFE: "#00C853",
    AlertLevel.INFO: "#2979FF",
    AlertLevel.WARNING: "#FFD600",
    AlertLevel.DANGER: "#FF5722",
    AlertLevel.CRITICAL: "#9C27B0",
}

# 预警级别图标
LEVEL_ICONS = {
    AlertLevel.SAFE: "✅",
    AlertLevel.INFO: "ℹ️",
    AlertLevel.WARNING: "⚠️",
    AlertLevel.DANGER: "🔴",
    AlertLevel.CRITICAL: "🚨",
}

# 预警级别中文名称
LEVEL_NAMES = {
    AlertLevel.SAFE: "安全",
    AlertLevel.INFO: "信息",
    AlertLevel.WARNING: "警告",
    AlertLevel.DANGER: "危险",
    AlertLevel.CRITICAL: "极端风险",
}


def create_alert(
    level: str,
    category: str,
    message: str,
    color: str = None,
    value: float = 0.0,
    threshold: float = 0.0
) -> Alert:
    """
    创建预警对象
    
    Args:
        level: 预警级别字符串
        category: 预警类别（利差/波动率/背离）
        message: 预警消息
        color: 颜色（可选，默认根据级别）
        value: 当前值
        threshold: 阈值
    
    Returns:
        Alert对象
    """
    alert_level = AlertLevel(level) if level in [e.value for e in AlertLevel] else AlertLevel.INFO
    
    if color is None:
        color = LEVEL_COLORS.get(alert_level, "#757575")
    
    return Alert(
        level=alert_level,
        category=category,
        message=message,
        color=color,
        value=value,
        threshold=threshold
    )


def get_highest_priority_alert(alerts: List[Alert]) -> Alert:
    """
    获取最高优先级的预警
    
    Args:
        alerts: 预警列表
    
    Returns:
        最高优先级的预警
    """
    if not alerts:
        return create_alert("safe", "系统", "一切正常")
    
    sorted_alerts = sorted(alerts, key=lambda x: LEVEL_PRIORITY.get(x.level, 99))
    return sorted_alerts[0]


def render_alert_banner(alerts: List[Alert]):
    """
    渲染预警横幅
    
    Args:
        alerts: 预警列表
    """
    if not alerts:
        st.success("✅ 当前风险状态：正常")
        return
    
    # 获取最高级别预警
    highest = get_highest_priority_alert(alerts)
    
    # 过滤出非安全的预警
    active_alerts = [a for a in alerts if a.level != AlertLevel.SAFE]
    
    if not active_alerts:
        st.success("✅ 当前风险状态：正常")
        return
    
    # 根据最高级别显示不同样式
    icon = LEVEL_ICONS.get(highest.level, "ℹ️")
    level_name = LEVEL_NAMES.get(highest.level, "未知")
    
    # 构建预警消息
    alert_messages = [f"{a.category}: {a.message}" for a in active_alerts]
    
    if highest.level == AlertLevel.CRITICAL:
        st.error(f"🚨 **极端风险预警** | {' | '.join(alert_messages)}")
    elif highest.level == AlertLevel.DANGER:
        st.error(f"🔴 **高风险预警** | {' | '.join(alert_messages)}")
    elif highest.level == AlertLevel.WARNING:
        st.warning(f"⚠️ **风险警告** | {' | '.join(alert_messages)}")
    else:
        st.info(f"ℹ️ **信息提示** | {' | '.join(alert_messages)}")


def render_alert_details(alerts: List[Alert]):
    """
    渲染预警详情列表
    
    Args:
        alerts: 预警列表
    """
    if not alerts:
        return
    
    # 按优先级排序
    sorted_alerts = sorted(alerts, key=lambda x: LEVEL_PRIORITY.get(x.level, 99))
    
    for alert in sorted_alerts:
        if alert.level == AlertLevel.SAFE:
            continue
        
        icon = LEVEL_ICONS.get(alert.level, "ℹ️")
        color = alert.color
        
        st.markdown(
            f"""
            <div style="
                padding: 10px;
                border-left: 4px solid {color};
                background-color: rgba(0,0,0,0.05);
                margin-bottom: 10px;
                border-radius: 0 8px 8px 0;
            ">
                <strong>{icon} {alert.category}</strong><br/>
                <span style="color: {color};">{alert.message}</span>
            </div>
            """,
            unsafe_allow_html=True
        )


def render_risk_gauge(risk_score: float, max_score: float = 100):
    """
    渲染风险仪表盘
    
    Args:
        risk_score: 风险分数 (0-100)
        max_score: 最大分数
    """
    # 确定风险级别
    ratio = risk_score / max_score
    
    if ratio < 0.25:
        level = AlertLevel.SAFE
        risk_text = "低风险"
    elif ratio < 0.5:
        level = AlertLevel.WARNING
        risk_text = "中等风险"
    elif ratio < 0.75:
        level = AlertLevel.DANGER
        risk_text = "高风险"
    else:
        level = AlertLevel.CRITICAL
        risk_text = "极端风险"
    
    color = LEVEL_COLORS.get(level, "#757575")
    
    # 使用Streamlit进度条模拟仪表盘
    st.markdown(f"### 综合风险评估: **{risk_text}**")
    st.progress(min(ratio, 1.0))
    st.caption(f"风险分数: {risk_score:.1f} / {max_score}")


def calculate_composite_risk_score(
    spread_stats: Dict,
    vol_stats: Dict,
    divergence_result: Dict
) -> Tuple[float, List[str]]:
    """
    计算综合风险分数
    
    Args:
        spread_stats: 利差统计
        vol_stats: 波动率统计
        divergence_result: 背离检测结果
    
    Returns:
        (风险分数, 风险因素列表)
    """
    score = 0.0
    factors = []
    
    # 利差风险评分 (0-40分)
    spread = spread_stats.get('current', 5.0)
    if spread <= 1.5:
        score += 40
        factors.append("利差极度收窄")
    elif spread <= 2.0:
        score += 30
        factors.append("利差危险收窄")
    elif spread <= 2.5:
        score += 20
        factors.append("利差收窄至警戒线")
    elif spread <= 3.0:
        score += 10
        factors.append("利差处于较低水平")
    
    # 波动率风险评分 (0-30分)
    hv_percentile = vol_stats.get('hv_percentile', 50)
    if hv_percentile >= 95:
        score += 30
        factors.append("波动率处于极端水平")
    elif hv_percentile >= 80:
        score += 20
        factors.append("波动率偏高")
    elif hv_percentile >= 60:
        score += 10
        factors.append("波动率有所上升")
    
    # 背离风险评分 (0-30分)
    if divergence_result.get('divergence_detected', False):
        div_score = abs(divergence_result.get('divergence_score', 0))
        if div_score > 20:
            score += 30
            factors.append("严重资产背离")
        elif div_score > 10:
            score += 20
            factors.append("明显资产背离")
        else:
            score += 10
            factors.append("轻微资产背离")
    
    return (score, factors)


def render_risk_summary(
    spread_alert: Tuple[str, str],
    vol_alert: Tuple[str, str, str],
    div_alert: Tuple[str, str, str]
):
    """
    渲染风险汇总卡片
    
    Args:
        spread_alert: (级别, 颜色) 利差预警
        vol_alert: (级别, 颜色, 消息) 波动率预警
        div_alert: (级别, 颜色, 消息) 背离预警
    """
    col1, col2, col3 = st.columns(3)
    
    with col1:
        level = spread_alert[0]
        color = spread_alert[1]
        icon = "✅" if level == "safe" else "⚠️" if level == "warning" else "🔴"
        st.markdown(
            f"""
            <div style="text-align: center; padding: 15px; 
                        border: 2px solid {color}; border-radius: 10px;">
                <h4>利差风险</h4>
                <p style="font-size: 24px;">{icon}</p>
                <p style="color: {color};">{level.upper()}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        level = vol_alert[0]
        color = vol_alert[1]
        icon = "✅" if level == "safe" else "⚠️" if level == "warning" else "🔴"
        st.markdown(
            f"""
            <div style="text-align: center; padding: 15px;
                        border: 2px solid {color}; border-radius: 10px;">
                <h4>波动率风险</h4>
                <p style="font-size: 24px;">{icon}</p>
                <p style="color: {color};">{level.upper()}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col3:
        level = div_alert[0]
        color = div_alert[1]
        icon = "✅" if level == "safe" else "ℹ️" if level == "info" else "⚠️"
        st.markdown(
            f"""
            <div style="text-align: center; padding: 15px;
                        border: 2px solid {color}; border-radius: 10px;">
                <h4>背离风险</h4>
                <p style="font-size: 24px;">{icon}</p>
                <p style="color: {color};">{level.upper()}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

