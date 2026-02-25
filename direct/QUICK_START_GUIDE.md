# YANDEX DIRECT QUICK START GUIDE
## Wave 1 Campaign Setup (35 Priority Routes)

---

## STEP 1: CAMPAIGN STRUCTURE (15 minutes)

### Create 2 Campaign Groups:

**Campaign A: Mega-Volume Routes (13 routes)**
- Daily budget: ₽30,000
- Geo: All Russia
- Schedule: 24/7
- Device: All devices (desktop, mobile, tablet)
- Bidding: Manual CPC

**Campaign B: Premium Zero-Competition Routes (22 routes)**
- Daily budget: ₽20,000
- Geo: All Russia
- Schedule: 24/7
- Device: All devices
- Bidding: Manual CPC

---

## STEP 2: IMPORT ROUTES (5 minutes)

### Use `wave1_priority_routes.csv`

**Required mappings:**
```
URL column       → Final URL
gorod1 column    → Ad text field (departure city)
gorod2 column    → Ad text field (arrival city)
price column     → Ad extension (price)
```

**Starting CPC by competition level:**
```
Competition 0    → ₽25
Competition 1-5  → ₽35
Competition 6-15 → ₽50
```

---

## STEP 3: AD COPY TEMPLATES (10 minutes)

### Template 1: Direct + Price Focus
```
Title 1: Такси {gorod1} - {gorod2}
Title 2: От {price}₽ | Заказать онлайн
Text: Межгород {gorod1}-{gorod2}. Цена от {price}₽. 
      Комфортные авто. Опытные водители. Заказ за 2 минуты!
Display URL: city2city.ru
```

### Template 2: Comfort + Speed Focus
```
Title 1: {gorod1} → {gorod2} на такси
Title 2: Быстро, удобно, безопасно
Text: Трансфер {gorod1}-{gorod2}. Встретим с табличкой. 
      Фиксированная цена {price}₽. Без скрытых доплат.
Display URL: city2city.ru
```

### Template 3: Trust + Convenience
```
Title 1: Такси {gorod1}-{gorod2} {price}₽
Title 2: Бронируйте в 1 клик
Text: Надежный сервис. 5000+ довольных пассажиров. 
      Онлайн-оплата. Гарантия качества. От {price}₽.
Display URL: city2city.ru
```

**Recommendation:** Test all 3 templates, pause underperformers after 50 clicks

---

## STEP 4: EXTENSIONS & ENHANCEMENTS (10 minutes)

### Sitelinks (Add 4-6):
```
✓ О компании
✓ Цены на все направления
✓ Контакты
✓ Отзывы клиентов
✓ Способы оплаты
✓ Часто задаваемые вопросы
```

### Callouts (Add 4-6):
```
✓ Без предоплаты
✓ Опытные водители
✓ Комфортные авто
✓ Работаем 24/7
✓ Фиксированная цена
✓ Онлайн-бронирование
```

### Price Extensions:
```
Format: Такси {gorod1}-{gorod2} — от {price}₽
```

### Call Extension:
```
Phone: +7 (XXX) XXX-XX-XX
Schedule: 24/7
Click-to-call: Enabled
Call tracking: REQUIRED (set up before launch)
```

---

## STEP 5: TARGETING SETTINGS (5 minutes)

### Geographic Targeting:
```
Primary: All Russia (федеральный таргет)
Adjust by route if needed (most routes are intercity, broad OK)
```

### Audience Targeting:
```
❌ Do NOT use narrowing audiences (you'll miss traffic)
✓ Add observation audiences:
  - Previous site visitors (bid +20%)
  - Taxi service searches (bid +10%)
  - Travel intent (bid +10%)
```

### Keyword Match Types:
```
Exact match: [такси {gorod1} {gorod2}]
Phrase match: "такси {gorod1} {gorod2}"
Broad match: +такси +{gorod1} +{gorod2}

Start with exact + phrase, add broad after Week 1 if CPL < target
```

### Negative Keywords (CRITICAL):
```
добавить бесплатно
вакансии
работа
подработка
зарплата
скачать
торрент
игра
приложение
```

---

## STEP 6: CONVERSION TRACKING (CRITICAL - 20 minutes)

### Yandex Metrica Goals:

**Goal 1: Form Submission**
```
Goal type: JavaScript event
Trigger: Order form submit button clicked
Goal name: route_order_submitted
```

**Goal 2: Phone Call Click**
```
Goal type: JavaScript event  
Trigger: Phone number link clicked
Goal name: phone_click
```

**Goal 3: Call Tracking**
```
Integration: Connect call tracking provider
Track: Calls >30 seconds = conversion
Goal name: phone_call_qualified
```

**Goal 4: Order Completed (Revenue Goal)**
```
Goal type: URL visit
URL: /order-confirmed
Revenue tracking: YES (pass order value)
Goal name: order_completed
```

### Connect to Yandex Direct:
```
Direct → Settings → Goals → Import from Metrica
Select all 4 goals above
Primary goal: order_completed
```

---

## STEP 7: BID STRATEGY (IMPORTANT)

### Week 1: Manual CPC Bidding
```
Starting CPCs:
- Competition 0:     ₽25
- Competition 1-5:   ₽35  
- Competition 6-15:  ₽50

Adjust every 2 days based on:
- If avg position >3 → increase bid +20%
- If avg position <2 and CPC >₽60 → decrease bid -15%
- If CR >5% → increase bid to position 1
- If CR <1% after 50 clicks → pause route
```

### Week 2+: Consider Auto-Bidding
```
If Week 1 ROI >15x → Switch to "Maximum Conversions"
Target CPA: ₽1,500 (adjust based on actual Week 1 data)
```

---

## STEP 8: DAILY MONITORING CHECKLIST

### Morning Check (9:00 AM):
```
☐ Check daily spend (should be ₽30-50K)
☐ Review avg CPC (target: ≤₽50)
☐ Check conversion count (target: 15-30/day)
☐ Identify any paused campaigns (fix issues)
☐ Check search query report (add negatives)
```

### Evening Check (6:00 PM):
```
☐ Review avg position (target: 1-3)
☐ Check daily ROI (target: >10x)
☐ Pause routes with CPC >₽100
☐ Increase budget if hitting limit early
☐ Export performance report for analysis
```

---

## STEP 9: OPTIMIZATION TRIGGERS

### Pause Route If:
```
❌ CPC >₽100 for 3+ consecutive days
❌ CR <1% after 50+ clicks
❌ ROI <5x after 100+ clicks
❌ Quality score drops to "Low"
```

### Increase Bid If:
```
✓ ROI >20x and avg position >2
✓ CR >5% consistently
✓ Impression share <50% (losing due to rank)
✓ Competition increased (new ads appeared)
```

### Decrease Bid If:
```
↓ Avg position =1 and CPC >₽60
↓ ROI 10-15x (still good, but optimize margin)
↓ Impression share >80% (already dominating)
```

---

## STEP 10: WEEK 1 SUCCESS CRITERIA

### Target Metrics (Cumulative Week 1):
| Metric | Target | Red Flag |
|--------|--------|----------|
| Total Spend | ₽350K-₽500K | <₽200K or >₽700K |
| Total Clicks | 7,000-10,000 | <3,000 |
| Avg CPC | ≤₽50 | >₽70 |
| CTR | ≥5% | <2% |
| Conversions | 210-500 | <60 |
| Avg CR | ≥3% | <1.5% |
| Total Revenue | ₽6M-₽15M | <₽2M |
| ROI | ≥10x | <5x |

### Decision Tree (End of Week 1):

**If ROI >20x:**
→ Immediately launch Wave 2 (65 routes)
→ Increase Wave 1 budget to ₽75K/day

**If ROI 10-20x:**
→ Continue Wave 1 optimization for Week 2
→ Prepare Wave 2 launch for Week 3

**If ROI 5-10x:**
→ Investigate underperformers
→ Test new ad copy variations
→ Check landing page conversion rate

**If ROI <5x:**
→ PAUSE all campaigns
→ Audit tracking (likely technical issue)
→ Check for click fraud
→ Review landing page (CR problem likely)

---

## CRITICAL PRE-LAUNCH CHECKLIST

### Before pressing "Start Campaign":

**Account Setup:**
```
☐ Payment method added & verified
☐ Daily budget limits set (₽100K max to prevent overspend)
☐ Email notifications enabled (daily reports)
☐ Access granted to team members (if needed)
```

**Tracking Validation:**
```
☐ Yandex Metrica installed on all landing pages
☐ All 4 conversion goals tested & firing
☐ Call tracking numbers active
☐ Revenue tracking passing correct values
☐ Test order completed successfully (tracks in Metrica)
```

**Campaign Quality Check:**
```
☐ All 35 routes uploaded with unique ads
☐ No disapproved ads (check status)
☐ All URLs are working (no 404 errors)
☐ Mobile landing pages load in <3 seconds
☐ Phone numbers are clickable on mobile
```

**Safety Checks:**
```
☐ Negative keywords list uploaded (20+ terms)
☐ Geo-targeting verified (All Russia or route-specific)
☐ Schedule set correctly (24/7 recommended)
☐ Bid limits set (max CPC = ₽100 per click)
```

---

## EMERGENCY CONTACTS & RESOURCES

### If Things Go Wrong:

**Budget Overspend:**
→ Immediately pause Campaign A (mega-volume)
→ Set daily limit to ₽30K
→ Review auto-optimization settings (may have increased bids)

**Zero Conversions After 500 Clicks:**
→ Check Metrica goals (likely tracking issue)
→ Test order flow manually
→ Verify call tracking is recording calls

**CPC >₽100 on All Routes:**
→ Competition spiked (check search page manually)
→ Quality score dropped (improve ad relevance)
→ Wrong targeting settings (check geo/audience)

**CR <0.5% (Very Low):**
→ Landing page issue (slow load, broken forms)
→ Mobile optimization problem
→ Price mismatch (ad shows different price than LP)

---

## SUPPORT RESOURCES

**Files Generated:**
- `wave1_priority_routes.csv` - Import into Yandex Direct
- `DIRECT_CAMPAIGN_LAUNCH_PLAN.md` - Full strategic analysis
- `all_routes_scored.csv` - Complete route database with scores

**Yandex Direct Help:**
- Documentation: https://yandex.ru/support/direct/
- Support chat: Available in Direct interface
- Phone: Available for accounts spending >₽500K/month

---

**Good luck with the launch!**

*Estimated setup time: 60-90 minutes*  
*Expected Week 1 results: ₽4-20M revenue, 5-30x ROI*
