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
8. `python3 catflow.py reserve --draft DRAFT --slot YYYY-MM-DDTHH:MM --purpose regular`（驗收用 acceptance 並傳 --task-id）。先用最新貼文確認無相同文案；以 connectorCommit CAS 保存 state/posts/KEY.json（publishing）成功才繼續。CAS拒絕就停止本輪，不重試發文。此鎖同時阻止相同文案、圖片、時段以及超過policy.daily_limit。
9. 僅呼叫一次 Windsor execute_action，參數採 reserve 回傳的 execute_action。立即把真實回傳寫檔；`catflow.py receipt --key KEY --result RESULT`。用 adapter 保存 state/posts 與回條。沒有post id保持publishing，先查重，絕不自動重送。
10. Windsor get_fields 後 get_data：account_id/post_id/post_message/post_created_time/permalink_url/full_picture，限定剛發布ID和日期。最多回讀3次、間隔至少60秒，不 force_refresh 升級付費。用 `catflow.py verify --key KEY --rows ROWS` 驗文字+圖片欄位；實際開啟圖片目視後才加 --visual passed。簽名 fbcdn URL 不公開保存，僅記 presence、比對結果與永久貼文網址。
11. 更新 CAT-PAGE-STATUS.md、state/posts、實測證據，同步唯一 Library status file libfile_eb843306062c81919a18f9a9efc211f9（有版本防衝突）。無論哪階段失敗都留下錯誤與下一步。只將安全摘要放公開repo。

## 一次排程驗收
沿用既有6ad6ec1845d48191938f06790c91fe8a，不新增重複每日任務。完整驗收要有 scheduled_for/start/end、A文案、B新原創生圖、C非到期HTTPS URL、D真實post id、E持久記錄、文字/圖片回讀與目視。任一缺失保持mode=draft。成功後可由驗收任務將policy改live並保存證據，既有每日任務會讀policy執行，不需新任務。每日上限依policy.daily_limit（現為4篇）（含本輪bootstrap與驗收）；跳過已占用時段。

## 每週成效與異常
先讀 get_fields；用 post_total_media_view_unique（舊post_impressions_unique已deprecated）、post_impressions、post_views、post_reactions_total、post_comments_with_reply、post_activity_by_action_type_share；Page用page_follows/page_daily_follows/page_daily_unfollows。缺值null，回傳0保留0並標資料品質，不填造。
保存 records/insights/DATE.json 與 records/reviews/DATE.json，按post id與已知主題/圖風/文案分類JOIN。新增追蹤只能用Page層級，無法歸因單篇不可分配。至少比較兩個完整7日窗及48小時成熟貼文；沒有前週或樣本少就不稱成效差異。
異常先讀Meta Business Suite（若需登入，記錄待使用者正常授權），未核對前不用可疑觸及算效率。7天先檢查發布/數據/觸及限制，再做單變因測試；14天擴大題材畫風形式；30天且每個對比組至少5篇成熟貼文才評估定位，不每日改名。先用2個小實驗：短三句 vs 情境故事；暖色手繪 vs 自然寫實。主題及時段保持可比，不用當前小樣本斷言勝負。

## V3.1 國際實驗（優先於舊台灣單市場選題段落）
先執行 international.py SLOT，依state/international.json取得語言/市場/實驗ID。12:30繁中；19:30英文優先US、其次PH；第2週第9/12天晚間以日文JP替換英文。排除ID/id。不得假設目標市場就是實際觸及市場。既有slot/policy每日上限及mode gate全部保留，任何未知發布先核對。
每輪看美日台Google Trends、可取得的公開FB/Threads、官方新聞與全球寵物/娛樂，至少存5候選含來源/日期/市場/訊號；常青原創題可沒有熱度，寫null。重要新聞核實，不複製迷因文案/品牌圖。英文用自然簡短生活幽默，日文用自然療癒短句；圖片儘量無字跨文化可理解，不強迫投資梗或固定角色。每篇內建ImageGen最多2次並目視QA，不合格留草稿。
prepare加 --language --target-markets --experiment-id（依plan回傳）；保留這些metadata至state/posts。檢查外部今日貼文及全repo未知狀態，CAS預約後才單次發布。隔離fixture不可作未發布新圖再送。
每輪收集已發文48h/168h成熟快照並標observed_at/age_hours/source_metric。用international.measures保留缺值null展示N/A；只有真的reach才計每千觸及互動/分享率，不用viewers冒充reach。國家觸及若無授權欄位/後台資料就N/A，page_fans_country是按讚者國籍，不是貼文國家觸及。新增追蹤只有Page層級就不能分配語言。48h比48h，168h比168h；語言與時段初期混雜，不做因果結論。
每週沿用原任務，把post metadata JOIN快照，按語言/主題/圖風/實際觀測市場比較，至少5篇成熟樣本才評估，仍不稱統計證明。第7天存基準，第14天比較；無成長先查資料/分發，再改一個變因。保留名稱；不因單篇成功轉型、不購買廣告或假流量。成長後才核對Meta限制/資格探索原創IP等營利，未驗資格不宣稱可營利。
本系統依賴已啟用ChatGPT任務與工具權限/額度。Repository與Pages可獨立留存；沒有部署外部免費LLM/ImageGen執行器，不能保證Work/訂閱終止後內容生產仍運作。授權/額度失效記錄並留草稿，不升付費。

## 免費成長追蹤補充（2026-10-25）
每週同時讀state/growth/observations.json、queue.json。Threads/Instagram未授權前僅備稿，禁止以FB權限冒充跨平台權限。每次跨平台發布先核對帳號、權限、平台+內容hash與未知狀態，保存真實回條/網址再回讀；不得使用留言洗版或假互動。新增平台不新增重複FB排程。外部成效只有原生來源/點擊證據可歸因，UTM存在不等於可量測點擊；無證據留N/A。品牌視覺10/25已改、名稱未改，與國際實驗混雜，不稱名稱帶動成長。7/14/30天按既有規則處理。

## Pages驗證備援（2026-10-26）
新草稿CAS上傳會自動啟動 .github/workflows/pages-probe.yml，純驗證、不發FB、不含FB憑證。先用check-url；只有DNS/timeout/連線類錯誤時可讀1小時內同url/hash的Actions回條。HTTP失敗/MIME錯/SHA錯一律停止。主要工具失敗不代表Pages真的故障。
讀GitHub Actions run及verify job成功證據，fetch最新repo的records/pages-proofs；來源須為本repo main上的官方workflow成功run，不能手寫成功JSON。run/source_commit/URL/hash/時間需對應。若新草稿未觸發或回條過期，CAS新增records/pages-requests/唯一請求.json（僅含draft key與時間）會觸發；最多等待3輪、每輪至少30秒。Actions驗證/保存失敗就保留草稿；CAS衝突重新讀最新狀態，不覆蓋。
取得回條後重新檢查policy/posts/外部真實貼文/時段資格，再reserve並CAS存publishing才單次Windsor。不清除鎖、不補第三篇、不跨日補發、不占19:30英文名額。Actions不是新增FB排程，也不會在Work結束後自行發布。若connector新貼文快取未更新，可由正式Facebook貼文UI核對真實ID、全文、圖片並目視，以明確source保存UI驗證，不冒充API full_picture回讀。未知狀態不可重發。

## 使用者提高頻率（2026-10-26，優先於舊每日兩篇描述）
每日最多4篇，台灣09:30英文、12:30繁中、16:30繁中、19:30英文；日文仍只在11/3、11/6的19:30替換。新增時段從10/27開始，不補今天已過09:30/16:30；今天只保留19:30。沿用同一每日task，不新增任務。每slot最多一篇，CAS/未知狀態/圖片URL/原創QA皆保留，生圖額度不足或內容不佳留草稿，不湊數。
3天檢查單篇48h觸及/互動/分享及Page追蹤變化，也看每日總量。比較原12:30/19:30與新增slot，記頻率及語言/題材混雜；總曝光因篇數增加不代表單篇改善。若樣本足且單篇表現或追蹤惡化，三天檢討可減量，禁止加量後忽略品質或洗版。既有14天實驗保留歷史，另記頻率介入，不把舊28slot計畫當新上限。

## 三天即調整（2026-10-26使用者最新要求，優先於舊7天等待）
加量實驗10/27–10/29，首次由既有每日任務於10/29 19:30當輪發布或跳過處理完後檢討，以後每3天一次，記錄last_review_at避免同日重做；不等週日才改。分析同齡48h與每篇/每日整體表現、Page追蹤變化。若無改善先查發布/曝光/分發/資料，資料有效仍持平就當輪保存下一周期的實質內容調整（題材、畫風、形式或頻率擇一），按授權執行，不只寫建議。不動Page ID、發布安全門檻及NT$0限制；不是每3天改名。缺數據不當0，明確記不足且修資料；可進行可逆探索但不宣稱勝負。原14天國際化追蹤和週日完整分析仍保留，標註頻率/內容調整混雜。

## 緊急中斷安全協議2（10/27，優先於舊reserve立即發送描述）
regular reserve只建立reserved(protocol2)，先CAS保存。欲發送時dispatch_guard.arm(state,唯一run owner)產生publishing與nonce；用publish_once.js將該狀態CAS保存並在同一工具執行單次Windsor呼叫。只允許CAS成功者呼叫，CAS失敗不可發送。已arm/publishing不可重新arm或重送；逾時/回條遺失須外部核對。expire僅適用協議2未arm且已跨日reserved，CAS保存not_published前重讀最新；舊protocol1 publishing永不依過期或write_calls=0自動清鎖。保留歷史hash/slot，不重用過期內容。
發文或製圖工具需要user_action就記具體狀態並正常回報，不吞掉錯誤。每輪peek真實daily與weekly，記observed_at/enabled/run狀態；不把GitHub enabled當runtime。任務自行停用後無法由已停用任務自我監測；未另建監控，不保證即時通知。平台API不提供停用審計原因則寫unknown。
三天檢討使用review_due.py判斷到期；即使發文被鎖仍執行研究/檢討。CAS建立records/reviews/cycle-日期.json（running）後才分析；完成保存結果與下一策略，重跑讀running續作、不建立第二份或再套策略。從10/29 19:30起每3天，錯過則下輪補檢討；資料不足不造數據。週日仍保留。

protocol2工具整合：bundle.py對JSON使用utf-8，供publish_once.js核對CAS內容；二進位圖片仍base64。先使用最新同一parent/tree重新檢查policy、所有posts、真實Facebook清單與slot，再prepare arm bundle。publishOnce必須在同一次functions.exec await CAS及單次Windsor，不得把已成功CAS bundle拿到另一輪重播。CAS後中斷的armed狀態仍需人工/外部證據核對，不能自動推定未發送。

## 2026-10-27 最新續作限制
所有更名/名稱研究/頭貼封面簡介修改暫停，直到使用者另行授權。舊f269 publishing結果仍unknown，核對證據見records/reconciliation/2026-10-27-legacy.json；所需後端審計與已備妥未送的查詢內容見provider-audit-request.txt。沒有新證據不無限重做舊查詢；不得清鎖/標verified/繞過全域安全門。任務可繼續研究、草稿與三天/週日分析；只有成功發布的Post ID納入成效樣本，故障缺樣明確標記。Meta UI日期可能為太平洋時間，核對日期須涵蓋原始UTC事件，不把預設截至昨天的空列表當完整否定證明。

## 2026-10-27 範圍隔離策略（使用者最新授權，優先於前述「任一舊未知＝全站停發」規則）
10/26 英文事故 f269fed6aaffbe02af467fe8b7759144aa9a479bce2fb626899a26bdfaa59ba1 仍為 publishing/unknown，不能結案、不能重送、不能補發過期時段。使用者要求更換方法，不可再因此把所有未來全新內容永久封鎖。僅當 state/legacy_quarantine.json 明確 enabled、精確 key/slot/caption SHA/image SHA/證據檔全部吻合、舊文 reconciliation.classification=unknown 且 closure_allowed=false/resend_allowed=false、舊記錄是未採 protocol2 的 publishing、且舊 slot 嚴格早於新 slot 日期，catflow.reserve 才將該筆舊未知排除於「全域阻擋」判斷。原始檔保持 publishing，所有文字/圖片hash查重、相同slot查重、每日上限、當日及其他未知的全域阻擋維持原樣。
新的每個正常時段使用完全不同的原創圖與文字；每輪先查 Facebook/Meta/Windsor 最新真實貼文與最近一次slot，驗證沒有新重複、Windsor權限、Pages公開驗證，依 protocol2 reserved CAS→armed publishing CAS→同一Work工具執行單次 create_photo_post→真實回條→FB UI/API回讀。若外部查詢失敗、Meta出現不明/延遲的舊文、CAS衝突或其他未解新鎖，停止並記錄，不能自動重試。歷史f269保持隔離並等待後端審計；不能改為verified/not_published，不能「全域清鎖」。舊文即使晚到也不會被重送，但仍有平台不可見延遲的殘餘風險，不能宣稱絕對零風險。
此改動只適用10/27以後新時段，不追補已過期slot；同一每日task、不新增重複排程，4篇上限且不為了湊量降品質。品牌更名維持暫停。首次新的 unattended 完整發文+回讀仍須真實驗收，程式規則更新不可當驗收成功。

## 2026-10-27 二進位傳輸修復（最新）
1. 每篇圖片生成後立即保存source_image_file_ref、文案、來源與草稿key；prepare後立即CAS保存JPEG+草稿，先於後續Insights與長篇分析。素材未上傳前不得標公開URL已通過。
2. 優先復原：已有JPEG先比SHA；僅有source_image_file_ref時用Library正常prepare_materialize取原圖，再用同一prepare的JPEG參數重建並比原SHA。不要無條件重生圖。原12:30圖已重建且精確SHA一致。
3. 大型binary bundle不能直接印出整個stdout，避免工具輸出截斷。使用新增connector_bundle.js的loadConnectorBundle(tools,workdir,message,paths)：內部呼叫bundle.py --manifest，對每個binary以--chunk分段24000字元取回base64，Promise.allSettled逐段確認；組裝結果只在functions.exec記憶體中，不text()/notify()全內容。text metadata only。
4. 同一functions.exec讀原connector_commit.js與connector_bundle.js組成函式；await loadConnectorBundle後await connectorCommit。adapter會比較GitHub回傳blob SHA與原始bytes計算的Git blob SHA，通過才建tree/commit並expected_sha CAS。不用git push、不把JPEG當UTF8、不把截斷base64貼回對話修補。CAS敗重讀最新repo重判斷，不重送Facebook。
5. 成功CAS後以原catflow check-url驗Pages匿名200/image/jpeg/SHA；無網路才用既有Actions可信證據。上傳成功不等於公開驗證，更不等於Meta已取圖。
6. 真工具失敗先保存tool_name、公開安全的實際error、stage、run_id、requires_user_action（若平台只回flag但無原因則寫平台未提供），再回報；不得杜撰是權限/配額/超時。真授權提示不可繞過。GitHub目前Allow all actions，Windsor繼承低風險預設；未更改權限，不能僅憑預設判定它造成停用。
7. 下一個正常slot重新研究/去重/驗原創及圖URL→原protocol2 CAS→單次Windsor→即存回條→回讀文字圖/目視；12:30已過不補。全新內容不受精確歷史f269隔離阻擋，所有其他未知照舊阻擋。

## 2026-10-27 16:30 發布授權故障（最新）
8b6bf1...屬protocol2已armed未知，與f269舊例外分開；不得套legacy_quarantine、不得重送、不得依查不到文就結案。原daily目前真實disabled，先保留，不再盲目重啟。新函式僅新增Windsor工具是否存在的CAS前檢查；工具存在不代表已獲背景發布批准。
原始requires_user_action原因/Request ID由工具未提供。GitHub在本輪無人模式已成功寫入，不能歸咎GitHub；Windsor連線/Action/schema/試用有效，但外掛目錄明載寫入需確認，仍要核對當次原始提示。不能把更改權限/拆分任務/換瀏覽器作繞過確認手段。
需要使用者在原已登入ChatGPT的Scheduled→原任務→10/27 16:30紀錄查看待處理工具名稱/提示。不要批准過期貼文。只有畫面明確證明Windsor呼叫尚待執行時，拒絕/取消該待批准動作並保存真實否決回條，才可作結案證據；若無該提示，請OpenAI/Windsor提供原始工具trace/後端action audit。拒絕pending並非刪鎖；仍須依真實回條CAS結案，保留hash/slot，禁止歷史重送。
未確認需要重新OAuth時不盲目重連。Windsor目前Use default/低風險，若要改成Allow all actions，需使用者明確指定該模式；它會擴及該外掛全部動作，不能保證覆蓋provider/platform必需確認。只在實際權限問題處理且未知紀錄安全處置後，恢復原四時段。
Metricool未連接且Free20篇/月不承接4篇/日；Meta官方排程僅見入口，未成功建立或驗收。沒有免費替代已部署，不能宣稱半自動也已成功。每週日分析仍保留enabled；每日停用期間三天檢討設定保留但依賴daily的執行會受阻，10/29前仍需恢復或由使用者明確發起檢討，不偷偷建立重複任務。
