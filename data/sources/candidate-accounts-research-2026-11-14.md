# 2026 直轄市長（補齊）與縣市長候選人官方線上來源查證報告

查核日：2026-11-14。範圍：六都市長候選人中 2026-07-05 未收錄的 10 位，以及 22 縣市中 16 縣市全部 58 位縣（市）長候選人（名單取自中選會登記名冊與各選委會號次公告，見 data/elections/2026/）。
方法與標準同 [2026-07-05 報告](candidate-accounts-research-2026-07-05.md)：只收本人／競選團隊官方帳號；first_party＝官網或已確認帳號直接連結；cross_ref＝至少兩個獨立來源互證；證據薄弱者不入 CSV，列在各節「待查」。
結果：46 位候選人、152 個帳號（first_party 83、cross_ref 69）。

以下候選人查無可確認的公開帳號，未列入 candidates.csv（頁面仍可在 /elections/ 查到號次）：
張火木（kinmen）、蘇輝湟（new-taipei）、許智富（penghu）、陳振中（penghu）、陳盡川（penghu）、吳炳輝（yunlin）、林佳瑜（yunlin）、魏造文（keelung）、王肇民（kaohsiung）、陳宏毅（yilan）、劉燦輝（yilan）、楊鉯婷（yilan）、郭璽（taipei）、林志成（taipei）、唐新民（taipei）、羅佩秦（hualien）、曹爾元（lienchiang）、王義成（chiayi-city）、陳愷璜（chiayi-city）、朱定瑀（hsinchu-county）、蕭燐洪（tainan）、洪麗華（taichung）


<!-- batch 1 -->

查核日：2026-11-14。方法如下：
- 官網、YouTube 頻道 about 頁與 Portaly 連結頁，以 curl fetch 讀出外部連結。
- FB、IG、Threads 以連結預覽 UA 讀取公開 og 標題與自介，不登入。
- FB 頁面 URL 以 Yahoo 台灣搜尋 `site:facebook.com` 取得，並與新聞圖說／報導交叉核對。
- 請求間隔 3–6 秒。DuckDuckGo 中途限流，Bing 結果無用，之後改用 Yahoo 與內建搜尋。

CSV 只收 first_party／cross_ref；證據不足者列於各節「待查」，未寫入 CSV。

## 金門縣

### 1 張國威（無黨籍）
- 收：
  - FB 粉專 kmgogogo「張國威-微風吹起」（campaign，cross_ref）。頁名即競選口號，分類為政治人物，有「金門縣長1號候選人張國威競選總部」成立貼文。
  - 個人帳號 zhang.guo.wei.988133（personal，cross_ref）。任職「二毛帶您遊金門」，與新聞所稱二毛租車負責人相符，並有「微風革命」選舉貼文。
- 排除：IG @kuowei_chang（自介「專發廢文」，與金門無關聯證據）、Threads @kuowei_chang（0 則串文）。
- 查無：官網、YouTube、LINE、TikTok、X、Podcast。

### 2 李文良（無黨籍，前副縣長）
- 收：FB 粉專「李文良-良政啟航 金門優先」（ID 61588799889987，campaign，cross_ref）。中央社／聯合報明載白皮書放在此粉專。搜尋結果曾以「良政啟航 金門優先-李文良」名稱出現，判定同一 ID 改名，未另立列。
- 查無：官網、IG、Threads、YouTube、LINE、TikTok、X。

### 3 洪和成（無黨籍）
- 收：FB honghercheng（personal，cross_ref）。自介「傾聽金門，做該做的事／金門縣長候選人」，與自由時報報導主張相同，並有第一人稱登記貼文。
- **待查**：FB HerCheng.Hong「洪和成粉專」（6,724 粉絲，自介「金門縣長候選人-洪和成」）。
  - 無互動數，可能是 2018／2020 參選時的舊粉專或支持者所開，無一手指認，未收。
- 查無：官網、IG、Threads、YouTube、LINE。

### 4 張火木（無黨籍，實踐大學退休副教授）
- **待查**：同名 FB 帳號至少四個，均無一手或新聞指認，全部未收。
  - zhanghuomu6：易經／道學講座「蘆荻居士」，5,207 粉絲。
  - zhang.huo.mu.559168：數位創作者，2026-09-07 有影片。
  - zhang.huo.mu.519871、zhang.huo.mu.2025：無內容。
  - 金門社團中有「張火木教授回應《金門日報》社論」第一人稱長文，但發文帳號不明。
- 查無：官網、IG、Threads、YouTube、LINE。

### 5 陳玉珍（國民黨）
- YouTube 頻道（UCrZ93hpb0idyyZZoxRUfjPQ，@陳玉珍珍愛金門）簡介直連 FB KinmenMyLove 與 IG lovekinmen → 兩列 first_party。
- LINE @k1689（first_party）：FB 粉專簡介與 IG 自介都寫 @k1689，page.line.me/k1689 標題「陳玉珍 | LINE 官方帳號」。
  - YouTube 簡介與個人 FB 仍寫舊 ID @lovekinmen，page.line.me/lovekinmen 回 404，判定已停用，未收。
- 個人 FB ntupkuc 自介逐一列出整個帳號矩陣 → cross_ref。
- Threads @lovekinmen：同 handle、同顯示名 → cross_ref。
- YouTube 頻道本身只被 IG／個人 FB 以文字點名，沒有超連結 → cross_ref。
- 排除：
  - 「珍礙金門」（IG goodbyebadtank）是罷免陣營帳號。
  - YouTube 連結區的 noractopork.tw 是 2021 公投議題站，不是本人帳號。
- 查無：競選專用官網（11/3 白皮書稱「上臉書點連結」，未見獨立站）、TikTok、X、Podcast。

### 6 梁文韜（無黨籍，成大政治系教授）
- 官網 kinmen-toto.oen.tw（first_party）。頁尾社群列與內文直連 IG／Threads @mantoleung、LINE lin.ee/wzaKzfQ（→ @635eccog）、兩個 FB share 連結；以上皆 first_party。
  - 兩個 FB share 連結實測都轉址到個人帳號 liang.wen.tao.879135。
- 競選粉專「梁文韜・金門走新路」（ID 61594179176285）：聯合報點名，官網未直連 → cross_ref。
- 官網內數十個 FB reel 連結與 YouTube 單支影片不另立列。
- 查無：YouTube 頻道、TikTok、X、Podcast。

### 7 黃世團（無黨籍，版畫家）
- 收：FB huang.shi.tuan（personal，cross_ref）。有第一人稱登記貼文，以及西園美術館競總成立邀請，與聯合報報導一致。
- **待查**：YouTube「金門縣長候選人黃世團」（UCoC3Z1m5_qyJeFTVfsg-9aw）。
  - handle 為 @金門縣長候選人黃世團，10 訂閱，無簡介。
  - 本人 FB 曾貼文推廣「黃世團博士影音頻道」，但名稱不同、無超連結，無法確認是同一頻道。
- 查無：官網、IG、Threads、LINE。

## 台東縣

### 1 李吳穎智（無黨籍）
- 收：FB「李吳穎智 競選總部 服務中心」（ID 61582118087400，campaign，cross_ref）。中天新聞圖說直接引用此頁名。
- 排除：FB winwinwinst「李吳穎智」（太陽能發電業務頁，17 粉絲，與競選無關，可能是本人商業頁，不屬從政帳號）。另有社團「李吳穎智 服務處」（groups/1638354723847607），內容多為轉貼他人；社團不收。
- 查無：官網、IG、Threads、YouTube、LINE。

### 2 陳瑩（民進黨）
- FB 11YIG：維基外部連結與 Wikidata 皆列，有本人提名貼文 → cross_ref。
- IG／Threads asenayig：Wikidata 列出，自介「台東縣長參選人」 → cross_ref。
- 本次沒有找到能讓上述帳號升為 first_party 的直連來源：無競選官網，YouTube 頻道也未找到。
- 排除：「東森新聞主播 陳瑩」FB 粉專（同名主播）。
- 查無：官網、YouTube、LINE OA、TikTok、X、Podcast。

### 3 王志偉（無黨籍，台東釋迦合作社理事主席）
- 收：FB「台東縣長參選人王志偉」（ID 61594918615193，campaign，cross_ref）。
  - 證據只有頁名，加上 yam 政見對照圖說「王志偉臉書」與中央社「以社群談政見」。
  - **偏弱，請人工複查**：讀不到粉專貼文內容。
- 排除：politicianccc（彰化縣議員陳重嘉，轉貼王志偉直播）；王志輝（副縣長，同音不同人）。
- 查無：官網、IG、Threads、YouTube、LINE。

### 4 吳秀華（國民黨，縣議長）
- 收：FB 100090624231494（personal，cross_ref）。中天圖說「圖取自吳秀華臉書」，自介內容相符。
- **待查**：
  - YouTube「Show what ?? 吳秀華的台東日常」（@Show.Taitung，UCj4ycB_wgdeBskSZN1Qdfnw）。簡介自述「吳秀華｜台東縣議長・縣長參選人」，但只有 33 訂閱、單一自述證據，未收。
  - 同名 IG／Threads @show.taitung 被擋讀，未能確認。
- 查無：官網、LINE OA、TikTok、X。

## 新竹市

### 1 高虹安（無黨籍，現任）
- YouTube 頻道（@高虹安）簡介直連 FB DrAnnKao、IG drannkao2021 → first_party。
- YouTube 本身：Wikidata 與頻道自述 → cross_ref。
- Threads drannkao2021：同 handle，自介逐字相同 → cross_ref。
- 全部沿用長期帳號，未見競選專用帳號，role 皆 personal。
- 排除：新竹市政府機關帳號。
- 查無：競選官網、LINE OA（未見本人導向）、TikTok、X、Podcast。

### 2 何志勇（無黨籍，前國民黨發言人）
- 官網 chihyungho.github.io：有政治獻金專戶，YouTube 也回連 → first_party。
- 官網聯絡區直連 FB／YouTube／IG／Threads／TikTok → 五列 first_party。
- YouTube 連結區另直連 X @ChihYungHo1 → first_party（X 擋爬，未確認活躍）。
- Portaly（portaly.cc/chihyungho）與 linktr.ee/chihyungho 是連結彙整頁，不另立列。
- 查無：LINE OA、Podcast。

### 3 莊競程（民進黨）
- FB Power3C、IG／Threads legislator2020：名稱一致，自介含「新竹市長候選人」，中央社／中時報導引用 → 皆 cross_ref。
- **待查**：
  - YouTube @莊競程（UCHAzWIQtMZeToDLFzyUCSVQ，212 訂閱，無簡介，無指認）。
  - LINE OA：只有支持者自製的 chengfeng-hsinchu.pages.dev 有列，不是一手來源。
- 排除：chengfeng-hsinchu.pages.dev（標明「支持者整理」的懶人包）、blindvote.app 等第三方站。
- 查無：競選官網、TikTok、X、Podcast。

## 嘉義縣

### 1 吳品叡（無黨籍，藍白支持）
- FB「Team叡 • 吳品叡」（100063479239691）：有宣布參選貼文 → cross_ref。
- IG wu_pin_jui：同品牌顯示名 → cross_ref。
- **待查**：
  - 個人 FB wu.pin.rui.2025（10,912 粉絲，自介談朴子大小事，連結被截斷）。
  - YouTube @吳品叡-s3t（UC_OchTLStq24tChorSykfiw，自動產生 handle，無簡介）。
  - Threads @wu_pin_jui（被登入牆擋住）。
- 排除：rex.wu.7140 等同名個人帳號；朴子市公所機關頁。
- 查無：官網、LINE OA、TikTok、X。

### 2 蔡易餘（民進黨）
- 帳號互相連結：
  - YouTube 簡介連到 FB 與 LINE。
  - Threads 自介連到 Portaly，Portaly 再連到 FB／IG／Threads／YouTube／LINE。
  - 五列皆 first_party。Portaly 本身不另立列。
- **待查**：YouTube 連結按鈕另有 LINE ID @chiayionefish（line.me/R/ti/p/%40chiayionefish），與簡介文字的 @xyx4958e 不同。兩者都沒有公開 page.line.me 檔案頁，無法判斷哪個是現行帳號，暫只收簡介與 Portaly 都指向的 @xyx4958e。
- 排除：Portaly 模板預設的 LINE @256ipjdm（名片 QR 預留值）、IG 連結只指向首頁那一筆。
- 查無：競選官網、TikTok、X、Podcast。

## 新北市

### 2 蘇輝湟（無黨籍）
- **查無**任何本人帳號。
  - 搜尋只見新聞、電視台，以及 YouTuber「MRG蓋瑞」(wsmymrggary) 的訪談影片。
  - facebook.com/public/蘇輝煌 是同音異字搜尋頁，不相干。
  - 新聞稱其競總設於自宅，無社群經營報導。
- 不寫入 CSV。

## 需人工複查清單
1. 王志偉 FB 粉專 61594918615193：證據只有頁名與一則圖說，讀不到貼文內容。
2. 張國威個人帳號 zhang.guo.wei.988133：是否由本人經營並用於選舉。
3. 洪和成：兩個粉專（honghercheng 與 HerCheng.Hong）何者是現行官方帳號。
4. 張火木：四個同名 FB 帳號，均無法認定。
5. 蔡易餘 LINE：@xyx4958e 與 @chiayionefish 何者是現行帳號。
6. 梁文韜 LINE @635eccog：無公開檔案頁，帳號名稱未確認。
7. 吳秀華 @Show.Taitung（YouTube／IG）：待確認；黃世團 YouTube、莊競程 YouTube、吳品叡 YouTube／個人 FB：都是單一自述，未收。
8. 吳秀華 FB 的「內政部資料連結」只見於搜尋摘要，未實際開頁核對。

<!-- batch 2 -->

查核日：2026-11-14。方法：競選官網與 YouTube 頻道 about 頁 fetch，Threads 個人頁 fetch（未登入時仍可讀到顯示名、自介、bio 連結與部分貼文），LINE 官方帳號頁 fetch，短網址以 curl 解析轉址；FB／IG／TikTok 擋爬，改用搜尋快照、維基百科／Wikidata 外部連結、政府網站與新聞引用互證。本批僅輸出 2026-11-14 有佐證的帳號；只有單一薄弱證據者一律列在「待查」。

## 澎湖

### 許智富（1 號，無黨籍）
- 多則新聞（聯合報、鏡週刊、壹蘋 2026-03-02；ETtoday、壹電視 2026-09-23）說他在「臉書」宣布參選、交保後也在臉書報平安，但沒有任何報導或搜尋結果給出粉專網址。
- 查無：FB 網址、IG、Threads、YouTube、LINE、官網。
- 待查：他的 FB 粉專或個人頁網址。可先找澎湖日報 2026-03 報導的圖片來源，或登入 FB 搜尋「許智富」。

### 周倪安（2 號，台聯）
- 收錄：FB 個人頁 nian.chou（cross_ref）。維基百科外部連結列出此頁；搜尋快照顯示簡介為「黨主席 at 台聯黨」「Lives in Makung」；上報與中天引用她 2026-06-03 在臉書宣布參選的貼文配圖。
- 排除：台聯黨粉專 tsu.org（政黨帳號）。
- 不收：Threads @nian.chou。帳號存在（顯示名 NIAN，95 追蹤，連到 IG nian.chou），但「No threads yet」，也沒有自介。
- 待查：FB「Formosa倪安祝您安」（facebook.com/tsu.chounian/），名稱像本人的另一個粉專，但沒有一手連結指認；IG nian.chou 只能從 Threads 的連結推知存在，無內容可佐證。

### 葉竹林（3 號，無黨籍）
- 收錄：FB 粉專 YEHCHULINinPENGHU（first_party，Threads 自介直連，頁面類別「澎湖縣長候選人」，維基同列）；Threads @yehchulin2020（cross_ref，自介經歷與維基一致，最新貼文 2026-11-03 為競選音樂會）；IG yehchulin2020（first_party，Threads 個人頁連結）。
- 待查：FB 舊頁 facebook.com/yehchulin/。搜尋顯示名為「葉竹林(@yehchulin)」，可能是 2022 年前或馬公市長時期的帳號，沒有一手指認，未收。YouTube UCPeAcTQCzl2pYMmaDnmd7Mw 雖列在維基外部連結，但 handle 是系統自動產生的 @葉竹林-f8z，只有 6 位訂閱者，屬單一薄弱證據，未收。
- 查無：LINE OA、官網、X、TikTok。

### 吳淑瑾（4 號，民進黨）
- 收錄：Threads @wu_shuchin（cross_ref，已驗證，自介「我是吳淑瑾」，競總活動貼文）；IG wu_shuchin（first_party，Threads 自介直連）；FB 61591067645616（cross_ref，維基外部連結，fetch 頁名「吳淑瑾」，2026 新建 ID，Threads 貼文稱「追蹤吳淑瑾 FB 或 IG」）。三者 account_role 皆標 campaign，理由是她 2026-06 才代夫出征，這些帳號都在參選後新開。
- 排除：陳光復臉書粉專與 IG chen_kuang_fu。她參選初期借用丈夫粉專發文，但那是現任縣長本人的帳號，不是她的。Facebook「Shu-chin Wu」（shuchin.wu.39）、「Shujin Wu」（shujin.wu.90）為同名或不相關的人。
- 查無：LINE OA、官網、YouTube、X、TikTok。

### 陳振中（5 號，國民黨）
- 本批未收任何帳號。
- 待查：FB 個人頁 chen.zhen.zhong.67701。目前只有維基百科／Wikidata 列出（兩者同源），內政部鄉鎮市長資料頁的部落格與連結網頁欄都填「無」，搜尋引擎也找不到該頁快照。屬單一來源，未收。
- 排除：facebook.com/XANGO888（「陳振中」，是兩岸物流代購商家，同名無關）。
- 查無：IG、Threads、YouTube、LINE、競選官網。

### 陳盡川（6 號，無黨籍，海洋保育志工）
- 查無任何本人帳號。搜尋只找到 2020 年快艇遭縱火、2025 年潛水失聯等新聞影片，以及他人的海洋保育頁面。
- 待查：可能有個人或志工隊 FB（澎湖海洋保護志工團隊），但沒找到可指認的網址。

## 雲林

### 吳炳輝（1 號，無黨籍，律師）
- 本批未收任何帳號。
- 待查：FB「2022台南市長候選人 吳炳輝律師」（facebook.com/p/…-100085942178534/）與「吳炳輝立委候選人」（facebook.com/p/…-100064082461516/）。自由時報證實參選雲林縣長的律師吳炳輝就是 2022 年參選台南市長的同一人，所以本人身分可以成立。但兩頁都是過去選舉的頁面，無法確認 2026 年是否仍在使用，也沒找到雲林縣長專頁，暫不收。
- 查無：2026 競選專頁、IG、Threads、YouTube、LINE。

### 張嘉郡（2 號，國民黨）
- 收錄：FB Sweet.Yunlin、IG dr.chiachunchang、TikTok dr.chiachunchang，皆為 cross_ref。三者都列在維基百科與 Wikidata；搜尋快照的帳號名與雲林議題內容互相一致。
- 不收：Threads @dr.chiachunchang。帳號存在（約 1,249 追蹤），但「No threads yet」，也沒有自介。
- 查無：競選官網、YouTube 自營頻道（搜尋只有新聞台影片）、LINE OA、X。
- 注意：縣府粉專與現任縣長張麗善的帳號屬機關或他人，不收。

### 劉建國（3 號，民進黨）
- 收錄：FB 粉專 liucnko.fans（cross_ref，搜尋快照簡介「雲林縣長候選人」，簡介列出 LINE／IG／Threads）；Threads @liu.cn.ko（cross_ref，已驗證）；IG liu.cn.ko（first_party，已驗證 Threads 直連）；LINE @liucnko（cross_ref，FB 簡介短鏈解析而得，LINE 頁回連粉專）。
- 待查：facebook.com/liucnko/（搜尋顯示名「劉建國」，可能是個人帳號或舊頁，沒有一手指認）；YouTube 自營頻道。2026-09-20 競總成立直播的頻道歸屬不明，未收。
- 查無：官網、X、TikTok。

### 林佳瑜（4 號，無黨籍，牙醫）
- 查無任何本人帳號。新聞（中時、自由、民視）形容他「佛系」「空氣系」，沒有提及社群。搜尋到的「林佳瑜」帳號都是同名的人，無法對應。
- 待查：正雲牙醫診所是否有粉專，以及粉專是否由本人以候選人身分經營。

## 基隆

### 童子瑋（1 號，民進黨）
- 競選官網 t-ziwei.com 2026-11-14 fetch 成功，頁首頁尾直連 FB wayne201817、IG／Threads／YouTube tungtung_keelung、LINE（lin.ee/5Uyf3qoo 解析為 @113cvbls，basic ID @tongziwei）。六列全部 first_party。
- YouTube 頻道簡介也回連 FB／IG／Threads／官網，形成雙向互證。
- 排除：官網媒體區的 Firstory 單集「遠見 on air」（open.firstory.fm/story/cmupa090h00bn01t45r1s0rnd），那是他上別人節目的來賓集，不是本人的 Podcast。
- 查無：X、TikTok、本人 Podcast。

### 魏造文（2 號，無黨籍）
- 查無任何本人帳號。媒體稱他為「最神秘候選人」：不設競總、不掛旗，登記資料也選擇不公開。2026-11-10 辯論會的諧音風波之後，只有新聞台與網友的貼文。
- 不需要待查：沒有任何線索。

### 謝國樑（3 號，國民黨，現任）
- 收錄：FB hsieh.kuo.liang（cross_ref）。基隆市政府官網的 Facebook 專頁列表把「市長謝國樑」直連到這頁，維基也同列。IG kl_george_hsieh（cross_ref）、LINE @keelung_hsieh（cross_ref，LINE 頁自述「基隆市長 謝國樑 官方line帳號」，role 標 incumbent）、YouTube UCvUV3Av_wV626FB1-ltmoLQ（cross_ref，「小愛爸爸謝國樑」，訂閱很少）。
- 市府官網並非候選人官網，所以 FB 沒有升為 first_party。
- 排除：基隆市政府、魅力基隆等機關粉專；「山海公民拆樑行動 - 罷免謝國樑」（反方團體）。2026-06 有冒名 LINE 群組詐騙報導，LINE 只認 @keelung_hsieh。
- 待查：Threads（kl_george_hsieh 在未登入時被登入牆擋住，存在與否都無法判斷）；2026 年連任專用帳號（新聞稱他「全程直播」，推測在 FB）。
- 查無：競選官網、X、TikTok。

## 高雄（本批只有兩位無黨籍候選人）

### 王肇民（2 號，無黨籍）
- 查無任何本人帳號。新聞提到他在造勢場「自架手機直播」，但沒說直播平台與帳號名稱；搜尋 FB／YouTube／TikTok 都只有民視等新聞台的影片。
- 待查：直播所用的帳號（很可能是 FB 個人頁）。

### 洪方隆（4 號，無黨籍）
- 收錄：Threads @ivyralphung（cross_ref）。2026-11-14 fetch 的自介學經歷（哥倫比亞大學、中興環工、常春藤電訊）與聯合報、中天報導的背景一致，2026-11-12 的貼文是高雄政見；GitHub 使用者 Ralphung 2026-10-03 在本 repo issue #2 以「洪方隆」名義自報此帳號；LinkedIn「洪方隆 Ralph IVY 常春藤電訊總經理」對得上 handle。IG ivyralphung 為 first_party（Threads 自介直連）。
- 待查：FB fang.lung.hung 與 X ivyralphung。兩者只有 issue #2 的自報（GitHub 帳號本身無法驗證是否本人），搜尋引擎找不到這兩頁，未收。
- 查無：官網、YouTube、LINE、TikTok。

## 南投

### 温世政（民進黨）
- 收錄：Threads @wen_shih_cheng（cross_ref，已驗證，自介「南投縣長候選人｜牙醫師」，民進黨官方 Threads 多次標記）；FB wEnShihheng（first_party，Threads 自介直連，維基同列；handle 大小寫原文如此）；IG wen_shih_cheng（first_party，Threads 連結）。
- 排除：世樺牙醫診所粉專（shihhwa.dental，診所商業頁）、植牙中心網站。
- 查無：官網、YouTube、LINE、X、TikTok。

### 許淑華（國民黨，現任）
- YouTube @shuhua_hsu（UCe-TpqL3Nwm0z-KXNgjUeWw）簡介「南投縣長許淑華官方頻道」，about 頁連結區直連 FB profile.php?id=100044482117533 與 IG shuhua_hsu，因此 FB／IG 為 first_party，YouTube 本身為 cross_ref（維基同列）。
- Threads @shuhua_hsu（已驗證，連 IG）與 LINE @shuhua_hsu（地址為縣府，3.6 萬好友）為 cross_ref。帳號以本名經營、自介寫職稱，比照蔣萬安前例，role 標 personal。
- 維基列的舊 page ID 130771133668155（YouTube 影片簡介 reurl 短鏈也指向這頁）推定與 100044482117533 是同一粉專（新版粉專會同時有 page ID 與 profile ID），未另立一列。
- 排除：TikTok #許淑華 標籤下的第三方帳號「台灣人物誌」、南投縣政府機關帳號。
- 查無：競選官網、X、TikTok、2026 連任專用帳號。Threads 未登入只看得到 2025-01 的貼文，近期活躍度需複查。

## 需人工複查摘要
1. 陳振中 FB chen.zhen.zhong.67701：只有維基／Wikidata 一個來源，國民黨主力候選人卻零收錄，優先補查。
2. 許智富、王肇民：新聞證實有臉書活動，但缺網址。
3. 洪方隆：Threads／IG 主要靠本人在 repo issue 自報加上背景吻合；FB 與 X 未收。
4. 吳炳輝的兩個舊 FB 頁：是否仍在使用。
5. 吳淑瑾 FB：只讀到頁名，cross_ref 的佐證偏弱，建議登入確認簡介。
6. 謝國樑：Threads 是否存在；YouTube 頻道是否仍在更新。
7. 許淑華 FB 新舊兩個 ID 是否為同一頁。

<!-- batch 3 -->

查核日：2026-11-14。方法與 candidate-accounts-research-2026-07-05.md 相同：先抓競選官網或連結中心（portaly、Threads bio），其直連列 first_party；無官網者以搜尋快照、新聞引用、維基百科／Wikidata 外部連結交叉印證。FB／IG／X 擋爬，自介靠搜尋快照；Threads 個人頁可直接 fetch。沒登入任何平台，請求有間隔。

輸出：`batch3-accounts.csv`（27 列）、`batch3-candidates.csv`（17 人）。

## 宜蘭

### 林國漳（民進黨，1號）
- 官網 2026openchang.tw 當日 fetch 成功。官網與 portaly.cc/lin.kuo.chang 都直連 FB linkuochang.yilan、IG lin.kuo.chang、Threads @lin.kuo.chang、YouTube @linkuochang、LINE @821mnknz，所以 6 列全是 first_party。
- 角色：官網、FB（分類 Political Candidate）、LINE 標 campaign。IG／Threads／YT 是同一套 handle，但看不出是不是為競選新開的，暫標 personal。
- 待查：
  - portaly 圖片按鈕的 FB 連到 `profile.php?id=61582589525417`，跟 linkuochang.yilan 不一樣。這個 ID 落在新帳號區段，可能就是同一個粉專的數字 ID，但搜尋查不到，所以沒另外列。
  - 搜尋還看到兩個 FB：`lin.guo.zhang.867804`（Digital creator，約 8.8K 追蹤，VoteTW 列為外部連結）和個人檔案 `p/林國漳-100000222463680`。兩個都沒有官網直連，所以沒收。
- 查無：X、TikTok、Podcast。

### 吳宗憲（國民黨，3號）
- 官網 yilan2026.tw（「2026 宜蘭縣長競選辦公室·官方網站」）當日 fetch，直連 FB jameswu88、IG jameswu_not_jacky、YouTube @jameswu_not_jacky、X jameswunotjacky，這 4 列加官網都是 first_party。
- 官網影音區「前往 YouTube 頻道」按鈕只連到 youtube.com 首頁，是網站 bug，不影響判定。
- Threads @jameswu_not_jacky：當日 fetch 到個人頁，有驗證徽章，自介「國民黨宜蘭縣長參選人」，bio 連回 IG。官網沒有直連 Threads，所以列 cross_ref。
- 排除：同名藝人吳宗憲的相關帳號。
- 查無：LINE OA（官網寫可掃 QR 加入，但頁面上找不到 LINE 連結）、TikTok、Podcast。

### 陳宏毅（無黨籍，2號）
- 查無。52 歲，三星鄉新住民、科技公司設計工程師，無政治背景，政見勾選不公開。搜尋找不到任何社群帳號。

### 劉燦輝（無黨籍，4號）
- 查無。員山鄉人，曾選鄉長和 2024 年員山縣議員補選。
- 排除：FB `liu.can.hui.527461`。這個帳號是建築師、台北科大畢業，沒有證據跟參選人是同一人。

### 楊鉯婷（無黨籍，5號）
- 查無。39 歲，崇右企專畢業。精確搜尋只回傳名字相近的無關帳號。

## 台北（小黨／無黨籍）

### 郭璽（台灣麻將最大黨，1號）
- 排除：FB `TMJGP`（台灣麻將最大黨粉專）和黨的 YouTube。這些是政黨帳號，不收。
- 待查：TVBS 圖說寫「翻攝郭璽臉書」，表示他可能有個人 FB，但搜尋找不到網址。
- 查無：個人 FB／IG／Threads／YT、官網、LINE。

### 林志成（無黨籍，2號）
- 查無。前健美國手、中華民國健美協會前秘書長。搜尋只看到 2019 年向館長叫陣的新聞，沒有本人帳號。

### 蕭文乾（臺灣SoR無法黨，4號）
- FB `wen.hsiao.100`：他自己事業的蕭博士 SoR 美語網站創辦人頁，用「蕭博士臉書」直連這個帳號；vocus 也有轉載他的臉書文章。因為那是事業網站，不是競選官網，列 cross_ref。
- 排除：
  - YouTube @MiParty（miparty）：網站頁尾的品牌頻道，同名政黨。
  - @MiOrg：臺灣雙母語研究學會的頻道。
  - @SoRTW：補教品牌的頻道。
  - FB MilingualPalace、IG milingualpalace、LINE lin.ee/flrdUJ1：補教客服帳號。
- 查無：競選官網、Threads、X、TikTok。他只以來賓身分上過 Podcast（不良大叔），沒有自己的節目。

### 唐新民（三勢團結促進聯盟，6號）
- 查無。YouTube 上只有新聞片段和《家國論壇》錄影，都不是他自己的頻道。

## 花蓮

### 魏嘉賢（無黨籍，1號）
- 競選官網 lovehualien.com 當日 fetch 成功。站上唯一的社群連結是 FB `sunwei038563787`，所以這個 FB 是 first_party。Wikidata Q27150807 和本人的 vocus 個人頁也列同一個帳號。
- IG `weijiaxian_hualien`：Wikidata 和本人 vocus 頁都有列，搜尋快照自介「我是花蓮縣議員，魏嘉賢」。官網沒直連，列 cross_ref。
- 待查：
  - Threads `@weijiaxian_hualien`：Wikidata 有列，handle 也跟 IG 一樣，但 fetch 只拿到登入牆，確認不了帳號存在，所以沒收。
  - 新聞提到他的「個人臉書及粉絲專頁」都被洗版，可見另有一個粉專，但查不到網址。目前收的 sunwei038563787 應該是個人帳號或其中之一。
- 查無：YouTube、LINE、X、TikTok。

### 張峻（無黨籍，2號）
- Threads `@changjun.hl`：當日 fetch，自介「「張峻」官方帳號 花蓮縣議會議長 花蓮縣縣長參選人」，約 8.4K 追蹤；議員張美慧等人也標記他。列 cross_ref。
- IG `changjun.hl`：Threads bio 直連，比照 07-05 李四川「本人 Threads 指認」的作法列 first_party。IG 自介本身沒核對到。
- FB `zhang.jun.901578`：自介「我是花蓮縣縣長參選人 這是我的官方帳號」，跟 Threads 一致，也有多則報導引用他的臉書影片。列 cross_ref。
- 查無：官網、YouTube（只有新聞片段）、LINE、X、TikTok。

### 游淑貞（國民黨，3號）
- FB `CandyHualien`：Politician 粉專，簡介「美好花蓮 加You 加游！」，跟登記參選時的口號一致。列 cross_ref。
- 排除：
  - 吉安鄉公所 FB：機關帳號。
  - 8 月被發現 IP 在香港的「支持游淑貞」粉專／Threads 帳號：本人已聲明跟她和競辦無關。
- 待查：IG `candyyu1125`。自介「花蓮縣吉安鄉鄉長」，約 1.2K 追蹤，跟 FB 的「Candy」一致，但只有一個搜尋來源，沒收。
- 查無：競選官網（國民黨知識庫只有黨的政見頁）、Threads、YouTube、LINE。

### 羅佩秦（台灣工黨，4號）
- 查無。精確搜尋只找到「羅佩恩」這個不同人的 FB。

## 苗栗

### 陳品安（民進黨，1號）
- Threads `@vote4pinan` 是她的連結中心。當日 fetch，有驗證徽章，自介「苗栗縣長候選人 苗栗縣議員．陳品安律師」，競總地址和專線跟新聞報導一致。列 cross_ref。
- FB `pinanchen064` 和 IG `vote4pinan`：都由 Threads 直連，維基百科外部連結也一致，列 first_party。
- YouTube `UCGTEP0GkrQM4G0RfLXvejrA`：維基百科有列，頻道 handle @陳品安律師苗栗縣議員 也對得上，列 cross_ref。
- LINE OA `@yip9758n`：彩虹平權大平台列了 vote4pinan.tw/split-friend 連結。當日抓這個落地頁，標題是「苗栗縣長候選人陳品安的 LINE 官方帳號」，會導向 @yip9758n。列 cross_ref。
- 注意：vote4pinan.tw 首頁只回傳「vote4pinan」這個字，是 LINE 導流閘道，不是官網，所以沒列 website。
- 查無：競選官網、X、TikTok、Podcast。

### 鍾東錦（國民黨，2號，現任）
- FB `DongJinZhong`：維基百科外部連結有列，Politician 粉專。TVBS 報導小編提醒民眾認明藍勾勾，這個 FB 列 cross_ref。帳號名稱是他本人姓名，不是職稱，所以標 personal。
- 待查：
  - 維基百科列的 YouTube `UCmXEmRs2eP0GJWMooJ2skSg`（原名「苗栗縣議長 鍾東錦頻道」）：當日抓到的頻道名是「苗栗縣」，handle 是 @苗栗縣-o9b。疑似已改名或移交給縣府用途，沒收。
  - IG `tungchinchung`：自介「您好，我是鍾東錦」，約 2.2K 追蹤，只有單一搜尋來源。
  - FB 個人檔案 `100003473088429`：職稱欄列縣長、國民黨縣黨部主委。
- 排除：冒名 FB（詐團盜照）、苗栗縣政府機關帳號。
- 查無：競選官網、Threads、LINE、X、TikTok。

## 連江

### 王忠銘（國民黨，現任）
- FB 粉專 `100071514671190`：Politician，簡介「嗨！我是王忠銘！」，地址是縣府。中央社和民進黨連江縣黨部都引用他的「粉絲專頁」，列 cross_ref。帳號名是他本人姓名，所以標 personal。快照另外出現 username「cmwang1958」，但沒確認可以當 FB vanity URL 用，所以 URL 用 ID 形式。
- 待查：FB 個人帳號 `wang.zhong.ming.957663`（Digital creator，職稱欄寫縣長）。可能是本人，也可能是冒名，沒收。
- 查無：官網、IG、Threads、YouTube、LINE。

### 曹爾元（無黨籍）
- 他 2026-06-15 在臉書宣布參選，但報導沒附帳號網址。
- 排除：FB「曹爾元競選縣長後援會」（`100084058213173`）。這是 2022 年的後援會，本人官網沒有直連。
- 待查：後援會頁連到的個人檔案 `profile.php?id=100003452332048`。可能是本人，但證據只有一條。
- 查無：官網、IG、Threads、YouTube、LINE。

## 需人工複查（摘要）
1. 林國漳：portaly 上的 FB ID 61582589525417 是不是 linkuochang.yilan 的數字 ID。
2. 魏嘉賢：Threads @weijiaxian_hualien 是否存在，以及他另一個 FB 粉專的網址。
3. 張峻：IG changjun.hl 的自介（目前只靠 Threads 指認）。
4. 游淑貞：IG candyyu1125 是不是本人。
5. 鍾東錦：YouTube 頻道改名「苗栗縣」的情況，以及 IG tungchinchung。
6. 王忠銘：個人 FB wang.zhong.ming.957663，以及 cmwang1958 能不能當 vanity URL。
7. 曹爾元：個人 FB 100003452332048。
8. 郭璽：TVBS 圖說提到的「郭璽臉書」網址。
9. 吳宗憲：X jameswunotjacky 雖然官網有直連，但擋爬，沒確認是否仍在活躍。

<!-- batch 4 -->

查核日：2026-11-14。方法：以 YouTube 頻道 about 頁（curl 直取外部連結欄位）、競選官網 fetch、維基百科外部連結、議會官網為一手連結中心，搭配搜尋快照與新聞交叉印證。FB／IG／TikTok／X 擋爬，未讀其自介者以官網／YT 直連或搜尋快照佐證。LINE 短鏈實際追轉址並以 page.line.me 標題核對帳號名稱。

合計 47 列：first_party 30、cross_ref 17、unverified 0。查無帳號 5 人：王義成、陳愷璜、朱定瑀、蕭燐洪、洪麗華。

## 嘉義市

### 王義成（1 號，無黨籍）
- 查無。新聞稱其「最低調神祕」、幾乎沒有宣傳物，獨自騎機車登記，公報經歷僅列兩本著作（《天下第二富裕之門》《新加坡逛吃悟》）。多組搜尋未見任何本人帳號。

### 陳愷璜（2 號，無黨籍）
- 未收任何帳號。
- 待查：Yahoo 新聞圖說註明照片取自其粉專「陳愷璜：走尋諸羅城千人計畫 2026嘉義美學運動」，但搜尋找不到該粉專網址。報導另稱政見會透過 Podcast 與 YouTube 頻道推播，也同樣找不到頻道或節目。美學運動聯絡信箱為 mcga2026@gmail.com（非池中藝術網），artemperor 頁回 403，無法讀取上面「群組、網站」的連結。
- 排除：facebook.com/kaihuang.chen，是同名的圓山飯店員工，與本人無關。

### 張啓楷（3 號，民眾黨，藍白共推）
- YouTube 頻道 UC19rcTF7haOmhfZxFx06J-A（@張啓楷）的 about 頁直連 FB、IG、Threads（皆為 qikai.zhang01）與 TikTok @ck19621221，5 列皆為 first_party。FB 粉專簡介（搜尋快照）反向指認此頻道為「官方頻道」，維基百科外部連結也列出 FB、IG、YT。
- 民眾黨候選人頁（tpp.org.tw）回 403，未能讀取。
- 全部歸為 personal：立委時期沿用的帳號，Threads 自介已改為「嘉義市市長候選人（3號）」。
- 查無：競選官網、LINE OA、X、Podcast。

### 王美惠（4 號，民進黨）
- FB、IG、Threads、X 都用 ahueimoto 這個 handle。維基百科外部連結列出 FB、IG、X，搜尋快照的自介與名稱也一致，4 列皆為 cross_ref。
- YouTube @ahuei0415（頻道名「立法委員王美惠」）：簡介為第一人稱，handle 中的 0415 與生日一致；但頻道沒有外部連結，也沒有其他帳號指認它，列為 cross_ref。
- 找不到任何一手連結中心（官網、帶連結的 YT 簡介），所以沒有升 first_party 的依據。
- 排除：facebook.com/people/王美惠/100003574732873 是個人 profile，雖然自介是嘉義市立委，但不是主要經營帳號，且無法確認是否本人經營，未收。
- 查無：競選官網、LINE OA、TikTok、Podcast。新聞提到的政策動畫（2026-11-12）沒有寫明發在哪個平台。

### 黃宏成台灣阿成世界偉人財神總統（5 號，無黨籍）
- 收 FB RichGodPresident（頁名即全名）與 YouTube UC0KglTbKx5ii1V6chB-Ov2A（@h573257，簡介自稱 2020 總統）；維基百科外部連結也列出這兩個帳號，都是 cross_ref。
- 收 FB twahchen（改名前的舊名「黃宏成台灣阿成世界偉人」）：聯絡信箱 h573257@gmail.com 與 YT handle 一致，列 cross_ref。待查：該頁是否仍在更新。
- YT about 頁另連 dirtkiss.com，未查證內容，暫不收。
- candidate_id 只取本名「黃宏成」（huang-hung-cheng）。

## 彰化縣

### 陳素月（1 號，民進黨）
- 競選 YouTube @sayyessayyhi（「2026彰化縣長候選人陳素月官方影音」）的 about 頁直連 FB chengSayYes、IG sayyessayhi、LINE（pse.is/4yv35e 轉址至 accountId=sayyes，page.line.me/sayyes 標題為「陳素月」），這 3 列皆為 first_party。
- YT 頻道本身：沒有看到 FB 或官網反向連結，但頻道名稱與內容都是競選影片，列為 cross_ref／campaign。
- 注意：IG 是 sayyessayhi（單 y），YT 是 sayyessayyhi（雙 y），以 YT 頁面上的原始連結為準。
- 查無：競選官網、Threads、X、TikTok、Podcast。

### 魏平政（2 號，國民黨）
- FB WeiPingCheng2026（「彰化正能量 魏平政」）：2026-04 成立的參選專頁，多家媒體報導過、國民黨知識庫也收錄其影片，列 cross_ref／campaign。
- 排除：女兒經營的「彰化女兒魏敬倫」粉專（家屬助選，非本人或競總）。
- 查無：官網、IG、Threads、YouTube、LINE、X、TikTok。第三支競選影片《彰化的領航者》只在國民黨記者會上發表，找不到本人頻道。

### 邱建富（3 號，無黨籍）
- 官網 chiuchienfu.tw（first_party）直連 FB ChenfuChanghua 與 IG chenfu168，都是 first_party。官網上的 YouTube 連結指回自站，LINE 只是「#」佔位，都沒有實際帳號。
- FB 個人帳號 chenfu168：自介寫明縣長候選人③，handle 與 IG 一致，退黨宣告也是在本人臉書發的，列 cross_ref。
- 排除：GitHub JK347-byte/chiu-jianfu-campaign，自稱「開發中，非正式對外連結」。
- 查無：Threads、YouTube、X、TikTok、LINE OA。

### 陳重嘉（4 號，無黨籍，現任縣議員）
- FB politicianccc（「陳重嘉 彰化縣議員」）：彰化縣議會議員頁列出此 FB 與 politicianccc@gmail.com，2018 公報與選舉黃頁也同列，列 cross_ref／personal。新聞所述登記後的發文就在本人臉書。
- 未收：曾公開的 LINE ID 是手機號碼個人帳號，不是 OA。
- 查無：縣長競選專頁、官網、IG、YouTube。

## 新竹縣

### 鄭朝方（1 號，民進黨）
- FB newchange13、IG／Threads new.change13：維基百科列出 FB，搜尋快照顯示名稱一致，3 列都是 cross_ref。
- YouTube UCzjXmEb66RBs42wX4BC3wMA：維基百科有列，最新影片「竹北經驗. 竹縣實現」與 2026 競選主軸相同，列 cross_ref。頻道沒有簡介與外部連結。
- Threads 自介連到 zhubei2022.com（2022 竹北市長競選站），2026-11-14 無法連線，未收。
- 待查：可能另有 2026 縣長競選官網或 LINE OA，搜尋沒找到。只要找到官網或 YT 連結，就能把這 4 列升為 first_party。
- 查無：X、TikTok、Podcast。

### 徐欣瑩（2 號，國民黨）
- 官網 shesinging.tw（「2號 徐欣瑩｜2026 國民黨新竹縣長候選人」）與 YouTube @shesingingmv 互相直連。YT about 頁另連 FB shesinging.tw、IG／Threads shesingingtw，5 列皆為 first_party。
- 查無：LINE OA、X、TikTok、Podcast。

### 朱定瑀（3 號，無黨籍）
- 查無。有支持者在 Threads 拉票，也有人問到湖口服務處，但沒找到本人或競總的帳號。
- 待查：此人有競總（新埔）、服務處，也提了政見，很可能有 FB 頁，可日後用 FB 站內搜尋補查。

## 臺南市

### 蕭燐洪（1 號，臺灣SoR無法黨）
- 查無。只找到新聞與第三方 Threads 轉貼。黨帳號（無法黨、其子蕭文乾）依規則不收。

### 葉人文（4 號，無黨籍）
- 競選官網 tainanyesman.oen.tw（維基百科也列為官方競選網站）直連 FB TainanYesMan、IG tainanyesman、Threads @tainanyesman，4 列皆為 first_party／campaign。
- 排除：yesmen.com.hk、yesmen.co、The Yes Men 等同名無關帳號。
- 查無：YouTube、X、TikTok、LINE OA。

## 屏東縣

### 蘇清泉（1 號，國民黨）
- YouTube @ptdrsu（「立法委員 蘇清泉 - 阿泉的Vlog」）的 about 頁直連 FB、IG、Threads（皆 ptdrsu）、TikTok @ptdrsu705、LINE（lin.ee/bqqYeejD → @lqh3251p，頁面標題為「蘇清泉」），這 5 列皆為 first_party。
- YT 頻道本身沒有看到反向連結，列 cross_ref。它的 handle 與「官方粉絲團」一致，粉絲團信箱是立法院網域。
- 查無：競選官網、X、Podcast。

### 周春米（2 號，民進黨，現任）
- YouTube @ricechou819 與 FB RiceChouChunMi 互相連結（FB 簡介見於搜尋快照）。YT about 頁另連 IG／Threads choulittlerice 與 LINE @966geqhk（FB 簡介列的 lin.ee/r5W05mW 也轉址到同一帳號），5 列皆為 first_party。
- 帳號名稱都是「周春米」，不是以縣長職稱經營，所以 role 標 personal，而非 incumbent。縣府機關帳號依規則不收。
- 查無：連任競選官網、X、TikTok、Podcast。

## 臺中市

### 洪麗華（2 號，司法正義黨）
- 查無。新聞稱她獨自開宣傳車掃街，沒有報導提到任何社群帳號，限定平台搜尋也只找到第三方轉貼。
