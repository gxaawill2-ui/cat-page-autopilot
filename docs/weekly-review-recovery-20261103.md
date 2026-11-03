# 週日分析續作修復

沿用既有 GitHub 補稿 cron（台北08:17/20:17名義時間，可能延遲），在同一 concurrency 執行唯讀週報。每週日20:00為七日窗口截止；延遲啟動仍使用原截止，不使用未完整當週。舊ChatGPT每週任務保持停用，原因unknown；不得把GitHub替代執行說成舊任務已恢復。

程式 scripts/weekly_performance_review.py；回條 records/reviews/weekly-YYYY-MM-DD.json。已存在cutoff跳過，無Token、錯Page、分頁不完整停止。只GET Facebook、無AI、不發文，沿用現有Secret但不讀出值。已知本人反應排除；未證實外部的正數維持unknown，缺失N/A。過去週報保留；新報告為結構化回讀，不是額外一次內容轉型決策。

99項scripts測試通過；自然週日執行仍待11/8截止後觀測。真review_only驗收待紀錄。
