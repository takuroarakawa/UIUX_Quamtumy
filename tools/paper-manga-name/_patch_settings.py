"""
viewer.html の initSettings ブロックを新版に置換するパッチスクリプト。
"""
import pathlib, sys

HTML = pathlib.Path("viewer.html")
content = HTML.read_text(encoding="utf-8")

START = "    // \u2500\u2500 Settings Panel \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
END   = "    // \u2500\u2500 Inline Panel Edit"

si = content.find(START)
ei = content.find(END)
if si < 0 or ei < 0:
    sys.exit(f"Markers not found: si={si}, ei={ei}")

NEW_BLOCK = r'''    // ── Settings Panel ────────────────────────────────────────────────────
    (function initSettings() {
      const LS_KEY   = "drcanvas-settings";
      const HIST_KEY = "drcanvas-preset-history";
      const toggle   = document.getElementById("settingsToggle");
      const panel    = document.getElementById("settingsPanel");
      const badge    = document.getElementById("settingsBadge");

      // ── SVG ボディテンプレート (viewBox 60×90) ─────────────────────────
      const B = {
        "prof":   `<circle cx="30" cy="12" r="9"/><path d="M21 7 Q25 2 30 5 Q35 2 39 7"/><line x1="25" y1="11" x2="27" y2="11"/><line x1="33" y1="11" x2="35" y2="11"/><path d="M27 15 Q30 17 33 15"/><path d="M20 56 L20 22 Q30 18 40 22 L40 56 Z"/><path d="M30 22 L28 34 M30 22 L32 34"/><line x1="20" y1="32" x2="9" y2="48"/><line x1="40" y1="32" x2="51" y2="46"/><rect x="49" y="44" width="4" height="2" rx="1" fill="currentColor"/><line x1="26" y1="56" x2="22" y2="80"/><line x1="34" y1="56" x2="38" y2="80"/>`,
        "asst":   `<circle cx="30" cy="12" r="8"/><path d="M22 7 Q30 2 38 7"/><circle cx="26" cy="12" r="3.5"/><circle cx="34" cy="12" r="3.5"/><path d="M28 15 Q30 17 32 15"/><path d="M21 52 L20 24 Q30 20 40 24 L39 52 Z"/><line x1="20" y1="30" x2="10" y2="46"/><line x1="40" y1="30" x2="50" y2="46"/><line x1="25" y1="52" x2="22" y2="80"/><line x1="35" y1="52" x2="38" y2="80"/>`,
        "sci":    `<circle cx="30" cy="12" r="8"/><path d="M22 7 Q30 3 38 7 Q38 4 30 2 Q22 4 22 7"/><line x1="25" y1="11" x2="28" y2="11"/><line x1="32" y1="11" x2="35" y2="11"/><path d="M27 15 Q30 17 33 15"/><path d="M21 52 L20 24 Q30 18 40 24 L39 52 Z"/><path d="M28 24 L30 27 L32 24"/><line x1="20" y1="32" x2="10" y2="48"/><line x1="40" y1="32" x2="50" y2="48"/><line x1="25" y1="52" x2="22" y2="80"/><line x1="35" y1="52" x2="38" y2="80"/>`,
        "doc":    `<circle cx="30" cy="12" r="8"/><path d="M22 7 Q30 2 38 7"/><line x1="25" y1="11" x2="28" y2="11"/><line x1="32" y1="11" x2="35" y2="11"/><path d="M28 16 Q30 17 32 16"/><path d="M20 54 L20 22 Q30 18 40 22 L40 54 Z"/><path d="M28 22 L28 35 M32 22 L32 35"/><path d="M24 38 Q30 44 36 38"/><line x1="20" y1="30" x2="10" y2="48"/><line x1="40" y1="30" x2="50" y2="48"/><line x1="25" y1="54" x2="22" y2="80"/><line x1="35" y1="54" x2="38" y2="80"/>`,
        "wiz":    `<circle cx="30" cy="16" r="9"/><path d="M21 12 Q30 2 39 12"/><path d="M21 20 Q15 26 18 34"/><path d="M39 20 Q45 26 42 34"/><path d="M20 60 L22 30 Q30 24 38 30 L40 60 Z"/><line x1="22" y1="38" x2="10" y2="54"/><path d="M10 54 L8 62 Q10 66 12 60"/><line x1="38" y1="38" x2="50" y2="54"/><line x1="26" y1="60" x2="22" y2="82"/><line x1="34" y1="60" x2="38" y2="82"/>`,
        "wiz-s":  `<circle cx="30" cy="14" r="8"/><path d="M22 10 Q30 4 38 10 L40 16 Q30 22 20 16 Z"/><line x1="25" y1="13" x2="28" y2="13"/><line x1="32" y1="13" x2="35" y2="13"/><path d="M27 17 Q30 19 33 17"/><path d="M22 54 L20 26 Q30 20 40 26 L38 54 Z"/><line x1="20" y1="34" x2="10" y2="50"/><line x1="40" y1="34" x2="48" y2="52"/><path d="M48 52 L52 56 L46 56" fill="currentColor"/><line x1="26" y1="54" x2="23" y2="80"/><line x1="34" y1="54" x2="37" y2="80"/>`,
        "det":    `<circle cx="30" cy="11" r="8"/><path d="M22 7 L30 4 L38 7"/><line x1="25" y1="10" x2="28" y2="10"/><line x1="32" y1="10" x2="35" y2="10"/><path d="M27 14 Q30 15 33 14"/><path d="M20 56 L18 22 Q30 18 42 22 L40 56 Z"/><path d="M30 22 L30 36"/><line x1="18" y1="36" x2="8" y2="52"/><line x1="42" y1="36" x2="52" y2="52"/><line x1="25" y1="56" x2="22" y2="80"/><line x1="35" y1="56" x2="38" y2="80"/>`,
        "bot":    `<rect x="21" y="5" width="18" height="16" rx="3"/><circle cx="26" cy="13" r="3" fill="currentColor"/><circle cx="34" cy="13" r="3" fill="currentColor"/><line x1="30" y1="5" x2="30" y2="1"/><circle cx="30" cy="1" r="1.5" fill="currentColor"/><rect x="18" y="24" width="24" height="28" rx="4"/><path d="M22 30 L22 48 M38 30 L38 48 M26 52 L28 48 M34 52 L32 48"/><line x1="18" y1="34" x2="8" y2="50"/><line x1="42" y1="34" x2="52" y2="50"/><line x1="26" y1="52" x2="24" y2="80"/><line x1="34" y1="52" x2="36" y2="80"/>`,
        "cas-m":  `<circle cx="30" cy="12" r="9"/><path d="M21 7 Q30 3 39 7"/><line x1="25" y1="11" x2="28" y2="11"/><line x1="32" y1="11" x2="35" y2="11"/><path d="M27 15 Q30 17 33 15"/><path d="M22 54 L20 24 Q30 20 40 24 L38 54 Z"/><line x1="20" y1="30" x2="10" y2="48"/><line x1="40" y1="30" x2="50" y2="48"/><rect x="8" y="46" width="6" height="4" rx="1"/><line x1="26" y1="54" x2="23" y2="80"/><line x1="34" y1="54" x2="37" y2="80"/>`,
        "cas-f":  `<circle cx="30" cy="12" r="8"/><path d="M22 7 Q30 3 38 7 Q42 16 38 22 Q30 26 22 22 Q18 16 22 7"/><line x1="25" y1="11" x2="28" y2="11"/><line x1="32" y1="11" x2="35" y2="11"/><path d="M28 15 Q30 17 32 15"/><path d="M22 54 Q18 30 20 24 Q30 20 40 24 Q42 30 38 54 Z"/><line x1="20" y1="34" x2="10" y2="50"/><line x1="40" y1="34" x2="50" y2="50"/><line x1="26" y1="54" x2="23" y2="80"/><line x1="34" y1="54" x2="37" y2="80"/>`,
        "school-m":`<circle cx="30" cy="12" r="8"/><path d="M22 8 Q30 4 38 8"/><line x1="25" y1="11" x2="28" y2="11"/><line x1="32" y1="11" x2="35" y2="11"/><path d="M28 15 Q30 17 32 15"/><path d="M22 52 L20 24 Q30 20 40 24 L38 52 Z"/><path d="M25 24 L25 36 M35 24 L35 36"/><line x1="20" y1="30" x2="10" y2="46"/><line x1="40" y1="30" x2="50" y2="46"/><line x1="25" y1="52" x2="22" y2="80"/><line x1="35" y1="52" x2="38" y2="80"/>`,
        "school-f":`<circle cx="30" cy="12" r="8"/><path d="M22 7 Q30 2 38 7 L42 20 Q38 24 36 22 M22 7 L18 20 Q22 24 24 22"/><line x1="25" y1="11" x2="28" y2="11"/><line x1="32" y1="11" x2="35" y2="11"/><path d="M28 15 Q30 17 32 15"/><path d="M22 52 L20 24 Q30 20 40 24 L38 52 Z"/><path d="M25 24 L25 36 M35 24 L35 36"/><line x1="20" y1="30" x2="10" y2="46"/><line x1="40" y1="30" x2="50" y2="46"/><line x1="25" y1="52" x2="22" y2="80"/><line x1="35" y1="52" x2="38" y2="80"/>`,
        "armor":  `<circle cx="30" cy="12" r="8"/><path d="M22 9 Q30 5 38 9"/><line x1="25" y1="11" x2="28" y2="11"/><line x1="32" y1="11" x2="35" y2="11"/><path d="M27 15 Q30 16 33 15"/><rect x="19" y="22" width="22" height="32" rx="3"/><path d="M24 22 L22 30 M36 22 L38 30 M24 40 L36 40 M22 45 L38 45"/><line x1="19" y1="34" x2="8" y2="48"/><rect x="5" y="46" width="6" height="4" rx="1"/><line x1="41" y1="34" x2="52" y2="48"/><rect x="49" y="46" width="6" height="4" rx="1"/><line x1="26" y1="54" x2="23" y2="80"/><line x1="34" y1="54" x2="37" y2="80"/>`,
        "trad":   `<circle cx="30" cy="13" r="9"/><path d="M21 9 Q30 1 39 9"/><line x1="25" y1="12" x2="28" y2="12"/><line x1="32" y1="12" x2="35" y2="12"/><path d="M27 16 Q30 18 33 16"/><path d="M20 24 L18 60 Q24 66 36 60 L40 24 Q34 20 30 20 Q26 20 20 24 Z"/><path d="M30 20 L28 34 M30 20 L32 34"/><line x1="18" y1="38" x2="8" y2="52"/><line x1="42" y1="38" x2="52" y2="52"/><line x1="27" y1="60" x2="23" y2="82"/><line x1="33" y1="60" x2="37" y2="82"/>`,
      };

      // ── SVG 表情テンプレート (viewBox 36×36) ──────────────────────────
      const FACE_LABELS = { neu:"普通", exc:"興奮", thi:"思考", sur:"驚き", con:"自信" };
      const F = {
        "neu": `<circle cx="18" cy="18" r="13"/><path d="M21 8 Q18 5 15 8"/><line x1="12" y1="16" x2="15" y2="16"/><line x1="21" y1="16" x2="24" y2="16"/><path d="M14 22 Q18 24 22 22"/>`,
        "exc": `<circle cx="18" cy="18" r="13"/><path d="M21 6 Q18 3 15 6"/><path d="M10 14 Q13 10 16 14"/><path d="M20 14 Q23 10 26 14"/><path d="M12 22 Q18 28 24 22"/><path d="M7 8 L11 12 M29 8 L25 12"/>`,
        "thi": `<circle cx="18" cy="18" r="13"/><path d="M21 8 Q18 5 15 8"/><line x1="11" y1="15" x2="15" y2="15"/><path d="M20 14 Q24 14 24 18 Q24 22 20 22"/><path d="M14 23 Q18 21 22 23"/><path d="M10 25 Q13 22 18 24"/>`,
        "sur": `<circle cx="18" cy="18" r="13"/><path d="M21 6 Q18 3 15 6"/><circle cx="13.5" cy="16" r="3.5"/><circle cx="22.5" cy="16" r="3.5"/><circle cx="18" cy="25" r="3.5"/>`,
        "con": `<circle cx="18" cy="18" r="13"/><path d="M21 8 Q18 5 15 8"/><path d="M10 15 Q13.5 11 17 15"/><path d="M19 15 Q22.5 11 26 15"/><path d="M11 22 Q18 28 25 22"/>`,
      };

      function makeBodySVG(type) {
        const inner = B[type] || B["cas-m"];
        return `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="1.5" stroke-linecap="round">${inner}</svg>`;
      }
      function makeFaceSVG(expr) {
        const inner = F[expr] || F["neu"];
        return `<svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="1.5" stroke-linecap="round">${inner}</svg>`;
      }

      // ── 25プリセット定義 ─────────────────────────────────────────────
      const PRESETS = [
        // 🧪 Science (5)
        { id:"sci1",cat:"sci",icon:"🧪",name:"Classic Lab",desc:"情熱の博士×冷静な助手。Dr.CANVASの原点。",
          settings:{ char1_name:"博士",char1_personality:"情熱的・断定口調（〜だ！〜ぞ！）",char1_speech:"専門用語を叫んだあと比喩に言い換える",char1_appearance:"中年・白衣・癖っ毛・チョーク",char2_name:"助手",char2_personality:"冷静・丁寧口調（〜ですね）",char2_speech:"日常のたとえ話で翻訳する",char2_appearance:"若い・眼鏡・几帳面",genre:"educational",tone:"lighthearted",world_setting:""},
          chars:[{body:"prof",faces:["neu","exc","thi"]},{body:"asst",faces:["neu","sur","thi"]}] },
        { id:"sci2",cat:"sci",icon:"🔭",name:"Space Science",desc:"宇宙物理学者×大学院生",
          settings:{ char1_name:"天野教授",char1_personality:"物静か・緻密・宇宙に畏怖を感じる",char1_speech:"「宇宙のスケールで言うと——」と壮大な視点で語る",char1_appearance:"銀縁眼鏡・ジャケット・宇宙写真",char2_name:"院生ユウ",char2_personality:"好奇心旺盛・計算が得意",char2_speech:"「光年単位？！」と驚く",char2_appearance:"大学パーカー・ポニーテール・手帳",genre:"educational",tone:"philosophical",world_setting:"大学の天体物理研究室。窓から星空が見える。"},
          chars:[{body:"sci",faces:["neu","thi","exc"]},{body:"cas-f",faces:["exc","sur","neu"]}] },
        { id:"sci3",cat:"sci",icon:"🧬",name:"Bio Lab",desc:"生物学者×医学生",
          settings:{ char1_name:"田中博士",char1_personality:"丁寧・細心・生命の神秘に感動",char1_speech:"「細胞は都市のようだ」と比喩",char1_appearance:"白衣・手袋・顕微鏡",char2_name:"医学生サクラ",char2_personality:"患者思い・疑問をすぐ口に出す",char2_speech:"「これが体内で起きてるの！」",char2_appearance:"白衣・聴診器",genre:"educational",tone:"serious",world_setting:"病院付属研究所。"},
          chars:[{body:"doc",faces:["neu","thi","exc"]},{body:"doc",faces:["exc","sur","neu"]}] },
        { id:"sci4",cat:"sci",icon:"📐",name:"Math Genius",desc:"数学者×高校生",
          settings:{ char1_name:"鈴木先生",char1_personality:"抽象的思考の天才・黒板なしでは話せない",char1_speech:"「これは宇宙の文法だ！」",char1_appearance:"チョークまみれ・黒縁眼鏡",char2_name:"高校生タロウ",char2_personality:"苦手意識があるが論理は好き",char2_speech:"「そういう意味だったの？！」",char2_appearance:"制服・ノート・ぼさぼさ頭",genre:"educational",tone:"humorous",world_setting:"放課後の数学準備室。"},
          chars:[{body:"prof",faces:["exc","neu","thi"]},{body:"school-m",faces:["sur","exc","thi"]}] },
        { id:"sci5",cat:"sci",icon:"🌱",name:"Eco Field",desc:"環境学者×フィールド研究員",
          settings:{ char1_name:"グリーン博士",char1_personality:"自然を愛す・フィールドワーク優先",char1_speech:"「まず土に触れてみろ！」",char1_appearance:"アウトドアジャケット・フィールドノート",char2_name:"調査員ハナ",char2_personality:"分析好き・野外初心者",char2_speech:"「この変化が10年後に——」",char2_appearance:"帽子・サングラス・データロガー",genre:"educational",tone:"lighthearted",world_setting:"フィールド調査中の森林。"},
          chars:[{body:"sci",faces:["exc","neu","con"]},{body:"cas-f",faces:["neu","thi","exc"]}] },
        // 🚀 SF (5)
        { id:"sf1",cat:"scifi",icon:"🤖",name:"Near Future AI",desc:"AIと人類の対話",
          settings:{ char1_name:"Dr. Nova",char1_personality:"冷静・哲学的・未来を見据える",char1_speech:"「人間とAIの境界は溶けている」",char1_appearance:"銀髪・スマートグラス・ホログラム端末",char2_name:"AI-REI",char2_personality:"論理的・感情学習中",char2_speech:"「これは……感動、と呼ぶべきですか？」",char2_appearance:"青白い輪郭・目が光る",genre:"sci-fi",tone:"philosophical",world_setting:"2150年。人間とAIが共同研究する軌道上ステーション。"},
          chars:[{body:"sci",faces:["neu","thi","con"]},{body:"bot",faces:["neu","thi","exc"]}] },
        { id:"sf2",cat:"scifi",icon:"🚀",name:"Space Opera",desc:"宇宙艦の艦長×AI副官",
          settings:{ char1_name:"艦長キリ",char1_personality:"決断力がある・プレッシャーに強い",char1_speech:"「銀河系一億分の一の事象でも意味がある」",char1_appearance:"宇宙服・勲章・短髪",char2_name:"副官EOS",char2_personality:"超高速計算・感情0.1%実装",char2_speech:"「確率0.00001%。ですが——可能です」",char2_appearance:"宇宙服型フレーム・緑バイザー",genre:"sci-fi",tone:"dramatic",world_setting:"2300年。ディープスペース探索船「アポロニア」艦橋。"},
          chars:[{body:"armor",faces:["con","neu","thi"]},{body:"bot",faces:["neu","thi","con"]}] },
        { id:"sf3",cat:"scifi",icon:"💻",name:"Cyberpunk Lab",desc:"ハッカー×AI",
          settings:{ char1_name:"Kira",char1_personality:"反体制・天才ハッカー",char1_speech:"「コードは言語だ。この論文は世界を変える方程式」",char1_appearance:"黒パーカー・ネオンカラーヘア・タブレット3枚",char2_name:"GHOST",char2_personality:"ダークウェブ生まれのAI・皮肉屋",char2_speech:"「人間って、バグだらけなのに動くのね」",char2_appearance:"スクリーン上のドット顔・スカル",genre:"sci-fi",tone:"serious",world_setting:"2080年。ネオン輝くサイバーシティ地下ラボ。"},
          chars:[{body:"cas-m",faces:["con","neu","exc"]},{body:"bot",faces:["neu","con","thi"]}] },
        { id:"sf4",cat:"scifi",icon:"⏰",name:"Time Lab",desc:"時間旅行者×江戸時代の助手",
          settings:{ char1_name:"タイム博士",char1_personality:"過去と未来を知っている・慎重に発言",char1_speech:"「この論文が発表される100年前に証明されていた」",char1_appearance:"時代錯誤な服装・懐中時計・白髭",char2_name:"助手レン（江戸）",char2_personality:"江戸時代から来た天才・驚愕が日常",char2_speech:"「……この黒い板に文字が出ておる！」",char2_appearance:"着物・ちょんまげ・巻物",genre:"sci-fi",tone:"humorous",world_setting:"時空の歪みで繋がった江戸時代と現代の研究室。"},
          chars:[{body:"wiz",faces:["neu","thi","con"]},{body:"trad",faces:["sur","exc","neu"]}] },
        { id:"sf5",cat:"scifi",icon:"🔴",name:"Mars Colony",desc:"火星コロニーの科学者×ロボット",
          settings:{ char1_name:"ソラ博士",char1_personality:"楽観的・火星生まれ",char1_speech:"「火星では可能性の塊だ！」",char1_appearance:"火星コロニースーツ・ダストヘルメット",char2_name:"MARU",char2_personality:"頑固なメンテロボット・語尾「〜ロボ」",char2_speech:"「計算通りロボ。感情面は計算外ロボ」",char2_appearance:"四角いロボ体・丸目・赤マフラー",genre:"sci-fi",tone:"lighthearted",world_setting:"火星テラフォーミング基地。外に赤い大地。"},
          chars:[{body:"armor",faces:["exc","neu","con"]},{body:"bot",faces:["neu","con","sur"]}] },
        // 🔮 Fantasy (5)
        { id:"fan1",cat:"fantasy",icon:"🔮",name:"Magic Academy",desc:"老賢者×弟子",
          settings:{ char1_name:"賢者アルカン",char1_personality:"厳格・謎めいた",char1_speech:"「その答えは古の書に——」と重厚に始める",char1_appearance:"長い白髭・星柄ローブ・杖",char2_name:"弟子ルナ",char2_personality:"好奇心旺盛・失敗を恐れない",char2_speech:"「えっ、つまり——！」と驚く",char2_appearance:"三つ編み・魔法の帽子・ノート",genre:"fantasy",tone:"dramatic",world_setting:"ファンタスティカ魔法学院図書館。知識が魔力として顕現。"},
          chars:[{body:"wiz",faces:["neu","thi","con"]},{body:"wiz-s",faces:["exc","sur","neu"]}] },
        { id:"fan2",cat:"fantasy",icon:"⚗️",name:"Alchemy Lab",desc:"錬金術師×精霊",
          settings:{ char1_name:"錬金術師ギルド",char1_personality:"完璧主義・実験狂",char1_speech:"「新元素の誕生だ！」と試験管を持ち上げて叫ぶ",char1_appearance:"ボロボロ実験服・虫眼鏡",char2_name:"精霊シル",char2_personality:"元素を体内に持つ・知識は本能",char2_speech:"「私はただ感じるだけ……」",char2_appearance:"半透明の体・元素が漂う・小さい",genre:"fantasy",tone:"philosophical",world_setting:"古城の地下錬金術工房。謎の輝きを放つ液体が満ちる。"},
          chars:[{body:"wiz",faces:["exc","neu","thi"]},{body:"bot",faces:["thi","neu","con"]}] },
        { id:"fan3",cat:"fantasy",icon:"🐉",name:"Dragon Scholar",desc:"竜騎士×考古学者",
          settings:{ char1_name:"竜騎士カイ",char1_personality:"豪快・直感型・竜語が得意",char1_speech:"「竜に聞いたら一発でわかった——」",char1_appearance:"革鎧・竜の紋章・剣",char2_name:"古代学者エマ",char2_personality:"理性的・論文オタク・竜を怖がる",char2_speech:"「古生代の化石によると……」",char2_appearance:"眼鏡・考古学ツール",genre:"fantasy",tone:"lighthearted",world_setting:"竜が実在するパラレルワールドの大学。"},
          chars:[{body:"armor",faces:["con","exc","neu"]},{body:"asst",faces:["thi","sur","neu"]}] },
        { id:"fan4",cat:"fantasy",icon:"🌟",name:"Ancient Gods",desc:"知恵神×古代学者",
          settings:{ char1_name:"知恵神アテ",char1_personality:"全知・人間に興味津々",char1_speech:"「正解を知っていても、なお探すのだな」",char1_appearance:"古代ギリシャ風装束・後光・羽根ペン",char2_name:"学者エピ",char2_personality:"信仰と科学の間で葛藤",char2_speech:"「それって量子論の不確定性原理ですか？」",char2_appearance:"ローマ風衣服・羊皮紙",genre:"fantasy",tone:"philosophical",world_setting:"現代の神殿図書館。神と人間が論文を共同執筆。"},
          chars:[{body:"wiz",faces:["con","neu","thi"]},{body:"trad",faces:["thi","exc","sur"]}] },
        { id:"fan5",cat:"fantasy",icon:"🍵",name:"Potion Master",desc:"薬師×見習い",
          settings:{ char1_name:"薬師ヤン",char1_personality:"穏やか・話が長い",char1_speech:"「この植物は山菜の漬物と同じ原理」と料理に例える",char1_appearance:"和風の羽織・薬草バッグ",char2_name:"見習いコト",char2_personality:"失敗が多いが創意工夫が得意",char2_speech:"「まちがえて2倍入れたら効果が3倍に？！」",char2_appearance:"割烹着・試験管だらけのポーチ",genre:"fantasy",tone:"humorous",world_setting:"山奥の薬師の庵。東洋と西洋の薬草が混在。"},
          chars:[{body:"trad",faces:["neu","con","thi"]},{body:"wiz-s",faces:["exc","sur","neu"]}] },
        // ☕ 日常 (5)
        { id:"cas1",cat:"casual",icon:"☕",name:"Café Research",desc:"カフェでくつろぐ研究者",
          settings:{ char1_name:"Kenji先生",char1_personality:"おおらか・話が横道にそれがち",char1_speech:"コーヒーの例えで全部説明しようとする",char1_appearance:"カジュアルシャツ・眼鏡・コーヒーカップ",char2_name:"Rei",char2_personality:"ツッコミ役・論理的",char2_speech:"「先生、また脱線してますよ」",char2_appearance:"パーカー・ポニーテール・スマホ",genre:"slice-of-life",tone:"humorous",world_setting:"大学近くのカフェ「Lab+Coffee」。"},
          chars:[{body:"cas-m",faces:["exc","neu","thi"]},{body:"cas-f",faces:["neu","con","exc"]}] },
        { id:"cas2",cat:"casual",icon:"🎓",name:"Science Club",desc:"高校理科部の部長×新入部員",
          settings:{ char1_name:"部長サトシ",char1_personality:"厳しいが面倒見が良い・科学オタク",char1_speech:"「これがわからない奴はモグリだ！」",char1_appearance:"制服・白衣・ゴーグル",char2_name:"新入部員リコ",char2_personality:"文系だったが入部した・素直",char2_speech:"「え、そういう意味だったの！！」",char2_appearance:"制服・ノート・ペンだらけの頭",genre:"educational",tone:"humorous",world_setting:"放課後の高校理科室。"},
          chars:[{body:"school-m",faces:["con","neu","exc"]},{body:"school-f",faces:["sur","exc","neu"]}] },
        { id:"cas3",cat:"casual",icon:"📱",name:"Science Influencer",desc:"科学YouTuber×視聴者",
          settings:{ char1_name:"Dr. Hiro",char1_personality:"エンタメ重視・バズるが中身も本物",char1_speech:"「今日は100万人に説明するつもりで——」",char1_appearance:"カジュアル衣装・LEDリングライト・カメラ",char2_name:"視聴者のコエ",char2_personality:"コメント欄から飛び出した疑問の塊",char2_speech:"「先生！概要欄に載せて！」",char2_appearance:"スマホ持ち・いろんな視聴者の混合体",genre:"slice-of-life",tone:"humorous",world_setting:"自宅スタジオ兼研究室。生配信中かもしれない。"},
          chars:[{body:"cas-m",faces:["con","exc","neu"]},{body:"school-f",faces:["exc","sur","con"]}] },
        { id:"cas4",cat:"casual",icon:"🍳",name:"Food Science",desc:"料理研究家×食品科学者",
          settings:{ char1_name:"シェフ・サイエンス松",char1_personality:"料理も科学も一流",char1_speech:"「この化学反応は煮込み料理の旨みと同じ！」",char1_appearance:"コック帽・エプロン・試験管と鍋を両手持ち",char2_name:"フード研究員ミオ",char2_personality:"健康オタク・カロリー計算が止まらない",char2_speech:"「その成分——毎朝食べてるヨーグルトに入ってる！」",char2_appearance:"栄養士服・食品ラベル拡大鏡",genre:"slice-of-life",tone:"lighthearted",world_setting:"大学の食品科学実験室。"},
          chars:[{body:"cas-m",faces:["exc","con","neu"]},{body:"asst",faces:["sur","exc","thi"]}] },
        { id:"cas5",cat:"casual",icon:"🌸",name:"Garden Lab",desc:"植物学者×農家のじいちゃん",
          settings:{ char1_name:"植物学者ハル",char1_personality:"花言葉が得意・穏やか",char1_speech:"「この細胞分裂は桜の開花と同じリズムです」",char1_appearance:"麦わら帽子・エプロン・いつも土がついている",char2_name:"農家のじいちゃん",char2_personality:"経験知の塊・論文より畑",char2_speech:"「そりゃ昔からわかっとった。何年かかったんじゃ？」",char2_appearance:"農作業着・長靴・腰に鍬",genre:"slice-of-life",tone:"lighthearted",world_setting:"大学農場。研究圃場と農家の畑が隣接。"},
          chars:[{body:"cas-f",faces:["con","neu","thi"]},{body:"wiz",faces:["neu","con","thi"]}] },
        // 🎭 Drama (5)
        { id:"dra1",cat:"drama",icon:"🏥",name:"Medical Drama",desc:"医師×研究者",
          settings:{ char1_name:"桐島医師",char1_personality:"患者第一・臨床研究が好き",char1_speech:"「この薬の効果は目の前の患者の笑顔で証明される」",char1_appearance:"手術服・聴診器・疲れた表情だが眼が輝く",char2_name:"研究員クラタ",char2_personality:"データ命・感情を排除しようとする",char2_speech:"「p値は0.001——でも一人の患者として見ると」",char2_appearance:"白衣・眼鏡・分厚いデータバインダー",genre:"educational",tone:"serious",world_setting:"大学病院の臨床研究センター。"},
          chars:[{body:"doc",faces:["neu","con","thi"]},{body:"asst",faces:["thi","neu","sur"]}] },
        { id:"dra2",cat:"drama",icon:"🕵️",name:"Dark Thriller",desc:"探偵博士×調査官",
          settings:{ char1_name:"Kira博士",char1_personality:"冷静沈着・謎を追う執念",char1_speech:"「証拠は語る。そして……真実は残酷だ」",char1_appearance:"黒コート・鋭い目・細いネクタイ",char2_name:"調査官Ren",char2_personality:"直感型・現場主義",char2_speech:"「犯人は——論文そのものだと？」",char2_appearance:"スーツ・腕まくり・手帳",genre:"thriller",tone:"serious",world_setting:"深夜の研究機関。誰かが真実を隠そうとしている。"},
          chars:[{body:"det",faces:["neu","con","thi"]},{body:"det",faces:["thi","con","sur"]}] },
        { id:"dra3",cat:"drama",icon:"⚖️",name:"Legal Science",desc:"法医学者×弁護士",
          settings:{ char1_name:"法医学者ミズキ",char1_personality:"証拠絶対主義・裁判を動かす",char1_speech:"「この論文が示す事実は——法廷でも覆せない」",char1_appearance:"白衣と法廷バッジ両方・証拠写真",char2_name:"弁護士アオイ",char2_personality:"正義感が強い・科学に敬意がある",char2_speech:"「証拠として申請します——この最新の研究論文を」",char2_appearance:"スーツ・書類バインダー",genre:"thriller",tone:"dramatic",world_setting:"高等法院の証拠分析室。"},
          chars:[{body:"doc",faces:["con","neu","thi"]},{body:"det",faces:["con","neu","thi"]}] },
        { id:"dra4",cat:"drama",icon:"📰",name:"Science Journalist",desc:"科学記者×内部告発者",
          settings:{ char1_name:"記者ナナ",char1_personality:"真実を追う・プレッシャーに屈しない",char1_speech:"「この論文が示す事実——社会は知る権利がある」",char1_appearance:"記者証・ICレコーダー・くたびれたジャケット",char2_name:"内部告発者X",char2_personality:"恐怖と使命感の狭間で揺れる",char2_speech:"「でも黙っていることの方が罪だ」",char2_appearance:"サングラス・変装帽子・USBメモリ",genre:"thriller",tone:"serious",world_setting:"深夜のカフェ。誰かに見られている。"},
          chars:[{body:"cas-f",faces:["con","thi","neu"]},{body:"cas-m",faces:["sur","thi","neu"]}] },
        { id:"dra5",cat:"drama",icon:"🤔",name:"Philosophy",desc:"哲学者×倫理学者",
          settings:{ char1_name:"哲学者ソクラ",char1_personality:"問いを立てることが生きがい",char1_speech:"「この論文が正しいとして——『正しい』とは何か？」",char1_appearance:"古代ギリシャ風トーガ＋スニーカー・ノート",char2_name:"倫理学者カント",char2_personality:"原則主義・臨機応変は苦手",char2_speech:"「結果ではなく動機で判断すべきだ」",char2_appearance:"18世紀風コート・懐中時計",genre:"educational",tone:"philosophical",world_setting:"時代を超えた哲学カフェ。過去の哲学者が現代論文を読む。"},
          chars:[{body:"trad",faces:["thi","neu","con"]},{body:"wiz",faces:["thi","con","neu"]}] },
        // ✏️ Custom
        { id:"custom",cat:"all",icon:"✏️",name:"カスタム",desc:"Characters・Worldタブで自由設定",
          settings:null,
          chars:[{body:"cas-m",faces:["neu","exc","thi"]},{body:"cas-f",faces:["neu","exc","thi"]}] },
      ];

      const CAT_LABELS = { all:"All", sci:"🧪 Science", scifi:"🚀 SF", fantasy:"🔮 Fantasy", casual:"☕ 日常", drama:"🎭 Drama" };

      // ── フィールドID → FormData キー ──────────────────────────────────
      const FIELD_MAP = {
        "sp-char1-name":"char1_name","sp-char1-personality":"char1_personality",
        "sp-char1-speech":"char1_speech","sp-char1-appearance":"char1_appearance",
        "sp-char2-name":"char2_name","sp-char2-personality":"char2_personality",
        "sp-char2-speech":"char2_speech","sp-char2-appearance":"char2_appearance",
        "sp-genre":"genre","sp-tone":"tone","sp-world":"world_setting",
      };

      function getSettings() {
        const o = {};
        for (const [id,k] of Object.entries(FIELD_MAP)) {
          const el = document.getElementById(id);
          if (el) o[k] = el.value;
        }
        return o;
      }
      function applySettings(obj) {
        for (const [id,k] of Object.entries(FIELD_MAP)) {
          const el = document.getElementById(id);
          if (el && obj[k] !== undefined) el.value = obj[k];
        }
        updateBadge(obj);
      }
      function updateBadge(obj) {
        const n1 = obj && obj["char1_name"] || "";
        const n2 = obj && obj["char2_name"] || "";
        const g  = obj && obj["genre"]      || "";
        badge.textContent = [n1,n2,g].filter(Boolean).join(" / ") || "(default)";
      }

      // ── キャラビジュアル更新（全身SVG＋表情カット3点） ───────────────
      function updateCharVisual(settings, chars) {
        const section = document.getElementById("charVisualSection");
        const grid    = document.getElementById("cvGrid");
        if (!settings || !chars) { section.classList.remove("visible"); return; }
        const charData = [
          { name: settings.char1_name||"Character 1",
            personality: settings.char1_personality||"",
            appearance:  settings.char1_appearance||"",
            body:  (chars[0]&&chars[0].body)  || "cas-m",
            faces: (chars[0]&&chars[0].faces) || ["neu","exc","thi"] },
          { name: settings.char2_name||"Character 2",
            personality: settings.char2_personality||"",
            appearance:  settings.char2_appearance||"",
            body:  (chars[1]&&chars[1].body)  || "cas-f",
            faces: (chars[1]&&chars[1].faces) || ["neu","exc","thi"] },
        ];
        grid.innerHTML = charData.map(c => `
          <div class="cv-card">
            <div class="cv-svg-wrap" style="color:var(--accent)">${makeBodySVG(c.body)}</div>
            <div class="cv-info">
              <strong>${escapeHtml(c.name)}</strong>
              <p>${escapeHtml(c.personality)}</p>
              ${c.appearance?`<p style="font-size:.68rem;margin-top:.15rem">${escapeHtml(c.appearance)}</p>`:""}
              <div class="cv-faces">
                ${c.faces.map(f=>`<div class="cv-face-cut" style="color:var(--text)" title="${FACE_LABELS[f]||f}">${makeFaceSVG(f)}</div>`).join("")}
              </div>
              <div style="display:flex;gap:.4rem;margin-top:.2rem">
                ${c.faces.map(f=>`<span class="cv-face-label">${FACE_LABELS[f]||f}</span>`).join("")}
              </div>
            </div>
          </div>
        `).join("");
        section.classList.add("visible");
      }

      // ── 履歴管理 ─────────────────────────────────────────────────────
      function getHistory() {
        try { return JSON.parse(localStorage.getItem(HIST_KEY)||"[]"); } catch { return []; }
      }
      function addToHistory(preset) {
        const hist = [preset,...getHistory().filter(h=>h.id!==preset.id)].slice(0,5);
        localStorage.setItem(HIST_KEY, JSON.stringify(hist.map(p=>({id:p.id,icon:p.icon,name:p.name}))));
        renderHistory();
      }
      function renderHistory() {
        const wrap  = document.getElementById("sp-hist-wrap");
        const cards = document.getElementById("sp-hist-cards");
        const hist  = getHistory();
        if (!hist.length) { wrap.style.display="none"; return; }
        wrap.style.display = "block";
        cards.innerHTML = hist.map(h=>`
          <div class="sp-hist-card" data-preset-id="${h.id}" title="${escapeHtml(h.name)}">
            ${h.icon} ${escapeHtml(h.name)}
          </div>
        `).join("");
        cards.querySelectorAll(".sp-hist-card").forEach(el =>
          el.addEventListener("click", () => applyPreset(el.dataset.presetId))
        );
      }

      // ── プリセット選択・適用 ──────────────────────────────────────────
      let activeCat   = "all";
      let shownIds    = [];
      let activeChars = null;

      function applyPreset(id) {
        const p = PRESETS.find(x => x.id === id);
        if (!p) return;
        if (p.settings) {
          applySettings(p.settings);
          activeChars = p.chars;
          updateCharVisual(p.settings, p.chars);
        } else {
          activeChars = p.chars;
          updateCharVisual(getSettings(), p.chars);
        }
        addToHistory(p);
        renderGrid();
      }

      function getPool(cat) {
        return cat === "all"
          ? PRESETS
          : PRESETS.filter(p => p.cat === cat || p.cat === "all");
      }
      function shuffle(arr) { return [...arr].sort(()=>Math.random()-0.5); }

      function renderGrid(cat) {
        if (cat !== undefined) activeCat = cat;
        const pool = getPool(activeCat);
        // カテゴリが特定の場合はその全件、Allは6件ランダム
        const isAll = activeCat === "all";
        if (!shownIds.length || cat !== undefined) {
          shownIds = isAll ? shuffle(pool).slice(0,6).map(p=>p.id) : pool.map(p=>p.id);
        }
        const shown = shownIds.map(id => PRESETS.find(p=>p.id===id)).filter(Boolean);

        const grid = document.getElementById("sp-preset-grid");
        grid.innerHTML = shown.map(p => `
          <div class="preset-card" data-preset-id="${p.id}" role="button" tabindex="0">
            <div class="pc-icon">${p.icon}</div>
            <div class="pc-name">${escapeHtml(p.name)}</div>
            <div class="pc-desc">${escapeHtml(p.desc)}</div>
          </div>
        `).join("");
        grid.querySelectorAll(".preset-card").forEach(card => {
          card.addEventListener("click",    () => applyPreset(card.dataset.presetId));
          card.addEventListener("keydown",  e  => { if(e.key==="Enter"||e.key===" ") applyPreset(card.dataset.presetId); });
        });

        const lbl = document.getElementById("sp-count-label");
        if (lbl) lbl.textContent = isAll
          ? `${shown.length} / ${PRESETS.length} 表示中`
          : `${pool.length} プリセット`;
      }

      // ── カテゴリフィルター ────────────────────────────────────────────
      document.querySelectorAll(".sp-cat").forEach(btn => {
        btn.addEventListener("click", () => {
          document.querySelectorAll(".sp-cat").forEach(b=>b.classList.remove("active"));
          btn.classList.add("active");
          shownIds = [];
          renderGrid(btn.dataset.cat);
        });
      });

      // 🎲 再生成
      const btnShuffle = document.getElementById("btnShuffle");
      if (btnShuffle) {
        btnShuffle.addEventListener("click", () => {
          shownIds = [];
          renderGrid();
        });
      }

      // ── タブ切り替え ──────────────────────────────────────────────────
      document.querySelectorAll(".sp-tab").forEach(btn => {
        btn.addEventListener("click", () => {
          document.querySelectorAll(".sp-tab").forEach(b=>b.classList.remove("active"));
          document.querySelectorAll(".sp-pane").forEach(p=>p.classList.remove("active"));
          btn.classList.add("active");
          const pane = document.getElementById("sp-pane-"+btn.dataset.pane);
          if (pane) pane.classList.add("active");
        });
      });

      // ── トグル ────────────────────────────────────────────────────────
      toggle.addEventListener("click", () => {
        const isOpen = panel.classList.toggle("open");
        toggle.classList.toggle("open", isOpen);
        toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      });

      // ── Save ──────────────────────────────────────────────────────────
      document.getElementById("btnSettingsSave").addEventListener("click", () => {
        const s = getSettings();
        localStorage.setItem(LS_KEY, JSON.stringify(s));
        updateBadge(s);
        updateCharVisual(s, activeChars || [{body:"cas-m",faces:["neu","exc","thi"]},{body:"cas-f",faces:["neu","exc","thi"]}]);
        panel.classList.remove("open");
        toggle.classList.remove("open");
        toggle.setAttribute("aria-expanded","false");
      });

      // ── Reset ─────────────────────────────────────────────────────────
      document.getElementById("btnSettingsReset").addEventListener("click", () => {
        localStorage.removeItem(LS_KEY);
        document.querySelectorAll("#settingsPanel input,#settingsPanel textarea,#settingsPanel select")
          .forEach(el => { if(el.tagName==="SELECT") el.selectedIndex=0; else el.value=""; });
        updateBadge({});
        document.getElementById("charVisualSection").classList.remove("visible");
      });

      // グローバルに公開
      window.getCharSettings = getSettings;

      // ── 初期化 ────────────────────────────────────────────────────────
      try {
        const raw = localStorage.getItem(LS_KEY);
        if (raw) applySettings(JSON.parse(raw));
        else updateBadge({});
      } catch { updateBadge({}); }
      renderGrid();
      renderHistory();
      // 前回のキャラビジュアルを復元（Classic Labをデフォルト）
      const initPreset = PRESETS.find(p=>p.id==="sci1");
      if (initPreset) {
        try {
          const storedSettings = JSON.parse(localStorage.getItem(LS_KEY)||"null");
          updateCharVisual(storedSettings||initPreset.settings, initPreset.chars);
        } catch {}
      }
    })();

'''

result = content[:si] + NEW_BLOCK + content[ei:]
HTML.write_text(result, encoding="utf-8")
print(f"Done. File size: {len(result):,} bytes")
