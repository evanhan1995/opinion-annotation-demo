# -*- coding: utf-8 -*-
"""LLM 模型降级状态追踪（按组件区分，参考 orchestrator._SCRAPER_FAILURES）。

判定口径（对称 2/2）：
  - 进入降级：连续失败 MODEL_DEGRADE_THRESHOLD(=2) 次。
  - 解除降级：连续成功 MODEL_RECOVER_THRESHOLD(=2) 次。
  对称设计理由：LLM 限流/网络类故障往往断断续续，单次成功可能只是短暂恢复；
  连续 2 次成功才可靠确认服务已稳定恢复，避免降级状态来回跳。

按组件（analyst / curator / daily_report）分开记录，不合并：
  各组件降级目标不同（Analyst→MiniMax/Sentinel，Curator→bigram，DailyReport→模板），
  且一个组件降级不影响其他组件是否降级。

持久化到 config/model_degradation.json（整体覆盖写入，沿用项目惯例），
进程重启后由 _load() 恢复。
"""
import json
import threading
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DEGRADATION_PATH = PROJECT_ROOT / "config" / "model_degradation.json"

MODEL_DEGRADE_THRESHOLD = 2   # 连续失败 N 次进入降级
MODEL_RECOVER_THRESHOLD = 2   # 连续成功 N 次解除降级

_lock = threading.Lock()
# 内存状态：{component: {"failures": int, "successes": int, "degraded": bool,
#                        "last_error": str, "updated_at": str}}
_state = {}


def _load() -> dict:
    """从 config/model_degradation.json 恢复持久化状态。"""
    if not MODEL_DEGRADATION_PATH.exists():
        return {}
    try:
        data = json.loads(MODEL_DEGRADATION_PATH.read_text(encoding="utf-8"))
        return data.get("components", {}) if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def _persist() -> None:
    """持久化到 config/model_degradation.json（整体覆盖）。"""
    MODEL_DEGRADATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_DEGRADATION_PATH.write_text(
        json.dumps({"version": 1, "components": _state}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# 模块加载时恢复
_state.update(_load())


def _entry(component: str) -> dict:
    return _state.setdefault(component, {
        "failures": 0, "successes": 0, "degraded": False,
        "last_error": "", "updated_at": "",
    })


def record_llm_success(component: str) -> None:
    """记录一次 LLM 调用成功。

    未降级：successes+1，达 RECOVER_THRESHOLD 前保持；降级中：连续成功
    RECOVER_THRESHOLD 次后解除（对称 2/2）。
    """
    with _lock:
        e = _entry(component)
        e["failures"] = 0
        if e["degraded"]:
            e["successes"] += 1
            if e["successes"] >= MODEL_RECOVER_THRESHOLD:
                e["degraded"] = False
                e["successes"] = 0
                e["last_error"] = ""
        else:
            e["successes"] += 1  # 正常态累计成功（不参与判定，仅留痕）
        e["updated_at"] = datetime.now().isoformat()
        _persist()


def record_llm_failure(component: str, error: str) -> None:
    """记录一次 LLM 调用失败：failures+1、successes 清零；达阈值进入降级。"""
    with _lock:
        e = _entry(component)
        e["failures"] += 1
        e["successes"] = 0
        e["last_error"] = str(error)[:200]
        if e["failures"] >= MODEL_DEGRADE_THRESHOLD:
            e["degraded"] = True
        e["updated_at"] = datetime.now().isoformat()
        _persist()


def is_llm_degraded(component: str) -> bool:
    """当前组件是否处于降级状态。"""
    with _lock:
        return bool(_state.get(component, {}).get("degraded", False))


def get_degraded_components() -> list[str]:
    """返回当前处于降级的所有组件（供 UI 展示）。"""
    with _lock:
        return [c for c, e in _state.items() if e.get("degraded")]
