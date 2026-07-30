"""
北京市科委 (kw.beijing.gov.cn) 通知公告监控脚本

数据源: https://kw.beijing.gov.cn/zwgk/tzgg/
- 直接抓取列表页,无需登录、无签名
- 对比上一次结果,发现新增通知就通过 Server酱 (sct.ftqq.com) 推送到微信
- 状态保存在 state.json(由 GitHub Actions commit 回仓库)
"""
import os
import re
import json
import requests
from urllib.parse import urljoin
from pathlib import Path
from datetime import datetime

# ===== 配置区 =====
TARGET_URL = os.environ.get("TARGET_URL", "https://kw.beijing.gov.cn/zwgk/tzgg/")
STATE_FILE = Path("state.json")
SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "")
MAX_PUSH = 10           # 单次推送最多列出多少条(避免消息过长)
KEEP_LAST_N = 1000      # state.json 里保留最近多少条已读 ID
# 关键词过滤(可选):非空时,只推送标题包含这些关键词的公告(用逗号分隔)
FILTER_KEYWORDS = [w.strip() for w in os.environ.get("FILTER_KEYWORDS", "").split(",") if w.strip()]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def _hash_id(text: str) -> str:
    """稳定 ID: 从公告 URL 里的日期+编号提取(如 t20260728_4793666)"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:16]


def fetch_notices(base_url: str) -> list[dict]:
    """抓取通知公告列表页"""
    resp = requests.get(base_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    if resp.apparent_encoding:
        resp.encoding = resp.apparent_encoding
    html = resp.text

    # 匹配公告链接:href 里包含 .html + 类似 t20260728_4793666 的编号
    # 兼容相对路径 ./202607/... 和绝对路径 https://kw.beijing.gov.cn/...
    pattern = re.compile(
        r'<a[^>]+href="([^"]*t\d{8}_\d+\.html)"[^>]*>([^<]+)</a>',
        re.IGNORECASE,
    )
    matches = pattern.findall(html)

    results = []
    seen_urls = set()
    for href, text in matches:
        # 补全 URL
        full_url = urljoin(base_url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        title = text.strip()
        # 清理 HTML 实体
        title = title.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#160;", " ")
        title = title.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
        if not title or len(title) < 5:
            continue

        # 从 URL 里提取日期(20260728)
        date_match = re.search(r"t(\d{8})_", full_url)
        pub_date = ""
        if date_match:
            d = date_match.group(1)
            pub_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

        # ID 用 URL 里的编号部分(t20260728_4793666),稳定
        id_match = re.search(r"(t\d{8}_\d+)\.html", full_url)
        item_id = id_match.group(1) if id_match else _hash_id(full_url)

        results.append({
            "id": item_id,
            "title": title,
            "url": full_url,
            "pub_date": pub_date,
        })

    return results


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"seen_ids": []}
    return {"seen_ids": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def send_wechat(title: str, content_md: str) -> None:
    """通过 Server酱 (sct.ftqq.com) 推送微信"""
    if not SERVERCHAN_KEY:
        print("[WARN] SERVERCHAN_KEY 未配置,跳过推送")
        print(f"[DEBUG] 本应推送:\n{title}\n{content_md[:500]}")
        return

    url = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
    payload = {
        "title": title,
        "desp": content_md,   # Markdown 正文
    }
    try:
        resp = requests.post(url, data=payload, timeout=15)
        try:
            result = resp.json()
        except Exception:
            result = {"raw": resp.text[:300]}
        code = result.get("code", -1)
        if code == 0:
            print(f"[INFO] Server酱推送成功: pushid={result.get('data', {}).get('pushid', '')}")
        else:
            print(f"[ERROR] Server酱返回错误 (HTTP {resp.status_code}): {result}")
    except Exception as e:
        print(f"[ERROR] Server酱推送失败: {e}")


def build_message(new_items: list[dict]) -> tuple[str, str]:
    """拼装 PushPlus markdown 消息"""
    title = f"北京科委新通知 · {len(new_items)} 条"
    lines = [
        f"## 📢 北京市科委通知公告 · 发现 {len(new_items)} 条新内容",
        "",
    ]
    for i, it in enumerate(new_items[:MAX_PUSH], 1):
        date_str = f" ({it['pub_date']})" if it.get("pub_date") else ""
        lines.append(f"### {i}. {it['title']}")
        if date_str:
            lines.append(f"> 📅 发布日期:{it['pub_date']}")
        lines.append(f"[🔗 查看原文]({it['url']})")
        lines.append("")
    if len(new_items) > MAX_PUSH:
        lines.append(f"_...还有 {len(new_items) - MAX_PUSH} 条未展示_")
    lines.append(f"\n---")
    lines.append(f"_数据源: [{TARGET_URL}]({TARGET_URL})_")
    lines.append(f"_检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    return title, "\n".join(lines)


def main() -> None:
    print(f"[{datetime.now()}] 开始检查: {TARGET_URL}")

    try:
        items = fetch_notices(TARGET_URL)
    except Exception as e:
        print(f"[ERROR] 抓取失败: {e}")
        return

    print(f"[INFO] 抓取到 {len(items)} 条")
    if not items:
        print("[WARN] 抓取结果为空,可能是页面改版或临时不可用")
        return

    # 关键词过滤(可选)
    if FILTER_KEYWORDS:
        before = len(items)
        items = [it for it in items if any(k in it["title"] for k in FILTER_KEYWORDS)]
        print(f"[INFO] 关键词过滤: {before} -> {len(items)} 条 (关键词: {FILTER_KEYWORDS})")

    state = load_state()
    seen_ids = set(state.get("seen_ids", []))
    is_first_run = len(seen_ids) == 0

    new_items = [it for it in items if it["id"] not in seen_ids]

    if is_first_run:
        print(f"[INFO] 首次运行,记录基线 {len(items)} 条,不推送")
    elif not new_items:
        print("[INFO] 没有新内容")
    else:
        print(f"[INFO] 发现 {len(new_items)} 条新内容,准备推送")
        # 按 ID 倒序(编号越大越新)
        new_items.sort(key=lambda x: x["id"], reverse=True)
        msg_title, content = build_message(new_items)
        send_wechat(msg_title, content)

    all_ids = list(seen_ids | {it["id"] for it in items})[-KEEP_LAST_N:]
    save_state({
        "seen_ids": all_ids,
        "last_update": datetime.now().isoformat(),
        "target_url": TARGET_URL,
        "last_run_count": len(items),
    })
    print("[INFO] 状态已保存,完成")


if __name__ == "__main__":
    main()
