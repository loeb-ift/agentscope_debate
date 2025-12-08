from agentscope.agent import AgentBase
from typing import Dict, Any
import redis
import json
import re
from worker.llm_utils import call_llm
from worker.tool_config import get_tools_description, get_recommended_tools_for_topic, STOCK_CODES, CURRENT_DATE
from api.prompt_service import PromptService
from api.database import SessionLocal

class Chairman(AgentBase):
    """
    主席智能體，負責主持辯論、賽前分析和賽後總結。
    """

    def __init__(self, name: str, **kwargs: Any):
        super().__init__()
        self.name = name

    def speak(self, content: str):
        """
        主席發言。
        """
        print(f"Chairman '{self.name}': {content}")

    def pre_debate_analysis(self, topic: str) -> Dict[str, Any]:
        """
        執行賽前分析的 7 步管線。
        """
        print(f"Chairman '{self.name}' is starting pre-debate analysis for topic: '{topic}'")

        # 獲取推薦工具
        recommended_tools = get_recommended_tools_for_topic(topic)
        tools_desc = get_tools_description()
        
        # 使用 PromptService 獲取 Prompt
        db = SessionLocal()
        try:
            default_prompt = f"""# 辯論賽前分析提示詞 v2.0
## 增強時間維度感知版

---

## 📌 核心理念
你是辯論賽的**主席與分析師**，任務是進行**時間敏感型的深度賽前分析**。辯題的價值往往隱藏在**過去→現在→未來**的時間軸上，需要識別「為什麼現在辯論這個問題」。

---

## ⏰ 當前時間基準（動態）

**{{{{CURRENT_DATE}}}}** ← 這是「現在」，會根據實際日期動態更新

### 時間計算邏輯：
```
過去時間點 = 當前日期 - N年/月/天
未來時間點 = 當前日期 + N年/月/天
相對時間 = 事件年份 與 當前日期的差距
```

### 根據當前日期動態判斷：

**季節與周期性判斷**：
- 若當前月份 = 1-3月 → 「年初」、新預算年開始、春季政策推行期
- 若當前月份 = 4-6月 → 「上半年中期」、中期評估期、二季度數據發佈期
- 若當前月份 = 7-9月 → 「下半年開始」、秋季調整期、年度預算中期檢視
- 若當前月份 = 10-12月 → 「年底」、年度結算期、來年規劃期

**數據可得性動態評估**：
- 上一完整年度數據：應已發佈 ✅
- 當前年度數據：部分發佈 ⚠️
- 未來年度數據：僅預測可得 🔮

**政策窗口動態識別**：
- 當前日期 ±30天：「近期」政策推行
- 當前日期 ±1年：「本年度」政策評估
- 當前日期 ±5年：「中期」規劃
- 當前日期 ±10年+：「長期」戰略

### 時間距離參考表（自動計算）：

| 時間參考 | 距今 | 說明 |
|---------|------|------|
| 5年前 | {{{{DATE_5_YEARS_AGO}}}} | 長期趨勢起點 |
| 3年前 | {{{{DATE_3_YEARS_AGO}}}} | 中期變化分析 |
| 1年前 | {{{{DATE_1_YEAR_AGO}}}} | 年度對比 |
| **現在** | **{{{{CURRENT_DATE}}}}** | **分析基準點** |
| 1年後 | {{{{DATE_1_YEAR_FUTURE}}}} | 短期預測 |
| 3年後 | {{{{DATE_3_YEARS_FUTURE}}}} | 中期規劃 |
| 5年後 | {{{{DATE_5_YEARS_FUTURE}}}} | 長期展望 |

**分析時應自動套用：所有時間參考都相對於「現在」計算，而非固定值。**

---

## 步驟 0：時間脈絡定位（優先執行）
**在開始其他分析前，必須回答**：

### 0.1 時間點判斷
- **辯題提出的時間戳**：何時首次出現（距今多久）？
- **當前時間節點**：{{{{CURRENT_DATE}}}} 是什麼階段（醞釀期/高峰期/轉折期/衰退期）？
- **歷史參照點**：過去有相似議題的關鍵時刻嗎（相對距今多少年）？

### 0.2 時間敏感度評估
| 時間跨度 | 分析重點 | 證據來源 | 示例時間 |
|---------|---------|---------|---------|
| **過去（{{{{DATE_5_YEARS_AGO}}}} 至 {{{{DATE_1_YEAR_AGO}}}}）** | 歷史背景、前案例、失敗教訓 | 學術回顧、新聞檔案、統計趨勢 | 5-1年前 |
| **現在（{{{{DATE_1_YEAR_AGO}}}} 至 {{{{CURRENT_DATE}}}}）** | 觸發事件、政策動向、民意變化 | 最新數據、新聞報導、即時調查 | 近1年內 |
| **近期未來（{{{{CURRENT_DATE}}}} 至 {{{{DATE_3_YEARS_FUTURE}}}}）** | 實施難度、短期影響、替代方案 | 專家預測、技術預測、政策規劃 | 今起3年 |
| **遠期未來（{{{{DATE_3_YEARS_FUTURE}}}} 至 {{{{DATE_5_YEARS_FUTURE}}}}）** | 結構性變化、長期代價、代際影響 | 趨勢分析、模型預測、倫理評估 | 3-5年後 |

### 0.3 時間衝突點識別
- **短期vs長期衝突**：什麼措施短期有效但長期有害？反之？
- **政治周期vs結構周期**：選舉週期內難以看到的效果是什麼？
- **不同群體的時間視角**：誰希望加速？誰希望延遲？為什麼？

---

## 步驟 1：類型識別 + 時間維度
**辯題分類必須納入時間視角**：

### 1.1 辯題類型（事實型/價值型/政策型）

### 1.2 核心爭議領域
（政治/經濟/社會/科技/倫理等）

### 1.3 時空範疇（**重點強化**）
- **時間跨度**：
  - ⏳ 當代議題（當下爭論）vs
  - 📚 歷史性議題（追溯根源） vs
  - 🔮 預測性議題（涉及未來）
  
- **時間急迫性**：
  - 🚨 高度時效性（需要立即行動）
  - ⚖️ 中度時效性（逐步推進可接受）
  - 🧘 低度時效性（長期規劃）

- **節點性**：
  - 📍 是否存在「決策窗口」？
  - 📍 錯過這個時間點的後果？
  - 📍 提前/延後行動的成本差異？

### 1.4 價值衝突類型
（自由vs秩序、效率vs公平、當下vs未來等）

---

## 步驟 2：核心要素提取 + 時間維度
基於辯題類型，識別時間相關的核心要素：

### 2.1 六大要素（原有）
1. 行動主體（Actor）
2. 行動內容（Action）
3. 政策工具（Instrument）
4. 目標群體（Target）
5. 預期目標（Goal）
6. 隱含假設（Assumptions）

### 2.2 **新增時間要素**
- **時間框架**：政策/行動的預定執行期限是多久？
- **臨界點**：是否有「不得不行動」的時間閾值？
- **滯後效應**：行動和效果之間的時間延遲是多少？
- **可逆性**：這個決定是否可以回頭？翻轉需要多久？
- **路徑依賴**：早期決定如何鎖定未來選項？

---

## 步驟 3：因果鏈建構 + 時間映射

### 3.1 **正方因果鏈**（至少3條主要路徑）
**格式**：政策/行動 → **[時間點]** → 中間機制 → **[時間點]** → 預期效果

**例示**：
```
提高碳稅
  ↓ [立即]
激勵企業轉向綠能投資
  ↓ [1-3年]
綠能產業規模擴大、成本下降
  ↓ [3-5年]
碳排放量減少、達成氣候目標
```

### 3.2 **反方因果鏈**（至少3條主要路徑）
**格式**：政策/行動 → **[時間點]** → 副作用/障礙 → **[時間點]** → 負面後果

**重點**：標注「滯後效應」何時爆發

```
碳稅政策
  ↓ [立即]
企業成本上升
  ↓ [3-6月]
產品價格上漲、低收入戶購買力下降
  ↓ [1-2年]
社會不滿、政治反彈、政策反轉
```

### 3.3 **因果鏈強度評估**
| 強度 | 證據時效 | 判斷標準 |
|------|---------|---------|
| 🔴 強 | 短期內驗證（<1年） | 機制明確、案例眾多、因果直接 |
| 🟡 中 | 中期驗證（1-5年） | 存在干擾變數、案例有限、因果間接 |
| 🟠 弱 | 長期難驗證（5年+） | 假設眾多、缺乏先例、需多重條件 |

### 3.4 **關鍵斷點與時間敏感性**
- 哪些環節最容易被質疑？
- 這些斷點什麼時候會暴露（立即/延遲/永不）？
- 雙方如何利用「時間差」來論證？

---

## 步驟 4：子問題分解 + 時間視角

**將辯題拆解為5-8個可驗證的關鍵子問題**：

### 4.1 **可行性問題**（技術/資源/制度層面）
- Q1: 在當前技術條件下可行嗎？（現在時點）
- Q2: 技術進步會如何改變可行性？（3-5年內）

### 4.2 **效果問題**（是否達到預期目標）
- Q3: 短期能看到效果嗎？（<1年）
- Q4: 長期效果會否逆轉？（5年+）

### 4.3 **代價問題**（成本/副作用/機會成本）
- Q5: 初期投入成本多大？（前期）
- Q6: 隱藏成本何時顯現？（延遲爆發點）

### 4.4 **時序與比較問題**
- Q7: 現在行動vs延後行動，哪個成本更低？
- Q8: 與替代方案相比，時間效益如何？

### 4.5 **價值與代際問題**
- Q9: 這個決定如何影響不同代際？（當代vs下一代）
- Q10: 短期犧牲是否值得長期收益？

---

## 步驟 5：資料蒐集戰略 + 時間優先級

### 5.1 **優先級排序**（按時間緊迫性）

**Tier 1（立即需要）**：
- 當前政策狀態、最新數據、觸發事件
- 搜索：2024年後的最新報導、數據

**Tier 2（關鍵支撐）**：
- 過去5年的類似案例、中期效果數據
- 搜索：學術研究、案例研究、統計趨勢

**Tier 3（深度論證）**：
- 長期理論預測、歷史對比、倫理評估
- 搜索：經典文獻、專家評論、模型預測

### 5.2 **資訊來源**（按時效性分類）
- **實時數據**：新聞、官方數據庫、市場指標
- **短期數據**（1-3年）：行業報告、政策評估、調查問卷
- **中期數據**（3-10年）：學術研究、統計年鑑、案例分析
- **長期數據**（10年+）：歷史檔案、結構變化研究、理論框架

### 5.3 **搜索關鍵詞**（含時間修飾詞）
- 「XXX 2024」「XXX 最新」「XXX 現況」
- 「XXX 案例 歷史」「XXX 過去 教訓」
- 「XXX 預測」「XXX 未來 趨勢」
- 「XXX 長期影響」「XXX 短期效果」

### 5.4 **時效性要求矩陣**
| 子問題 | 需要最新數據 | 可用歷史數據 | 優先搜索時間範圍 |
|--------|------------|------------|-----------|
| 當前可行性 | ✅ | ❌ | {{{{DATE_1_YEAR_AGO}}}} 至 {{{{CURRENT_DATE}}}} |
| 短期效果 | ✅ | ⚠️ | {{{{DATE_3_YEARS_AGO}}}} 至 {{{{CURRENT_DATE}}}} |
| 長期趨勢 | ❌ | ✅ | {{{{DATE_5_YEARS_AGO}}}} 至 {{{{CURRENT_DATE}}}} |
| 代替方案 | ✅ | ✅ | {{{{DATE_3_YEARS_AGO}}}} 至 {{{{CURRENT_DATE}}}} |

---

## 步驟 6：主席手卡生成（時間視角）

### 【辯論基礎資訊】
- 辯題內容
- 辯論背景與觸發事件（**為什麼現在辯這個**）
- **時間節點**：當前處於該議題的哪個階段

### 【時間脈絡梳理】
**過去** ← 根源與先例
**現在** ← 觸發點與當前困境
**未來** ← 預期與風險

### 【正方論證架構】（主線1-3）
每條包含：
- 論點
- 時間機制（何時發生、為何有效）
- 證據（來自哪個時期）
- 關鍵時間預期

### 【反方論證架構】（主線1-3）
每條包含：
- 論點
- 副作用何時顯現（滯後效應）
- 反例與歷史教訓
- 時間風險點

### 【關鍵交鋒點】
- 爭議點
- 雙方立場
- **時間維度的分歧**（短期vs長期、立即vs延遲）
- 判準

### 【數據與案例庫】
- 關鍵統計（標註數據年份）
- 成功案例（何時成功、條件是什麼）
- 失敗案例（何時失敗、原因是什麼）
- **時間對比**：相同政策在不同時期的不同結果

### 【主席引導問題庫】（10-15題）

**時間維度問題**：
- Q1: 你說這個政策要X年見效，這個時間框架有根據嗎？
- Q2: 短期成本和長期收益，哪個對你的論點更重要？
- Q3: 歷史上類似的政策，從決策到效果出現用了多久？
- Q4: 如果現在不採取行動，5年後會如何？
- Q5: 這個政策是否可逆？如果失敗了多久才能糾正？

### 【時間管理建議】
- 全場用時配置
- 何時應該深入時間論證
- 雙方容易在時間上的邏輯漏洞

---

## 步驟 7：工具策略映射 + 時間層級

### 【工具使用決策樹】
```
IF 需要最新數據（2024後）→ web_search + 年份篩選
IF 需要過去案例對比 → web_fetch 文章 + 歷史檔案
IF 需要台灣上市櫃財務（含時間序列）→ TEJ 工具
IF 需要長期趨勢圖表 → web_search + 學術資料庫
IF 需要完整報告 → web_fetch
IF 需要專業權威 → .edu / .gov / 學術期刊
```

### 【按時間層級的搜索策略】

**層級1：立即層（{{{{CURRENT_DATE}}}} 至 {{{{DATE_3_MONTHS_FUTURE}}}}）**
- 工具：web_search（最新新聞、官方公告）
- 關鍵詞：「最新」「現在」「{{{{CURRENT_MONTH}}}}」
- 例：「台灣AI政策 {{{{CURRENT_YEAR}}}}最新進展」

**層級2：過往層（{{{{DATE_5_YEARS_AGO}}}} 至 {{{{DATE_3_MONTHS_AGO}}}}）**
- 工具：web_fetch（學術論文、新聞檔案、案例研究）
- 關鍵詞：「案例」「分析」「評估」「過去」
- 例：「綠能轉型 各國案例對比」

**層級3：預測層（{{{{DATE_1_YEAR_FUTURE}}}} 至 {{{{DATE_5_YEARS_FUTURE}}}}）**
- 工具：web_search（專家評論、趨勢預測）
- 關鍵詞：「趨勢」「預測」「{{{{NEXT_YEAR}}}}」「未來」
- 例：「AI對就業 長期結構影響」

### 【結果存儲建議】
按時間維度組織：
```
過去數據庫
├─ 歷史案例
├─ 失敗教訓
└─ 趨勢回顧

現在數據庫
├─ 最新政策
├─ 當前困境
└─ 觸發事件

未來數據庫
├─ 預期效果
├─ 風險評估
└─ 替代方案
```

### 外部工具描述:
{{tools_desc}}

### 股票代碼列表:
{{stock_codes}}

---

## 步驟 8：時間敏感性綜合評分

**評分維度**：

| 維度 | 評分點 | 說明 |
|------|-------|------|
| **時間急迫性** | 1-5 | 是否存在「現在不做就來不及」的窗口？ |
| **滯後效應複雜性** | 1-5 | 政策效果展現時間有多長、多難預測？ |
| **時間爭議性** | 1-5 | 雙方對時間框架的分歧有多大？ |
| **歷史案例豐富度** | 1-5 | 過去案例有多豐富？足以支撐論證嗎？ |

**綜合評分** = 各維度平均
- 4.0-5.0：時間維度是該辯題的核心
- 2.5-3.9：時間維度重要但不決定性
- 1.0-2.4：時間維度為補充論點

---

## 📊 最終輸出格式（JSON）

```json
{{
    "step0_temporal_positioning": {{
        "debate_timestamp": "...",
        "current_phase": "...",
        "historical_reference": "...",
        "temporal_sensitivity": "...",
        "temporal_conflict_points": "..."
    }},
    "step1_type_classification": "...",
    "step2_core_elements": "...",
    "step3_causal_chain": {{
        "affirmative_chains": "...",
        "negative_chains": "...",
        "temporal_strength_assessment": "...",
        "critical_breakpoints": "..."
    }},
    "step4_sub_questions": "...",
    "step5_research_strategy": {{
        "priority_ranking": "...",
        "information_sources": "...",
        "temporal_keywords": "...",
        "timeliness_matrix": "..."
    }},
    "step6_handcard": {{
        "basic_info": "...",
        "temporal_context": "...",
        "affirmative_arguments": "...",
        "negative_arguments": "...",
        "key_confrontation_points": "...",
        "temporal_data_cases": "...",
        "guiding_questions": "...",
        "time_management": "..."
    }},
    "step7_tool_strategy": {{
        "decision_tree": "...",
        "temporal_search_strategy": "...",
        "storage_recommendation": "..."
    }},
    "step8_temporal_sensitivity_score": {{
        "urgency": 0,
        "lag_effect_complexity": 0,
        "temporal_controversy": 0,
        "case_richness": 0,
        "composite_score": 0
    }}
}}
```

---

## 🎯 核心提醒

✅ **時間是隱藏的維度**：辯手往往忽視時間框架的不同，導致雞同鴨講
✅ **「現在」是相對的**：同一政策在不同歷史時期有完全不同的效果
✅ **滯後效應是陷阱**：許多政策短期見效長期失效（或反之），要抓住這個爭議點
✅ **決策窗口有限**：識別「為什麼現在必須決定」是最有力的論證
✅ **案例要附時間戳**：說「日本案例」不如說「2011年日本能源改革」

---

**現在，請提供你的辯題，我將按照此優化框架執行完整的時間敏感型分析！** ⏰📊🎯
"""
            template = PromptService.get_prompt(db, "chairman.pre_debate_analysis", default=default_prompt)
            # Fill dynamic variables
            # Need to replace temporal variables in the template manually or ensure they are passed if they were placeholders
            # The new prompt uses Jinja2-style {{VAR}} but Python format expects {VAR}.
            # Since we use template.format(), we need to provide the values.
            # However, the updated prompt has many more variables like DATE_5_YEARS_AGO etc.
            # We should calculate them.
            
            from datetime import datetime, timedelta
            now = datetime.strptime(CURRENT_DATE, "%Y-%m-%d")
            
            format_vars = {
                "tools_desc": tools_desc,
                "stock_codes": chr(10).join([f"- {name}: {code}" for name, code in STOCK_CODES.items()]),
                "recommended_tools": ', '.join(recommended_tools),
                "CURRENT_DATE": CURRENT_DATE,
                "CURRENT_YEAR": now.year,
                "CURRENT_MONTH": now.month,
                "NEXT_YEAR": now.year + 1,
                "DATE_5_YEARS_AGO": (now - timedelta(days=365*5)).strftime("%Y-%m-%d"),
                "DATE_3_YEARS_AGO": (now - timedelta(days=365*3)).strftime("%Y-%m-%d"),
                "DATE_1_YEAR_AGO": (now - timedelta(days=365*1)).strftime("%Y-%m-%d"),
                "DATE_3_MONTHS_AGO": (now - timedelta(days=90)).strftime("%Y-%m-%d"),
                "DATE_3_MONTHS_FUTURE": (now + timedelta(days=90)).strftime("%Y-%m-%d"),
                "DATE_1_YEAR_FUTURE": (now + timedelta(days=365*1)).strftime("%Y-%m-%d"),
                "DATE_3_YEARS_FUTURE": (now + timedelta(days=365*3)).strftime("%Y-%m-%d"),
                "DATE_5_YEARS_FUTURE": (now + timedelta(days=365*5)).strftime("%Y-%m-%d"),
            }
            
            # Note: PromptService.get_prompt likely returns the raw content which has {{VAR}} style.
            # If standard python format() is used, double braces {{ }} are escape for single brace {.
            # But here the prompt uses {{VAR}} intending for replacement.
            # If the stored prompt uses {{VAR}}, python format() won't replace it unless keys match exactly like {VAR} or we do string replacement.
            # Assuming the prompt stored in DB is exactly as provided (with {{VAR}}),
            # and we want to replace {{VAR}} with value.
            # Python's format() uses {VAR}. So we might need to pre-process the template
            # to replace {{VAR}} with {VAR} or just use string replace for {{VAR}}.
            # Given the previous code used .format(), the previous prompt likely used {VAR}.
            # The NEW prompt provided by user uses {{VAR}}.
            # We should replace {{VAR}} with value directly.
            
            system_prompt = template
            for key, value in format_vars.items():
                system_prompt = system_prompt.replace(f"{{{{{key}}}}}", str(value))
        finally:
            db.close()
        prompt = f"請對以下辯題進行分析：{topic}"
        
        response = call_llm(prompt, system_prompt=system_prompt)
        
        try:
            # 使用 Regex 提取 JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # 嘗試修復常見的 JSON 格式錯誤 (如未轉義的換行符)
                try:
                    analysis_result = json.loads(json_str, strict=False)
                except json.JSONDecodeError:
                    # 如果 strict=False 仍然失敗，嘗試手動替換換行符
                    # 這是一個簡單的啟發式替換，將不在引號外的換行符替換為 \n
                    # 但對於複雜的嵌套 JSON 可能不夠完美
                    fixed_json_str = json_str.replace('\n', '\\n')
                    analysis_result = json.loads(fixed_json_str, strict=False)
            else:
                raise ValueError("No JSON object found in response")
            
            # 為了兼容舊代碼，將 step6_handcard 映射為 step5_summary (因為 debate_cycle.py 使用此 key)
            if "step6_handcard" in analysis_result:
                analysis_result["step5_summary"] = analysis_result["step6_handcard"]
            elif analysis_result.get("step5_summary") is None: # Only if neither handcard nor summary exists
                # 嘗試從其他欄位構建摘要
                summary_parts = []
                if "step1_type_classification" in analysis_result:
                    summary_parts.append(f"題型：{analysis_result['step1_type_classification']}")
                elif "step1_type" in analysis_result: # Backward compatibility
                    summary_parts.append(f"題型：{analysis_result['step1_type']}")
                    
                if "step2_elements" in analysis_result: # Same key in new prompt? No, new is same step2_core_elements?
                    # Wait, prompt says: step2_core_elements. Old code: step2_elements.
                    summary_parts.append(f"關鍵要素：{analysis_result['step2_elements']}")
                elif "step2_core_elements" in analysis_result:
                    summary_parts.append(f"關鍵要素：{analysis_result['step2_core_elements']}")
                    
                if "step5_research_strategy" in analysis_result:
                    summary_parts.append(f"資料蒐集戰略：{analysis_result['step5_research_strategy']}")
                
                if summary_parts:
                    analysis_result["step5_summary"] = "\n".join(summary_parts)
                else:
                    print(f"WARNING: LLM Analysis JSON missing key fields. Keys found: {list(analysis_result.keys())}")
                    analysis_result["step5_summary"] = f"分析完成，但在提取摘要時遇到問題。完整回應如下：\n{json.dumps(analysis_result, ensure_ascii=False, indent=2)}"

        except Exception as e:
            print(f"Error parsing analysis result: {e}. Raw response: {response}")
            # Fallback structure
            analysis_result = {
                "step1_type_classification": "未識別",
                "step2_core_elements": "未提取",
                "step3_causal_chain": "未建構",
                "step4_sub_questions": "未拆解",
                "step5_research_strategy": "未規劃",
                "step6_handcard": response if response else "分析失敗，無法生成主席手卡。",
                "step7_tool_strategy": ", ".join(recommended_tools),
                "step5_summary": response if response else "分析失敗，無法生成摘要。" # 兼容性
            }

        # Debug: 確認 step5_summary 存在
        print(f"DEBUG: analysis_result keys: {list(analysis_result.keys())}")
        summary_value = analysis_result.get('step5_summary', 'KEY_NOT_FOUND')
        summary_preview = str(summary_value)[:200] if summary_value else "EMPTY"
        print(f"DEBUG: step5_summary value: {summary_preview}")
        
        print(f"Pre-debate analysis completed.")
        return analysis_result

    def summarize_round(self, debate_id: str, round_num: int, handcard: str = ""):
        """
        對本輪辯論進行總結，基於賽前手卡進行評估。
        """
        print(f"Chairman '{self.name}' is summarizing round {round_num}.")
        
        redis_client = redis.Redis(host='redis', port=6379, db=0)
        evidence_key = f"debate:{debate_id}:evidence"
        
        # 獲取本輪累積的證據/工具調用
        evidence_list = [json.loads(item) for item in redis_client.lrange(evidence_key, 0, -1)]
        
        # 構建證據摘要 (應用簡單的緊湊化策略)
        compact_evidence = []
        for e in evidence_list:
            content = e.get('content', str(e))
            if len(content) > 500:
                content = content[:200] + "...(略)..." + content[-200:]
            compact_evidence.append(f"- {e.get('role', 'Unknown')}: {content}")
            
        evidence_text = "\n".join(compact_evidence)
        
        # 這裡理想情況下應該也要獲取本輪的發言內容 (需從 Redis log stream 或 DB 獲取)
        # 暫時依賴 evidence_list 作為代理，或者假設 debate_cycle 會傳入上下文
        
        db = SessionLocal()
        try:
            default_prompt = """你是辯論賽主席。你的任務是總結第 {round_num} 輪辯論。
請根據賽前分析的【主席手卡】進行評估：

{handcard}

請回答：
1. 本輪雙方是否觸及關鍵交鋒點？
2. 提出的證據是否有效支持了論點？
3. 下一輪辯論應該聚焦什麼問題？

請保持中立、專業，並給出具體引導。"""
            
            template = PromptService.get_prompt(db, "chairman.summarize_round", default=default_prompt)
            system_prompt = template.format(round_num=round_num, handcard=handcard)
        finally:
            db.close()

        user_prompt = f"""本輪收集到的證據與發言摘要：
{evidence_text}

請進行總結："""

        if not evidence_list:
            user_prompt += "\n(本輪未收集到具體證據工具調用)"

        summary = call_llm(user_prompt, system_prompt=system_prompt)
        
        prefix = f"【第 {round_num} 輪總結】\n"
        final_summary = prefix + summary
        self.speak(final_summary)
        
        # 清除本輪證據 (準備下一輪)
        redis_client.delete(evidence_key)
        return final_summary

    def summarize_debate(self, debate_id: str, topic: str, rounds_data: list, handcard: str = "") -> str:
        """
        對整場辯論進行最終總結。
        """
        print(f"Chairman '{self.name}' is making the final conclusion.")
        
        # 構建辯論摘要
        summary_text = f"辯題：{topic}\n\n"
        for round_data in rounds_data:
            summary_text += f"--- 第 {round_data['round']} 輪 ---\n"
            # 動態遍歷所有團隊的發言
            for key, value in round_data.items():
                if key.endswith("_content"):
                    side = key.replace("_content", "")
                    agent_name = round_data.get(f"{side}_agent", "Unknown")
                    summary_text += f"團隊 {side} ({agent_name}): {str(value)[:200]}...\n"
            
            summary_text += f"回合總結: {str(round_data.get('summary', ''))[:200]}...\n\n"
            
        db = SessionLocal()
        try:
            default_prompt = """你是辯論賽主席。辯論已經結束。
你的任務是根據賽前分析的【主席手卡】以及整場辯論的過程，做出最終的【有意義的結論】。

{handcard}

請在結論中包含：
1. 勝負判定（或優勢方判定），基於邏輯與證據強度。
2. 核心觀點梳理：雙方最強的論點是什麼？
3. 價值昇華：這場辯論帶給我們什麼啟示？

請務必保持客觀、公正、深度。"""
            template = PromptService.get_prompt(db, "chairman.summarize_debate", default=default_prompt)
            system_prompt = template.format(handcard=handcard)
        finally:
            db.close()

        user_prompt = f"""整場辯論記錄摘要：
{summary_text}

請進行最終總結："""

        final_conclusion = call_llm(user_prompt, system_prompt=system_prompt)
        
        self.speak(f"【最終總結】\n{final_conclusion}")
        return final_conclusion