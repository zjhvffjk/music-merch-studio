# 热门批量制作与单曲制作页统一 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让热门歌曲批量制作复用单曲制作页的商品选择与参数编辑体验，同时保留原有批量生成和交付结果。

**Architecture:** 前端继续以 `openHotMaker(data)` 为批量入口。它复用单曲制作页的 DOM 结构和现有隐藏参数字段，而不是新增后端 API 或复制生成逻辑。开始按钮只把批量数量和商品选择回写到现有状态，然后触发既有生成入口。

**Tech Stack:** 原生 HTML、CSS、JavaScript；Python 本地 HTTP 服务。

**Spec:** `docs/superpowers/specs/2026-09-20-hot-batch-maker-unification-design.md`

## Global Constraints

- 不新增后端接口或改变 `/api/run` 参数协议。
- 打印与交付功能只在生成完成后显示。
- 商品和参数的字段名沿用 `#p_*`、`SHOP_CV`、`SHOP_BG`、`VINYL_W`。
- 保留现有歌曲列表返回和浏览器历史路由。

## Review Focus

- 选择 5、10、15 首时，传给生成流程的 `TOP` 必须与界面高亮一致。
- 取消全部可选商品时，现有生成校验必须照常阻止空任务。
- 批量页的参数修改必须影响生成结果，不能只改变当前页面显示。
- 从批量页返回及浏览器后退必须恢复歌曲列表。
- 批量生成完成后，现有整组总览、打印输出及 ZIP 不受影响。

---

### Task 1: 统一批量制作配置页

**Files:**
- Modify: `workbench/index.html: openHotMaker`

**Interfaces:**
- Consumes: `data.artist`、`data.songs`、既有 `#p_*` 参数输入和 `SHOP_*` 状态。
- Produces: `MODE='artist'`、`TOP` 和三个商品开关，供既有 `#btnGo` 使用。

- [x] **Step 1: 扩展批量页面标记**

在 `openHotMaker(data)` 中保留数量卡片，并追加与单曲页同名的 `song-maker-products`、`song-maker-details` 和页底状态区。

- [x] **Step 2: 复用商品和参数事件**

为输出卡片维护 `{keychain, shop, vinyl}`，将参数输入、复选框和画布/底色/黑胶尺寸芯片同步到既有全局字段。

- [x] **Step 3: 回写并启动既有批量生成**

开始按钮设置 `MODE='artist'`、`TOP=count`，将所选输出回写到 `#p_keychain`、`#p_shop`、`#p_vinyl` 并触发 `#btnGo`。

- [x] **Step 4: 验证页面结构与脚本语法**

Run: `node --check <提取出的 workbench/index.html 脚本>`
Expected: PASS。

- [x] **Step 5: Commit**

```powershell
git add workbench/index.html
git commit -m "unify hot batch maker with song setup"
```

### Task 2: 回归验证

**Files:**
- Modify: none

**Interfaces:**
- Consumes: Task 1 的批量制作入口。
- Produces: 可复现的接口与静态检查结果。

- [x] **Step 1: 检查服务端与前端语法**

Run: `python -m py_compile workbench/server.py` 和前端脚本 `node --check`。
Expected: PASS。

- [x] **Step 2: 验证生成参数入口**

确认 `openHotMaker` 内的 `TOP=count`、三个商品开关回写和 `#btnGo.click()` 均存在；确认批量页不包含任何打印预览标记。

- [x] **Step 3: 检查未预期改动**

Run: `git diff --check`。
Expected: PASS。


### Task 3: 统一热门批量交付页

**Files:**
- Modify: `workbench/index.html: singleDeliveryView, paint`
- Test: `tests/test_hot_maker_page.py`

**Interfaces:**
- Consumes: 批量任务快照中的 `overview`、`keychainOverview`、`shopGrids`、`vinylOverview` 和 `playerPrints`。
- Produces: 与单曲一致的固定交付目录和单一画布预览。

- [x] **Step 1: 为 artist 批量任务启用交付壳**

在 `paint(d)` 内对已完成、包含多首歌曲的 `d.mode === 'artist'` 调用现有交付视图。

- [x] **Step 2: 使用批量资源填充目录**

交付视图继续从现有概览、钥匙扣、商品拼版、黑胶和打印资源建立标签，不新增后端数据。

- [x] **Step 3: 验证**

Run: `python -m unittest tests.test_hot_maker_page -v`、`node --check <提取的脚本>`、`git diff --check`。
Expected: PASS。
