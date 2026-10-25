# 執行程序（由 ChatGPT Work 工具執行；不是外部免費生圖 API）

唯一 repository：gxaawill2-ui/cat-page-autopilot。先讀 CAT-PAGE-STATUS.md、state/policy.json 及本檔。GitHub 是 canonical；Library 的 CAT-PAGE-STATUS.md 為對應入口快照。

## 每輪
1. 用現有 GitHub 工具確認連線，fresh clone 公開 repo。用 Windsor get_connectors、list_actions 確認 Page 1346385028565797 和 create_photo_post。讀 state/posts、最近貼文、records 去重。若發現 publishing / published_unverified，先核對它們，禁止重送。
2. 搜尋最近24–48小時台灣趨勢、可信新聞、公開 Threads/Facebook（取得不到就寫未取得）。保留5個候選、來源、事件日期、實際熱度訊號；不把搜尋結果筆數當熱度。重要事實用官方來源核對；原創生活題無時事數字可直接創作。
3. 生成新原創圖片（現有內建工具，最多2次）；目視檢查角色、肢體、錯字與相關性。不可將 ChatGPT Plus 當外部 API；若背景工具/額度不可用就保存草稿，不拿低品質重複圖代替。
4. 把文案寫文字檔；執行 `python3 catflow.py prepare --image IMAGE --caption CAPTION --topic TOPIC --style STYLE --source ORIGINAL_PROVENANCE`。Pillow 為現有環境依賴；缺少可由標準 registry 安裝免費套件。JPEG 最大4MB，公開檔移除 EXIF；檔名為圖像SHA256，不覆蓋舊圖。
5. 使用 connector_commit.js 的 connectorCommit 工具適配器保存 asset、draft、gallery。`python3 bundle.py MESSAGE PATH...` 提供 parent/baseTree/files；其 stdout 可在 code mode 內解析，勿對話輸出 base64。讀 adapter 原始碼，作為 async function 在 functions.exec 中執行（tools 為工具物件）。每次寫入前 `git fetch origin main` 更新 origin/main，但若遠端有其他 worker 更新了 state，必須重新 clone/rebase並重作判斷，不用新parent包住舊state。一般 git push 未認證，禁止尋找/公開秘密來替代。
6. 等 GitHub Pages 部署，最多3次、每次間隔至少30秒匿名 GET。`python3 catflow.py check-url --draft DRAFT` 要200、image/jpeg、SHA一致。網址無簽名/到期參數；不是保證永久可用，保留原圖和hash可恢復。
7. policy.mode=draft 時一般輪次到此交草稿，禁止發文。只有 bootstrap 或指定 acceptance_task_id 的一次驗收可例外。live 時可 regular。
8. `python3 catflow.py reserve --draft DRAFT --slot YYYY-MM-DDTHH:MM --purpose regular`（驗收用 acceptance 並傳 --task-id）。先用最新貼文確認無相同文案；以 connectorCommit CAS 保存 state/posts/KEY.json（publishing）成功才繼續。CAS拒絕就停止本輪，不重試發文。此鎖同時阻止相同文案、圖片、時段以及每日超過兩篇。
9. 僅呼叫一次 Windsor execute_action，參數採 reserve 回傳的 execute_action。立即把真實回傳寫檔；`catflow.py receipt --key KEY --result RESULT`。用 adapter 保存 state/posts 與回條。沒有post id保持publishing，先查重，絕不自動重送。
10. Windsor get_fields 後 get_data：account_id/post_id/post_message/post_created_time/permalink_url/full_picture，限定剛發布ID和日期。最多回讀3次、間隔至少60秒，不 force_refresh 升級付費。用 `catflow.py verify --key KEY --rows ROWS` 驗文字+圖片欄位；實際開啟圖片目視後才加 --visual passed。簽名 fbcdn URL 不公開保存，僅記 presence、比對結果與永久貼文網址。
11. 更新 CAT-PAGE-STATUS.md、state/posts、實測證據，同步唯一 Library status file libfile_eb843306062c81919a18f9a9efc211f9（有版本防衝突）。無論哪階段失敗都留下錯誤與下一步。只將安全摘要放公開repo。

## 一次排程驗收
沿用既有6ad6ec1845d48191938f06790c91fe8a，不新增重複每日任務。完整驗收要有 scheduled_for/start/end、A文案、B新原創生圖、C非到期HTTPS URL、D真實post id、E持久記錄、文字/圖片回讀與目視。任一缺失保持mode=draft。成功後可由驗收任務將policy改live並保存證據，既有每日任務會讀policy執行，不需新任務。每日上限2篇（含本輪bootstrap與驗收）；跳過已占用時段。

## 每週成效與異常
先讀 get_fields；用 post_total_media_view_unique（舊post_impressions_unique已deprecated）、post_impressions、post_views、post_reactions_total、post_comments_with_reply、post_activity_by_action_type_share；Page用page_follows/page_daily_follows/page_daily_unfollows。缺值null，回傳0保留0並標資料品質，不填造。
保存 records/insights/DATE.json 與 records/reviews/DATE.json，按post id與已知主題/圖風/文案分類JOIN。新增追蹤只能用Page層級，無法歸因單篇不可分配。至少比較兩個完整7日窗及48小時成熟貼文；沒有前週或樣本少就不稱成效差異。
異常先讀Meta Business Suite（若需登入，記錄待使用者正常授權），未核對前不用可疑觸及算效率。7天先檢查發布/數據/觸及限制，再做單變因測試；14天擴大題材畫風形式；30天且每個對比組至少5篇成熟貼文才評估定位，不每日改名。先用2個小實驗：短三句 vs 情境故事；暖色手繪 vs 自然寫實。主題及時段保持可比，不用當前小樣本斷言勝負。
