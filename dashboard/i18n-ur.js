/* ==========================================================================================
   URDU STRING DICTIONARY — loaded before app.js (plain global, no fetch/build step needed for a
   static dashboard). Kept in its own file so the corpus can grow into the hundreds of entries
   needed for full-page coverage (translateTree() in app.js walks every rendered text node)
   without bloating app.js itself. English key -> Urdu value; lookup is exact, trimmed-text match.

   Scope is deliberate: interface chrome, investor-desk surfaces, and disclaimers — exact-string
   match only. Dynamic agent prose (daily read, Room debates, news summaries, macro, sector
   debates) is translated separately, near generation time, by a dedicated fact-blind agent
   (state-translator) that writes `_ur` sibling fields into state/*.json. Rendered via tp()/tpArr()
   in app.js's LANGUAGE section, not this dictionary.
   ========================================================================================== */
window.UR_STRINGS = {
  // nav
  "Learn": "سیکھیں", "Today": "آج", "Board": "بورڈ", "Watchlist": "واچ لسٹ", "Portfolio": "پورٹ فولیو",
  "Your Chart": "آپ کا چارٹ", "Practice": "مشق", "Strategies": "حکمتِ عملی", "Value": "ویلیو",
  "Research": "تحقیق", "Scores": "اسکور", "News": "خبریں", "Macro": "معیشت", "Dividends": "منافع",
  "Analysis": "تجزیہ", "Markets": "منڈیاں",
  "Earnings": "نتائج", "Astro": "فلکیات", "Tools": "اوزار", "Settings": "ترتیبات", "Plans": "پلانز",
  "Sign in": "سائن اِن", "Sign out": "سائن آؤٹ", "Search a stock": "اسٹاک تلاش کریں",
  // learn / journey
  "Become an investor": "سرمایہ کار بنیں", "The investment journey": "سرمایہ کاری کا سفر",
  "your progress": "آپ کی پیش رفت", "steps complete": "مراحل مکمل", "Deep dives": "تفصیلی کورس",
  "today's lesson": "آج کا سبق", "your next lesson": "آپ کا اگلا سبق", "Learn it": "سیکھیں",
  "Continue": "جاری رکھیں", "Start the journey": "سفر شروع کریں", "lesson": "سبق",
  "watch out": "خبردار", "the point": "خلاصہ", "interactive": "انٹرایکٹو", "check yourself": "خود کو جانچیں",
  "back": "واپس", "Next": "اگلا", "Complete lesson": "سبق مکمل کریں",
  // practice + tools
  "Practice portfolio": "مشقی پورٹ فولیو", "virtual money · real prices": "فرضی رقم · اصل قیمتیں",
  "Holdings": "ملکیتیں", "Trade log": "ٹریڈ ریکارڈ", "Buy": "خریدیں", "Sell": "بیچیں",
  "Portfolio value": "پورٹ فولیو کی مالیت", "Return": "منافع", "Cash": "نقد",
  "Compound growth": "مرکب اضافہ", "Inflation": "مہنگائی", "Goal planner": "ہدف کا منصوبہ",
  "Mortgage": "گھر کا قرض", "Zakat on shares": "حصص پر زکوٰۃ", "Dividend reinvestment": "منافع کی دوبارہ سرمایہ کاری",
  "Calculate": "حساب کریں", "Years": "سال",
  // compliance — these must always be visible in the reader's language
  "Research · not advice": "تحقیق · مشورہ نہیں",
  "Education, not investment advice": "تعلیم، سرمایہ کاری کا مشورہ نہیں",
  "Henneth Desk is a research & analytics tool — not an investment adviser.":
    "ہینتھ ڈیسک تحقیق اور تجزیہ کا ٹول ہے — سرمایہ کاری کا مشیر نہیں۔",
  "This is a research & analytics tool, not an investment adviser.":
    "یہ تحقیق اور تجزیہ کا ٹول ہے، سرمایہ کاری کا مشیر نہیں۔",
  "Everything here is educational information, never personalized advice or a recommendation to buy or sell. No guaranteed returns; past performance does not predict future results. Investing in PSX carries risk, including the loss of your capital. You make your own decisions; execution is manual.":
    "یہاں ہر چیز تعلیمی معلومات ہے، کبھی ذاتی مشورہ یا خریدنے/بیچنے کی سفارش نہیں۔ کوئی ضمانت شدہ منافع نہیں؛ ماضی کی کارکردگی مستقبل کے نتائج کی ضمانت نہیں دیتی۔ PSX میں سرمایہ کاری خطرہ رکھتی ہے، جس میں آپ کی رقم کا نقصان بھی شامل ہے۔ فیصلے آپ خود کرتے ہیں؛ عملدرآمد دستی ہے۔",
  // topbar / chrome
  "Collapse menu": "مینو بند کریں", "Open menu": "مینو کھولیں", "Drag to resize": "سائز تبدیل کریں",
  "Search ticker": "ٹکر تلاش کریں", "Search a stock": "اسٹاک تلاش کریں",
  "Search a stock — symbol or name…": "اسٹاک تلاش کریں — علامت یا نام…",
  "Close search": "تلاش بند کریں",
  // sign-in gate
  "The terminal is members-only.": "ٹرمینل صرف اراکین کے لیے ہے۔",
  "Create a free account to open the desk. Free covers casting your chart, the daily read and the public track record — no card, no trial clock.":
    "ڈیسک کھولنے کے لیے مفت اکاؤنٹ بنائیں۔ مفت میں آپ کا چارٹ بنانا، روزانہ کا تجزیہ اور عوامی ٹریک ریکارڈ شامل ہے — نہ کارڈ، نہ ٹرائل کی گھڑی۔",
  "Create your account": "اپنا اکاؤنٹ بنائیں",
  "I already have one — log in": "میرے پاس پہلے سے ہے — لاگ ان کریں",
  "Not ready? You can still": "ابھی تیار نہیں؟ آپ پھر بھی",
  "cast your birth chart": "اپنا برتھ چارٹ بنا",
  "without an account — it follows you in when you sign up.": "بغیر اکاؤنٹ کے — سائن اپ کرنے پر یہ آپ کے ساتھ آ جائے گا۔",
  "Research & analytics, never investment advice. Read the": "تحقیق اور تجزیہ، کبھی سرمایہ کاری کا مشورہ نہیں۔ پڑھیں",
  "terms": "شرائط", "and": "اور", "risk disclosure": "خطرے کا اعلامیہ", "first.": "پہلے۔",

  // today page — chrome around the (untranslated) agent-written daily read
  "Risk:": "خطرہ:", "favoured": "پسندیدہ", "Favoured": "پسندیدہ",
  "avoid": "گریز", "Avoiding": "گریز کرتے ہوئے", "neutral": "غیر جانبدار",
  "cautious": "محتاط", "constructive": "مثبت", "defensive": "دفاعی",
  "risk-on": "رسک آن", "risk-off": "رسک آف",
  "sectors": "شعبے", "+1 more sectors": "+1 مزید شعبے",
  "The desk's tone": "ڈیسک کا انداز", "Next catalyst": "اگلا محرک",
  "your next lesson · 8 min": "آپ کا اگلا سبق · 8 منٹ", "Continue →": "جاری رکھیں →",
  "Sectors to watch": "نظر رکھنے کے شعبے", "Key risks": "اہم خطرات",
  "what would spoil the read": "کیا چیز اس تجزیے کو غلط ثابت کر سکتی ہے",
  "Catalysts:": "محرکات:", "Names on the desk's radar": "ڈیسک کی نظر میں موجود نام",
  "Ticker": "ٹکر", "The desk's angle": "ڈیسک کا زاویہ", "Key risk": "اہم خطرہ",
  "Research, not advice. The desk generates signals; it does not place orders. Losses are expected.":
    "تحقیق، مشورہ نہیں۔ ڈیسک سگنل بناتا ہے؛ آرڈر نہیں دیتا۔ نقصان متوقع ہے۔",

  // global macro strip — index labels + fixed methodology tooltips
  "Brent crude": "برینٹ خام تیل", "S&P 500": "ایس اینڈ پی 500", "Dow Jones": "ڈاؤ جونز",
  "Gold": "سونا", "Bitcoin": "بٹ کوائن", "Ethereum": "ایتھیریم",
  "USD/PKR": "ڈالر/روپیہ", "US Dollar Index": "امریکی ڈالر انڈیکس",
  "↑ = import bill up, PKR/inflation risk; E&P + refiners rise": "↑ = درآمدی بل میں اضافہ، روپے/مہنگائی کا خطرہ؛ ای اینڈ پی + ریفائنرز کو فائدہ",
  "global risk-on/off; frontier flows follow": "عالمی خطرہ آن/آف؛ فرنٹیئر سرمایہ اسی کے ساتھ چلتا ہے",
  "global risk appetite": "عالمی خطرہ مول لینے کا رجحان",
  "fear gauge; high = risk-off = PSX outflows": "خوف کا پیمانہ؛ زیادہ = رسک آف = PSX سے سرمایہ نکاسی",
  "safe-haven + PKR/inflation hedge sentiment": "محفوظ پناہ گاہ + روپے/مہنگائی ہیج کا رجحان",
  "global liquidity / retail risk barometer": "عالمی لیکویڈیٹی / ریٹیل رسک پیمانہ",
  "risk appetite": "خطرہ مول لینے کا رجحان",
  "biggest lever: weak PKR = imported inflation = hawkish SBP = equity headwind": "سب سے بڑا عنصر: کمزور روپیہ = درآمدی مہنگائی = سخت SBP پالیسی = حصص کے لیے مشکل",
  "strong USD pressures EM/frontier currencies incl PKR": "مضبوط ڈالر ابھرتی/فرنٹیئر کرنسیوں بشمول روپے پر دباؤ ڈالتا ہے",

  // account / plan chrome
  "Free plan": "مفت پلان", "Free": "مفت",
  "Switch to the Learner desk": "لرنر ڈیسک پر جائیں", "Replay the tour": "ٹور دوبارہ دیکھیں",

  // sign-in / create-account modal
  "Create account": "اکاؤنٹ بنائیں", "Email": "ای میل", "Password": "پاسورڈ",
  "Show": "دکھائیں", "Forgot password?": "پاسورڈ بھول گئے؟",
  "Research & analytics tool, not an investment adviser. By continuing you agree to the":
    "تحقیق اور تجزیہ کا ٹول، سرمایہ کاری کا مشیر نہیں۔ جاری رکھ کر آپ اتفاق کرتے ہیں",
  "Terms": "شرائط", "Privacy Policy": "پرائیویسی پالیسی", "Risk Disclosure": "خطرے کا اعلامیہ",
  "— nothing here is personalized advice.": "— یہاں کچھ بھی ذاتی مشورہ نہیں۔",
  "your password": "آپ کا پاسورڈ", "Show password": "پاسورڈ دکھائیں",
  "Signing in…": "سائن ان ہو رہا ہے…",

  // topbar pills (static prefixes only — value suffix stays untranslated, see note in app.js)
  "HEALTH —": "صحت —", "REGIME —": "نظام —", "RISK —": "خطرہ —",
  "PSX WEEKEND": "پی ایس ایکس ویک اینڈ", "HEALTH OK": "صحت درست", "REGIME: RISK-OFF": "نظام: رسک آف",
  "Broker plan": "بروکر پلان", "Broker": "بروکر",

  // sector card headers (Board / macro sector snapshots)
  "Banks": "بینکس", "Oil & Gas Exploration (E&P)": "تیل و گیس ایکسپلوریشن (E&P)",
  "OMCs & Refiners": "او ایم سیز اور ریفائنرز", "Cement": "سیمنٹ",
  "Fertiliser": "کھاد", "Textiles & Exporters": "ٹیکسٹائل اور برآمد کنندگان",
  "Oil & Gas": "تیل و گیس",

  // Board page — indices strip
  "PSX indices": "پی ایس ایکس اشاریے", "7 sessions kept": "7 سیشن محفوظ",
  "KSE All Share": "KSE آل شیئر", "KMI All Share": "KMI آل شیئر", "All Share": "آل شیئر",
  "No public source keeps PSX index history — the desk records it each cycle.":
    "کوئی عوامی ذریعہ PSX انڈیکس کی تاریخ محفوظ نہیں رکھتا — ڈیسک ہر سائیکل میں خود ریکارڈ کرتا ہے۔",
  "is the honest benchmark for names outside the KSE100.": "KSE100 سے باہر ناموں کے لیے حقیقی معیار ہے۔",
  "KSE100 — the headline 100": "KSE100 — سرکردہ 100",
  "KSE All Share — every listed company": "KSE آل شیئر — ہر لسٹڈ کمپنی",
  "KMI30 — Shariah, top 30": "KMI30 — شریعہ، ٹاپ 30",
  "KMI All Share — every Shariah-compliant name": "KMI آل شیئر — ہر شریعہ کے مطابق نام",
  "KSE30 — free-float top 30": "KSE30 — فری فلوٹ ٹاپ 30",
  "Banks — sector index": "بینکس — شعبہ اشاریہ", "Oil & Gas — sector index": "تیل و گیس — شعبہ اشاریہ",

  // Board page — proven strategies table
  "Volume leads price": "والیوم قیمت سے پہلے", "backtest-proven": "بیک ٹیسٹ ثابت شدہ",
  "high": "زیادہ", "medium": "درمیانہ", "low": "کم",
  "hit rate": "کامیابی کی شرح", "sample": "نمونہ", "net/trade": "فی ٹریڈ خالص", "hold": "قبضہ",
  "Work out your own levels →": "اپنی سطحیں خود طے کریں →",
  "Positions": "پوزیشنز", "Flat — no open positions.": "فلیٹ — کوئی کھلی پوزیشن نہیں۔",
  "Universe": "یونیورس", "day move · click any name": "دن کی حرکت · کسی بھی نام پر کلک کریں",
  "Predictability": "پیشین گوئی کی صلاحیت", "Score": "اسکور",
  "Proven strategies": "ثابت شدہ حکمتِ عملیاں",
  "cleared backtest + out-of-sample bars · click through": "بیک ٹیسٹ + آؤٹ آف سیمپل کلیئر · مزید کے لیے کلک کریں",
  "Template": "ٹیمپلیٹ", "Hit": "کامیابی", "Net": "خالص",
  "Triggering now, proven on this stock's own history. Backtest-proven, not auditor-verified. Research, not advice.":
    "ابھی متحرک، اس اسٹاک کی اپنی تاریخ پر ثابت شدہ۔ بیک ٹیسٹ سے ثابت، آڈیٹر سے تصدیق شدہ نہیں۔ تحقیق، مشورہ نہیں۔",

  // Board page — news / agent wire
  "News wire": "نیوز وائر", "full wire →": "مکمل وائر →", "Agent wire": "ایجنٹ وائر",
  "this cycle": "اس سائیکل میں", "No cycle run yet.": "ابھی تک کوئی سائیکل نہیں چلا۔",

  // Board page — today's scanner
  "Today's scanner": "آج کا اسکینر", "rebuilt every cycle": "ہر سائیکل میں دوبارہ تیار",
  "Below model fair value": "ماڈل کی مناسب قیمت سے کم", "Momentum": "مومینٹم",
  "Covered dividend yield": "کور شدہ ڈیویڈنڈ ییلڈ", "Quality earners": "معیاری کمائی والے",
  "High predictability": "اعلیٰ پیشین گوئی کی صلاحیت", "Washed-out (RSI)": "دھل چکا (RSI)",
  "Ranked from the desk's own data each cycle — screens, not recommendations. A list a stock qualifies for is a place to start reading, never a reason to buy. (Insider-dealing and Shariah-status screens await a verified data source — the desk won't fake either.)":
    "ڈیسک کے اپنے ڈیٹا سے ہر سائیکل میں ترتیب دیا جاتا ہے — اسکرینز ہیں، سفارشات نہیں۔ جس فہرست میں اسٹاک آئے وہ پڑھنا شروع کرنے کی جگہ ہے، خریدنے کی وجہ کبھی نہیں۔ (انسائیڈر ڈیلنگ اور شریعہ اسٹیٹس اسکرینز تصدیق شدہ ڈیٹا ذریعے کی منتظر ہیں — ڈیسک کوئی بھی نہیں بنائے گا۔)",

  // Watchlist page
  "Your watchlist": "آپ کی واچ لسٹ",
  "The stocks you follow, with the four things that matter at a glance. Star toggles on any stock page. Research, not advice.":
    "وہ اسٹاک جن پر آپ نظر رکھتے ہیں، ایک نظر میں چار اہم چیزوں کے ساتھ۔ ★ کسی بھی اسٹاک پیج پر ٹوگل ہوتا ہے۔ تحقیق، مشورہ نہیں۔",
  "No stocks yet. Open any stock and tap the ★ to add it — try": "ابھی تک کوئی اسٹاک نہیں۔ کوئی بھی اسٹاک کھولیں اور ★ دبا کر شامل کریں — آزمائیں",
  "the Board": "بورڈ", "or search (top right).": "یا تلاش کریں (اوپر دائیں)۔",

  // Strategies page (chrome only — the ~70 individual strategy template
  // names/descriptions are excluded, same translation-risk class as agent
  // prose: out of scope per this file's header note)
  "70 strategies": "70 حکمتِ عملیاں",
  "An open rule set, backtested on each stock's own ~19 years. It counts only where it cleared the bar — win rate ≥55%, positive expectancy after costs, profitable out-of-sample. Research, not advice.":
    "ایک کھلا رول سیٹ، ہر اسٹاک کے اپنے ~19 سالہ ڈیٹا پر بیک ٹیسٹڈ۔ صرف وہی شمار جو معیار پر پورا اترے — جیت کی شرح ≥55%، اخراجات کے بعد مثبت توقع، آؤٹ آف سیمپل منافع بخش۔ تحقیق، مشورہ نہیں۔",
  "transparent rule sets": "شفاف رول سیٹس",
  "Proven pairs": "ثابت شدہ جوڑے",
  "strategy × stock, after costs + OOS": "حکمتِ عملی × اسٹاک، اخراجات کے بعد + OOS",
  "Stocks with a proven edge": "ثابت شدہ برتری والے اسٹاک",
  "across the universe": "پورے یونیورس میں",
  "Library updated": "لائبریری اپ ڈیٹ",
  "full re-backtest": "مکمل ری بیک ٹیسٹ",
  "Your board": "آپ کا بورڈ",
  "waiting for a run": "رن کا انتظار",
  "Add a stock": "اسٹاک شامل کریں",
  "Add to board": "بورڈ میں شامل کریں",
  "All 70 of the desk's strategies, backtested across its ~19-year history — costs included, out-of-sample checked — with every stock–strategy pair that survived, ranked.":
    "ڈیسک کی تمام 70 حکمتِ عملیاں، اس کی ~19 سالہ تاریخ پر بیک ٹیسٹڈ — اخراجات شامل، آؤٹ آف سیمپل چیک شدہ — ہر وہ اسٹاک–حکمتِ عملی جوڑا جو قائم رہا، درجہ بندی کے ساتھ۔",
  "Read ›": "پڑھیں ›",
  "not run yet": "ابھی رن نہیں ہوا",
  "The library's results for": "لائبریری کے نتائج برائے",
  "aren't open yet — hit": "ابھی کھلے نہیں — دبائیں",
  "The library": "لائبریری",
  "What's in the library": "لائبریری میں کیا ہے",
  "every strategy the desk runs, and how each one works": "ڈیسک کی ہر حکمتِ عملی، اور ہر ایک کیسے کام کرتی ہے",
  "Request a strategy": "حکمتِ عملی کی درخواست کریں",
  "the desk tests it": "ڈیسک اسے ٹیسٹ کرتا ہے",
  "Trade by a rule that isn't in the library? Explain it below. The desk codes it, backtests it on ~19 years, and if it clears the bar it joins the library.":
    "کوئی رول لائبریری میں نہیں؟ نیچے بتائیں۔ ڈیسک اسے کوڈ کرے گا، ~19 سال پر بیک ٹیسٹ کرے گا، اور معیار پر پورا اترنے پر لائبریری میں شامل کرے گا۔",
  "Send to the desk": "ڈیسک کو بھیجیں",
  "e.g. FFC": "مثلاً FFC",
  "Name it (e.g. Monday gap fade)": "نام دیں (مثلاً Monday gap fade)",
  "Strategy name": "حکمتِ عملی کا نام",
  "Ticker (optional)": "ٹکر (اختیاری)",
  "Explain the rules in plain English: when it buys, when it exits, any filters (volume, trend, day of week…).":
    "اصول آسان الفاظ میں بتائیں: کب خریدتی ہے، کب نکلتی ہے، کوئی فلٹرز (والیوم، رجحان، ہفتے کا دن…)۔",
  // Strategy category filter labels
  "breakout": "بریک آؤٹ", "volatility": "اتار چڑھاؤ", "trend": "رجحان",
  "mean reversion": "مطلب کی طرف واپسی", "momentum": "مومینٹم",
  "volume": "والیوم", "oscillator": "آسیلیٹر",

  // Value page
  "Value screen — price vs model fair value": "ویلیو اسکرین — قیمت بمقابلہ ماڈل فیئر ویلیو",
  "Below fair value": "فیئر ویلیو سے کم", "Above fair value": "فیئر ویلیو سے زیادہ",
  "Near fair": "فیئر کے قریب", "within the model's band": "ماڈل کے بینڈ کے اندر",
  "Widest gap": "سب سے بڑا فرق",
  "Model estimates on public fundamentals for": "عوامی فنڈامینٹلز پر ماڈل کے تخمینے برائے",
  "research and education": "تحقیق اور تعلیم",
  "— not price targets, not advice, not a signal to buy or sell. A price below model fair value is not a recommendation, and a low share price never means a company is cheap. Past performance does not guarantee future results.":
    "— قیمت کے اہداف نہیں، مشورہ نہیں، خریدنے یا بیچنے کا اشارہ نہیں۔ فیئر ویلیو سے کم قیمت سفارش نہیں، اور کم شیئر قیمت کبھی سستے ہونے کا مطلب نہیں۔ ماضی کی کارکردگی مستقبل کے نتائج کی ضمانت نہیں دیتی۔",
  "How the model works": "ماڈل کیسے کام کرتا ہے", "four models, median wins": "چار ماڈلز، میڈین جیتتا ہے",
  "Each stock is valued four ways (peer P/E, earnings-power vs bond yield, Graham, dividend discount); the median is its":
    "ہر اسٹاک کو چار طریقوں سے پرکھا جاتا ہے (پیئر P/E، ارننگز پاور بمقابلہ بانڈ ییلڈ، گراہم، ڈیویڈنڈ ڈسکاؤنٹ)؛ میڈین اس کا",
  "model fair value": "ماڈل فیئر ویلیو",
  "Priced below model fair value": "ماڈل فیئر ویلیو سے کم قیمت",
  "Priced above model fair value": "ماڈل فیئر ویلیو سے زیادہ قیمت",
  "Price": "قیمت", "Fair value": "فیئر ویلیو", "Upside": "اپ سائیڈ", "Downside": "ڈاؤن سائیڈ",
  "Verdict": "فیصلہ", "below fair": "فیئر سے کم", "above fair": "فیئر سے زیادہ",
  "How the fair value was built — four independent models, price vs each:":
    "فیئر ویلیو کیسے بنی — چار آزاد ماڈلز، ہر ایک کے مقابلے میں قیمت:",
  "Peer P/E": "پیئر P/E", "Earnings power": "ارننگز پاور", "Graham (revised)": "گراہم (نظرثانی شدہ)",
  "Dividend discount": "ڈیویڈنڈ ڈسکاؤنٹ", "composite fair": "مجموعی فیئر", "inputs": "ان پٹس",
  "full page →": "مکمل صفحہ →",

  // Research page (chrome only — broker-call/filing-headline digest prose,
  // broker/source proper nouns, and embedded live counts excluded, same
  // translation-risk class as agent prose: out of scope per header note)
  "Switch language": "زبان تبدیل کریں",
  "Research library": "تحقیقی لائبریری",
  "Broker notes": "بروکر نوٹس",
  "Filings & briefings": "فائلنگز اور بریفنگز",
  "results · AGM · board": "نتائج · AGM · بورڈ",
  "Claims on the record": "درج دعوے",
  "each scored when it resolves": "ہر ایک طے ہونے پر اسکور ہوتا ہے",
  "Latest document": "تازہ ترین دستاویز",
  "the wire updates weekly": "وائر ہفتہ وار اپ ڈیٹ ہوتا ہے",
  "Broker research and company filings are": "بروکر تحقیق اور کمپنی فائلنگز",
  "evidence the desk cross-examines, never takes at face value": "وہ شواہد ہیں جن پر ڈیسک جرح کرتا ہے، کبھی من و عن قبول نہیں کرتا",
  ". Brokers miss things, carry sector bias, and are often wrong — every broker claim here is extracted, scored against what actually happens, and ranked on the":
    "۔ بروکرز چیزیں چھوڑ دیتے ہیں، شعبہ جاتی تعصب رکھتے ہیں، اور اکثر غلط ہوتے ہیں — یہاں ہر بروکر دعویٰ نکالا جاتا ہے، حقیقت سے ملا کر اسکور کیا جاتا ہے، اور اس پر درجہ بندی کی جاتی ہے",
  "broker leaderboard": "بروکر لیڈر بورڈ",
  ". Educational, not advice.": "۔ تعلیمی، مشورہ نہیں۔",
  "broker note": "بروکر نوٹ",
  "source ↗": "ماخذ ↗",
  "Claims (scored later):": "دعوے (بعد میں اسکور ہوں گے):",
  "Company filings & briefings": "کمپنی فائلنگز اور بریفنگز",
  "results": "نتائج",
  "headline only": "صرف ہیڈ لائن",
  "filing": "فائلنگ",
  "board meeting": "بورڈ میٹنگ",
  "corporate briefing": "کارپوریٹ بریفنگ",
  "AGM": "اے جی ایم",
  "morning note": "صبح کا نوٹ",

  // News page (chrome only — headline/digest prose from state/news.json excluded,
  // same translation-risk class as agent prose: out of scope per header note)
  "all": "تمام",
  "impact ≥3": "اثر ≥3",
  "impact ≥4": "اثر ≥4",
  "impact ≥5": "اثر ≥5",
  "filter ticker/text": "ٹکر/متن سے فلٹر کریں",

  // Macro page (chrome + fixed driver/sector taxonomy only — macro-driver prose sourced from
  // state/macro.json, correlation stats, timestamps, and directional-arrow instrument rows
  // excluded, same translation-risk class as agent prose: out of scope per header note)
  "Instrument": "انسٹرومنٹ", "1d": "1 دن", "1mo": "1 ماہ",
  "PSX read-through": "PSX پر اثر", "What moves PSX": "PSX کو کیا حرکت دیتا ہے",
  "Macro regime": "میکرو نظام", "Geo risk": "جغرافیائی خطرہ", "moderate": "درمیانہ",
  "Global markets refresh every cycle (Yahoo Finance); Pakistan numbers are verified from primary sources. Hover a read-through for why it matters.":
    "عالمی مارکیٹس ہر سائیکل میں ریفریش ہوتی ہیں (Yahoo Finance)؛ پاکستان کے اعداد و شمار بنیادی ذرائع سے تصدیق شدہ ہیں۔ اہمیت جاننے کے لیے کسی بھی ریڈ-تھرو پر ہوور کریں۔",
  "What actually moves each sector": "ہر شعبے کو اصل میں کیا حرکت دیتا ہے",
  "Sector": "شعبہ", "Demonstrated drivers": "ثابت شدہ محرکات", "Global tape explains": "عالمی ٹیپ وضاحت کرتی ہے",

  // Macro page — PSX official sector-index names (distinct strings from the Board page's
  // shorthand sector labels above — do not merge, PSX index names are exact-match keys)
  "Oil & Gas Exploration Companies": "آئل اینڈ گیس ایکسپلوریشن کمپنیز",
  "Oil & Gas Marketing Companies": "آئل اینڈ گیس مارکیٹنگ کمپنیز",
  "Commercial Banks": "کمرشل بینکس", "Textile Composite": "ٹیکسٹائل کمپوزٹ",
  "Food & Personal Care Products": "فوڈ اینڈ پرسنل کیئر پروڈکٹس",
  "Power Generation & Distribution": "پاور جنریشن اینڈ ڈسٹری بیوشن",
  "Technology & Communication": "ٹیکنالوجی اینڈ کمیونیکیشن",
  "Refinery": "ریفائنری", "Pharmaceuticals": "فارماسیوٹیکلز",
  "Automobile Assembler": "آٹوموبائل اسمبلر", "Fertilizer": "کھاد", "Miscellaneous": "متفرق",
  "THE MARKET (KSE100 proxy)": "مارکیٹ (KSE100 پراکسی)",

  // Macro page — predictability-vs-astrology methodology blurb (static text-node fragments)
  "nothing beat chance": "کچھ بھی اتفاق کو نہ ہرا سکا",
  "Nineteen years of daily returns against the global tape — oil, gold, USD/PKR, the S&P, EM flows, the US 10y — each lagged a day, since those markets close after Karachi. The same test found nothing in":
    "انیس سال کے روزانہ ریٹرنز کا عالمی ٹیپ کے خلاف موازنہ — تیل، سونا، ڈالر/روپیہ، S&P، EM فلوز، امریکی 10 سالہ — ہر ایک ایک دن تاخیر سے، کیونکہ وہ مارکیٹس کراچی کے بعد بند ہوتی ہیں۔ وہی ٹیسٹ میں کچھ نہیں ملا",
  "astrology": "علمِ نجوم", ". Here it finds": "۔ یہاں یہ ملتا ہے",
  ". That contrast is the point.": "۔ یہی تضاد اصل بات ہے۔",
  "Read the last column first.": "پہلے آخری کالم پڑھیں۔",
  "Even at its strongest, the world tape explains a few percent of a day's move — PSX is made at home. A driver says what":
    "اپنی مضبوط ترین حالت میں بھی، عالمی ٹیپ دن کی حرکت کا چند فیصد ہی بتاتی ہے — PSX گھر میں بنتا ہے۔ کوئی محرک یہ بتاتا ہے کہ کیا",
  "has tended": "رجحان رہا ہے",
  "to move a sector, never what will.": "شعبے کو حرکت دینے کا، کبھی یہ نہیں کہ کیا ہوگا۔",

  // Macro page — geopolitical/risk radar factor table (fixed factor labels + one-line
  // methodology explanations; live score/level values excluded)
  "Geopolitical & risk radar": "جغرافیائی و خطرے کا ریڈار",
  "· desk composite from free signals (VIX/oil/gold/DXY/PKR/news)":
    "· ڈیسک کا مرکب مفت سگنلز سے (VIX/تیل/سونا/DXY/روپیہ/خبریں)",
  "Conflict / escalation": "تنازع / کشیدگی میں اضافہ",
  "geopolitical shocks (oil, conflict, policy) are what hit PSX hardest and fastest":
    "جغرافیائی سیاسی جھٹکے (تیل، تنازع، پالیسی) PSX کو سب سے سخت اور تیز ترین ضرب لگاتے ہیں",
  "Energy shock (Brent)": "توانائی کا جھٹکا (برینٹ)",
  "rising crude widens the import bill, pressures PKR & inflation; helps E&P/refiners only":
    "بڑھتا خام تیل درآمدی بل بڑھاتا ہے، روپے اور مہنگائی پر دباؤ ڈالتا ہے؛ صرف E&P/ریفائنرز کو فائدہ",
  "Safe-haven (Gold)": "محفوظ پناہ گاہ (سونا)",
  "gold bid = flight to safety; risk sentiment defensive": "سونے کی خریداری = تحفظ کی جانب رجحان؛ دفاعی خطرہ رجحان",
  "USD strength (DXY)": "ڈالر کی مضبوطی (DXY)",
  "a strong dollar drains capital from frontier markets and pressures the rupee":
    "مضبوط ڈالر فرنٹیئر مارکیٹس سے سرمایہ نکالتا ہے اور روپے پر دباؤ ڈالتا ہے",
  "Rupee stress (USD/PKR)": "روپے پر دباؤ (ڈالر/روپیہ)",
  "a weakening rupee imports inflation and keeps SBP hawkish — an equity headwind":
    "کمزور ہوتا روپیہ درآمدی مہنگائی لاتا ہے اور SBP کو سخت پالیسی پر رکھتا ہے — حصص کے لیے مشکل",
  "Global fear (VIX)": "عالمی خوف (VIX)",
  "high VIX = global risk-off = foreign outflows from PSX": "زیادہ VIX = عالمی رسک آف = PSX سے غیر ملکی سرمائے کا انخلاء",
  "Sector read-through:": "شعبے پر اثر:",
  "OMCs & cement (fuel/energy cost) · E&P benefits (OGDC/PPL/MARI)":
    "او ایم سیز اور سیمنٹ (ایندھن/توانائی لاگت) · E&P کو فائدہ (OGDC/PPL/MARI)",
  "For true Country Instability Index (Pakistan), add a worldmonitor.app API key as WORLDMONITOR_KEY.":
    "حقیقی کنٹری انسٹیبلیٹی انڈیکس (پاکستان) کے لیے، worldmonitor.app کی API کلید بطور WORLDMONITOR_KEY شامل کریں۔",

  // Macro page — Pakistan macro panel (fixed field labels; live values/prose excluded)
  "Pakistan macro": "پاکستان میکرو", "regime": "نظام",
  "SBP policy rate": "SBP پالیسی ریٹ", "CPI YoY": "CPI سالانہ", "FX reserves": "زرمبادلہ ذخائر",
  "6m T-bill": "6 ماہ ٹی بل", "10y PIB": "10 سالہ PIB", "Remittances": "ترسیلاتِ زر",
  "Debt/borrowing:": "قرض/ادھار:", "Drivers:": "محرکات:", "Next:": "اگلا:",
  "Favored:": "پسندیدہ:", "Avoid:": "گریز:",

  // Macro page — global-tape driver table (fixed row labels; live values/correlation stats excluded)
  "Currency — the biggest macro lever for PSX": "کرنسی — PSX کے لیے سب سے بڑا میکرو عنصر",
  "Energy — oil drives Pakistan's import bill, PKR & inflation":
    "توانائی — تیل پاکستان کے درآمدی بل، روپے اور مہنگائی کو چلاتا ہے",
  "WTI crude": "WTI خام تیل", "global oil proxy": "عالمی تیل پراکسی",
  "Global risk appetite — frontier flows follow": "عالمی رسک بھوک — فرنٹیئر فلوز اسی کی پیروی کرتے ہیں",
  "Crypto — global liquidity / retail risk barometer": "کرپٹو — عالمی لیکویڈیٹی / ریٹیل رسک بیرومیٹر",
  "Safe haven": "محفوظ پناہ گاہ",

  // Dividends page (chrome + fixed table headers/captions only — brand/PII, live day-counts,
  // per-stock dividend % strings, closure/announce dates, and templated regime/radar sentences
  // with embedded live scores excluded, same translation-risk class as data-sourced content)
  "How to collect a dividend": "ڈیویڈنڈ کیسے حاصل کریں",
  "Buy before → hold through → sell after": "پہلے خریدیں → درمیان میں رکھیں → بعد میں بیچیں",
  "① Buy by": "① خریدیں بذریعہ", "the last session before the ex-date": "ایکس ڈیٹ سے پہلے کا آخری سیشن",
  "② Sell on / after": "② بیچیں پر / بعد میں",
  "the ex-date — you keep the full payout": "ایکس ڈیٹ — آپ کو مکمل ادائیگی ملتی ہے",
  "Upcoming dividends & book closures": "آنے والے ڈیویڈنڈز اور بک کلوژرز",
  "Payout": "ادائیگی", "Rs/sh": "روپے/حصص", "Yield": "ییلڈ", "Buy by": "خریدیں بذریعہ",
  "Ex / sell-after": "ایکس / بیچیں بعد", "ex dividend": "ایکس ڈیویڈنڈ",
  "Past payouts": "گزشتہ ادائیگیاں",
  "last 40 closures · cash dividends (D) as % of Rs 10 face value":
    "آخری 40 کلوژرز · نقد ڈیویڈنڈ (D) بطور فیصد Rs 10 فیس ویلیو کے",
  "Yield@now": "ییلڈ@اب", "Announced": "اعلان شدہ", "Closure start": "کلوژر آغاز",

  // Calendar/Earnings page (chrome + fixed table headers/legend only — brand/PII, live risk
  // score, timestamps, month labels, dynamic day-counts, and templated regime/radar sentences
  // excluded, same translation-risk class as data-sourced content)
  "Earnings calendar": "آمدنی کیلنڈر",
  "verified": "تصدیق شدہ", "estimate": "تخمینہ",
  "= confirmed against a board-meeting notice ·": "= بورڈ میٹنگ نوٹس کے خلاف تصدیق شدہ ·",
  "= scraped, pending. The desk won't hold a swing through an unconfirmed results date — earnings gaps blow through stops.":
    "= اسکریپ شدہ، زیرِ التوا۔ ڈیسک غیر تصدیق شدہ نتائج کی تاریخ کے دوران پوزیشن نہیں رکھتا — آمدنی کے گیپ اسٹاپس کو توڑ دیتے ہیں۔",
  "scraped estimate — fundamentals-agent verifies": "اسکریپ شدہ تخمینہ — فنڈامینٹلز ایجنٹ تصدیق کرتا ہے",
  "Date": "تاریخ", "In": "میں", "Event": "ایونٹ", "Status": "حیثیت",
};
