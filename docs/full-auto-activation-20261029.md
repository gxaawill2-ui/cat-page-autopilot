# 全自動貓咪粉專｜2026-10-29 安全啟用說明

## 本分支已建立，但尚未啟用

本分支提供完整的背景流程骨架：GitHub Actions 每天兩次檢查未來三天的空缺時段 → Vercel AI Gateway 自動生成原創文案與新圖片 → 圖像完整性驗證及 AI 視覺 QA → 原圖+草稿 commit 到 GitHub、等公開 JPEG 可驗證 → Meta Graph 官方 API 送入「未來預約貼文」，由 **Facebook 官方排程** 負責到點發佈。

目前正式站 `main` 仍使用 Work 互動製稿+ Meta Business Suite 原生預約，且 10/29 四篇已預約。**此分支未上線，不會更動/重發任何已預約貼文。**

## 阻礙（必須真實解決，不可假裝自動化成功）

1. 原 GitHub `META_PAGE_ACCESS_TOKEN` 真實 GET 曾回 HTTP401、code190、subcode463（已失效）。必須透過合法 Meta 官方授權取得新 Page Token、以安全表單更新 **同名 GitHub Secret**；只允許既有 Page 1346385028565797 與必要 scopes。切勿把 Token 貼在聊天或提交到 repo。若 credential 再失效，系統會在**AI 生圖前**安全停下，不會重新發送舊文章。
2. 需在 Vercel AI Gateway 開通並安全設定 `AI_GATEWAY_API_KEY` 為 GitHub Secret。**ChatGPT Plus 不提供額外的 API 生圖額度。** AI Gateway 官方 2026 年資料有每月 $5 免費額度，但方案與模型成本可能變；應在官方帳務設定硬性阻斷自費（確認沒有自動加值或付費轉換），再啟用。未設硬限制前不要打開正式開關。
3. 免費文字、視覺模型為可能變動的限時供應；圖片預設 `bfl/flux-3-image-klein` 顯示約 $0.009/張，但要通過實際授權/模型回傳格式/帳務檢驗。任何模型停用、配額不夠、非預期影像格式、視覺 QA 失敗一律停止，不自動買點數。
4. 以上兩項金鑰與免自費帳務設置完成，且單篇真正預約成功、可於 Meta Planner 查見後，才可把此分支合併到 `main`，設定 GitHub Repository Variable `CAT_AUTOPILOT_ENABLED=true`。此前**絕不能宣稱完全無人經營已恢復**。

## 調度與防重複

- 新 workflow: `.github/workflows/cat-unattended-replenish.yml`。
- 兩次 UTC 00:17、12:17 觸發；不是 Facebook 到點發文工作，所以 GitHub 延遲通常不會直接造成錯過當天四個時段。
- 目標台灣 09:30 en、12:30 繁中、16:30 繁中、19:30 en；保持每天最多四篇，先填未來三天。已存在 `state/meta_native/YYYY-MM-DD-HHMM.json` 的時段絕不重用。
- 有 queue 但尚未預約者，不會重新付費生成同一張圖片；待 GitHub Pages 公開 JPEG 200/MIME/SHA 真驗證後，下一次才向 Meta 排定。
- 真 API 使用現有 `scripts/meta_native_schedule.py`，先 CAS 鎖，再傳未發布圖片、單次 Meta Page Feed 預約，回讀真 Post ID。遇不明回應保持鎖，絕不重送。
- 預設 `CAT_AUTOPILOT_ENABLED` 未啟用；手動 dry-run 只統計缺口、測試不寫 Meta。
- 過去 10/26～10/28 未知貼文不補發、不清鎖。新版也不碰既有 10/29 已預約四篇。
- 每月無新額外費用為硬要求；**若無法驗證模型與帳務硬上限，系統必須保持關閉**。
- Meta API 或 AI Gateway 再遇需授權/審核，無法合法繞過；安全停用並回報真實錯誤。

## 尚未做的正式驗收

- 尚無新的 Meta Page Token，也無已確認可用的 AI Gateway Key；因此無法執行真正的首次 AI → Meta 預約交易。
- 尚未驗證新 Vercel Gateway 模型的實際 JSON/圖片回傳格式，也未跑本分支的 CI 執行。
- 分支僅為安全實作、未合併正式站。要稱「全自動運作中」，至少要取得 **真正原創圖片＋文案 → Meta 預約 Post ID → Facebook 到時間實際發布** 的完整兩輪實證。
