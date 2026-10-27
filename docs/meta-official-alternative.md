# V3.1 官方 Meta API + GitHub Actions 發文替代方案（2026-10-27）

## 最新實際狀態
- 使用者要求停止重試 Windsor 在 ChatGPT 無人排程內發文的流程。舊 daily 目前 disabled；不要在舊管線與本管線同時發布相同時段。
- 此方案**已保存程式與 GitHub Actions workflow，但預設關閉，沒有 Meta Token 就不會發布**。它**不是**已完成 Meta 發文驗收。
- 保留 Page ID `1346385028565797`，原粉專名稱與頭貼封面簡介不變。不得公開任何 Meta Token、密碼或 App Secret。
- 保留 2026-10-26 f269 舊文與 2026-10-27 16:30 8b6 armed 事故的 unknown 記錄及所有 hash；**禁止重新發布這些舊文**。

## 新分工
1. ChatGPT Work 僅負責原創選題/圖文、持久化 JPEG、GitHub Pages 公開 200/MIME/SHA 核對、準備新的未來時段 queue 檔；不再呼叫 Windsor 或 Meta 發布寫入。先在 Work 可見執行模式驗收，排程模式仍需驗證。
2. GitHub Actions workflow `.github/workflows/meta-graph-publish.yml` 讀取已準備好的 queue，透過 `scripts/meta_graph_publish.py` 直接呼叫 Meta 官方 Graph API `/{page-id}/photos`；不透過 ChatGPT Plugin 連線。
3. Graph 發布回應與安全狀態記錄於 `state/meta_dispatch/YYYY-MM-DD-HHMM.json`。**真正的 Meta Post ID 與回讀一致才算成功**。

## 前提與最低人工一次授權
- 使用者以真正 Page 管理員身分進入 https://developers.facebook.com/ ，建立或使用可管理該 Page 的 Meta App，查當前官方文件要求及可用存取模式。
- 先以合法官方流程確認 `pages_manage_posts`、`pages_read_engagement`、`pages_show_list` 與 Page 發布權限。若 App Review、商家驗證、額外權限或免費方案限制擋住，記錄真實錯誤，不繞過。不要假設自己的 App 一定免審。
- 透過正式授權取得 Page Access Token，**只在 GitHub repo Settings → Secrets and variables → Actions → Secrets 新增 `META_PAGE_ACCESS_TOKEN`**。不要在聊天、Issue、Commit、Workflow log、Python檔或公開 repo 印出 Token。
- 在 Actions → Variables 新增 `META_PUBLISH_ENABLED`，保持 `false` 直到所有前置測試及 Meta 官方權限核對都通過。使用者明確確認啟用後才設為 `true`。
- Work 不得以 Windsor 已授權推論 Graph API Token 已經取得；兩套授權獨立。

## Queue JSON 格式
檔名：`queue/meta/2026-10-28/0930.json`（日期及四個時間各自一個）
```json
{
  "page_id": "1346385028565797",
  "slot": "2026-10-28T09:30",
  "language": "en",
  "caption": "此處改成新原創文案",
  "image_sha256": "此處放64字元小寫十六進位實際SHA256",
  "image_url": "https://gxaawill2-ui.github.io/cat-page-autopilot/assets/實際SHA256.jpg",
  "experiment_id": "intl-20261026-14d"
}
```
這是格式範例，不是可以實際發布的內容。不得把舊圖片、舊文案、舊過期 slot 放進新 queue。公開 repo 中的候發文案會對外可見，不得放入任何敏感資訊。

## 安全邏輯
- 排程：台灣 09:30 英文、12:30 繁中、16:30 繁中、19:30 英文（11/3、11/6 晚間日文由準備 queue 階段決定）。
- GitHub Actions 使用 UTC 01:30、04:30、08:30、11:30，每次只讀同一天同一 slot；超過 45 分鐘、缺圖文、缺 Token、變數未開、查重不過、圖片未公開都跳過。
- 同一 slot 發布前**先 commit + push armed 狀態**；CAS 失敗禁止呼叫 API。單次 API POST；成功則儲存真 ID/回讀結果；逾時或回條缺失保持 unknown，**不自動重送**。
- 先核對本地 old/new state 的文案與圖片 hash，並向 Meta 官方讀取近期貼文查同 caption。所有未知舊文保留供調查，不清除。
- GitHub Actions 排程屬 best-effort，官方文件載明可能延遲或漏執行；45 分鐘以外一律不補發，不能保證分鐘級準點。
- 不使用額外付費 LLM、AI 圖片 API、廣告或第三方付費排程。

## 驗收和切換順序
1. GitHub Actions 手動執行 workflow_dispatch `dry_run=true`。執行 `python3 -m unittest discover -s scripts -p test_meta_graph_publish.py -v`；只驗證 local safety，沒有 Facebook 寫入。
2. Work 完成並安全儲存**一篇未來正常時段的新原創 queue**和已驗證的圖片網址。先檢查資料及 image hash；不要補舊事故。
3. Meta App/Token 正式取得且保密後，用 Graph GET 測 Page 身分、授權及最近貼文；任何錯誤不得打開開關。確認出站連線及 API 預檢可行。
4. 關閉舊 daily 中的 Windsor 發文路徑。新的官方 API queue 來源可以沿用原 daily，但**它只能產生 queue，不得再送 Facebook**；若因排程任務互動確認而停用則只保存草稿並回報。
5. 使用者確認後將 GitHub Actions 變數 `META_PUBLISH_ENABLED=true`。在下一個正常時段只試發**一篇新內容**，確認 Post ID、Meta UI及 Graph回讀、GitHub狀態。若為 unknown，絕不自動重送。
6. 下一時段再觀察一次。成功前不宣稱「每天四篇已完全恢復」。
7. 若 Meta App/Token 根本無法合法取得：暫改 Work 批次生成內容 + Meta Business Suite **人工一次排多篇**；清楚標成半自動，不能稱完全無人。

## 技術路徑
- Python：`scripts/meta_graph_publish.py`
- 安全測試：`scripts/test_meta_graph_publish.py`
- 工作流程：`.github/workflows/meta-graph-publish.yml`
- 官方權限：https://developers.facebook.com/docs/permissions/reference/
- 官方 GitHub Secrets：https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- 官方 GitHub Actions 免費規則：https://docs.github.com/en/actions/concepts/billing-and-usage

最新授權：**粉專更名暫停。額外 NT$0。禁止重啟舊 Windsor 發文造成競爭。**
