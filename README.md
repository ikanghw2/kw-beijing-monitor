# 北京市科委通知公告监控 · Server酱微信推送

基于 GitHub Actions,每 30 分钟检查一次 [北京市科委通知公告页](https://kw.beijing.gov.cn/zwgk/tzgg/) 的最新通知,发现新增就通过 **Server酱** 推送到微信。

## 一、方案特点
- ✅ **免费**(每天 5 条,合并推送,对政府通知量足够)
- ✅ **微信公众号直接接收**,不用装陌生 APP
- ✅ 支持 Markdown 富文本
- ✅ 支持关键词过滤
- 💡 **合并推送策略**:一次抓到多条新增会合并成 1 条消息,不浪费额度

## 二、部署步骤

### 1️⃣ 拿到 Server酱 SendKey

1. 打开 <https://sct.ftqq.com/>
2. 微信扫码 或 GitHub 登录
3. 按提示**扫码关注公众号「方糖服务号」**
4. 到 <https://sct.ftqq.com/sendkey> 复制你的 SendKey(形如 `SCT12345TxxxxxxxxxxxxxxxxxT`)
5. **测试**:浏览器打开 `https://sctapi.ftqq.com/你的KEY.send?title=测试` 微信应该秒收到消息

### 2️⃣ 本地先测试(推荐)

```powershell
cd d:\大学学习\深度学习\zhihu-monitor
pip install -r requirements.txt

$env:SERVERCHAN_KEY = "SCT你的Key"
$env:TARGET_URL = "https://kw.beijing.gov.cn/zwgk/tzgg/"

# 首次会记录基线不推送
python monitor.py

# 强制测试推送(模拟有 3 条新通知)
Remove-Item state.json -ErrorAction SilentlyContinue
python -c "
import json, sys
sys.path.insert(0, '.')
from monitor import fetch_notices, TARGET_URL
from pathlib import Path
items = fetch_notices(TARGET_URL)
seen = [it['id'] for it in items[3:]]
Path('state.json').write_text(json.dumps({'seen_ids': seen}, ensure_ascii=False), encoding='utf-8')
print(f'预留 {len(items)-len(seen)} 条作为新增')
"
python monitor.py
```

### 3️⃣ 创建 GitHub 仓库
```powershell
cd d:\大学学习\深度学习\zhihu-monitor
git init
git add .
git commit -m "init: kw beijing gov notice monitor"
```

到 <https://github.com/new> 建 Private 仓库,然后:
```powershell
git remote add origin https://github.com/你的用户名/仓库名.git
git branch -M main
git push -u origin main
```

### 4️⃣ 配置 GitHub Secret

仓库 → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|-----|-----|
| `SERVERCHAN_KEY` | 你的 SendKey (以 `SCT` 开头) |

### 5️⃣ 开启 Actions 写权限
仓库 → **Settings → Actions → General → Workflow permissions** → **Read and write** → 保存

### 6️⃣ 手动运行一次
仓库 → **Actions → Monitor Beijing KW Notices → Run workflow**

之后每 30 分钟自动运行。

## 三、常见问题

### Q1: 免费 5 条/天够用吗?
- 北京科委通知一般一天新增 1-3 条,足够
- 单次运行发现多条新增会**合并成 1 条**消息,不会浪费额度
- 万一某天连续更新超过 5 次会被限流,次日恢复(不影响后续)

### Q2: 收不到消息?
- 确认已关注公众号「方糖服务号」
- 在 <https://sct.ftqq.com/send> 页面查看发送记录
- 用测试链接手动测试

### Q3: 想只推特定关键词的通知?
在 `.github/workflows/monitor.yml` 里取消 `FILTER_KEYWORDS` 那行的注释:
```yaml
FILTER_KEYWORDS: '申报,公示,征集'
```

### Q4: 想换监控目标?
改 `.github/workflows/monitor.yml` 里的 `TARGET_URL`。脚本按 `t20260728_4793666.html` 这种"日期+编号"格式识别公告链接,大部分政府网站都用这个模式。

### Q5: 想改频率?
- `'*/15 * * * *'` — 每 15 分钟
- `'7,37 * * * *'` — 每 30 分钟(当前配置)
- `'0 8-20 * * *'` — 白天每小时一次

### Q6: 5 条不够想升级?
Server酱 Turbo 版 ¥18/年 可提到 **1000 条/天**。

## 四、成本
- **GitHub Actions**:免费 2000 分钟/月 ✅
- **Server酱**:免费 5 条/天(足够) ✅
- **总成本**:**¥0**

## 五、文件说明

| 文件 | 用途 |
|-----|-----|
| `monitor.py` | 主脚本 |
| `.github/workflows/monitor.yml` | GitHub Actions 定时配置 |
| `requirements.txt` | Python 依赖 |
| `state.json` | 自动生成的状态文件 |
