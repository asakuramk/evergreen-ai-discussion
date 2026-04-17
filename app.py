import json
import os
import re
from datetime import datetime
from flask import Flask, render_template, Response, stream_with_context, request, jsonify
import requests

app = Flask(__name__)

OLLAMA_BASE = "http://localhost:11434"
OLLAMA_URL  = f"{OLLAMA_BASE}/api/chat"

PRESET_THEMES = [
    {
        "key": "evergreen",
        "name": "Project Evergreen",
        "desc": "24時間稼働AIシステムの立ち上げ",
        "agenda": [
            "プロジェクトのビジョンと目的",
            "アーキテクチャと技術的実現性",
            "開発フェーズとタイムライン",
            "コスト構造とROI予測",
            "リスク管理とガバナンス",
        ],
        "personas": [
            {"name": "AI研究者",       "desc": "技術的限界と学術知見から、AIの現実的な能力と将来性を客観的に評価する"},
            {"name": "現場オペレーター", "desc": "24時間稼働の運用現実を知り尽くし、人間が担うべき役割の重要性を強く訴える"},
            {"name": "消費者権利活動家", "desc": "ユーザーのプライバシー・安全・同意を最優先に考え、企業論理に対峙する"},
            {"name": "競合アナリスト",  "desc": "市場競争・差別化・ビジネスモデルの持続可能性を冷徹に分析する"},
        ],
        "moderator": {"name": "テクノロジー政策研究者", "desc": "技術と社会の接点を研究し、多角的な議論を整理する中立的ファシリテーター"},
    },
    {
        "key": "ai_ethics",
        "name": "AI倫理と規制",
        "desc": "AI導入における倫理・法規制の整備",
        "agenda": [
            "AIの意思決定の透明性",
            "プライバシーとデータ保護",
            "AI規制の国際標準化",
            "自律型AIのガバナンス",
            "AIと雇用の未来",
        ],
        "personas": [
            {"name": "哲学者・倫理学者",       "desc": "人間の尊厳・自由意志・価値観の根本から問い直し、技術決定論に警鐘を鳴らす"},
            {"name": "AIスタートアップCEO",     "desc": "イノベーションの自由を守る立場から、過剰規制がもたらす競争力低下を訴える"},
            {"name": "社会福祉士",             "desc": "AIの恩恵と弊害を社会的弱者・マイノリティの視点で捉え、格差拡大を危惧する"},
            {"name": "国際政策アナリスト",      "desc": "地政学的競争・国際標準・外交上の影響を分析し、国益の観点で規制を論じる"},
        ],
        "moderator": {"name": "国連AI倫理委員会アドバイザー", "desc": "各国の立場と利害を超えて議論を整理する国際的な中立ファシリテーター"},
    },
    {
        "key": "remote_work",
        "name": "リモートワーク戦略",
        "desc": "フルリモート移行の是非と施策",
        "agenda": [
            "生産性と管理の課題",
            "チームコミュニケーション",
            "オフィス縮小とコスト削減",
            "採用・人材確保への影響",
            "セキュリティとコンプライアンス",
        ],
        "personas": [
            {"name": "組織心理学者",       "desc": "孤独感・メンタルヘルス・チーム結束力を科学的エビデンスで分析する"},
            {"name": "不動産投資家",       "desc": "オフィス市場の崩壊・都市経済・資産価値への影響を数字で語る"},
            {"name": "子育て中の社員代表", "desc": "通勤ゼロの恩恵と自宅での集中困難、キャリア停滞の不安を生々しく語る"},
            {"name": "サイバーセキュリティ専門家", "desc": "リモート環境のVPN・エンドポイントリスクと現実的な対策コストを主張する"},
        ],
        "moderator": {"name": "働き方改革コンサルタント", "desc": "多様な立場の主張を実務的観点で整理し、組織変革への示唆を導くファシリテーター"},
    },
    {
        "key": "carbon_neutral",
        "name": "カーボンニュートラル",
        "desc": "2030年CO₂排出ゼロへの道筋",
        "agenda": [
            "現状の炭素排出量と削減目標",
            "再生可能エネルギーへの移行",
            "サプライチェーンの脱炭素化",
            "コストと投資回収",
            "社会・規制上のリスク",
        ],
        "personas": [
            {"name": "気候科学者",         "desc": "IPCCデータと気温上昇シナリオを根拠に、行動の緊急性を科学的に訴える"},
            {"name": "製造業の現場監督",   "desc": "脱炭素化コストと製造ラインへの実際的な打撃を、現場の声として伝える"},
            {"name": "グリーンテック投資家", "desc": "再エネ市場の爆発的成長機会とESGリターンの観点から移行を強く推進する"},
            {"name": "途上国支援NGO代表",  "desc": "先進国の脱炭素政策が途上国に与える不平等な負担と南北格差を告発する"},
        ],
        "moderator": {"name": "環境省政策立案者", "desc": "科学・経済・外交の三者を調停しながら実行可能な政策に落とし込むファシリテーター"},
    },
    {
        "key": "global_expansion",
        "name": "海外展開戦略",
        "desc": "東南アジア・欧米市場への進出計画",
        "agenda": [
            "ターゲット市場の選定",
            "現地化とプロダクト適応",
            "法規制・コンプライアンス",
            "組織体制と採用",
            "財務計画とリスク",
        ],
        "personas": [
            {"name": "現地文化研究者",  "desc": "文化的誤解・ローカライズの失敗事例を引き合いに、表面的な現地化の危険を警告する"},
            {"name": "帰国子女エンジニア", "desc": "現地と本社のギャップ・技術スタックの現実・採用市場の厳しさを両者の目線で語る"},
            {"name": "国際法律家",      "desc": "現地の知的財産権・労働法・データ規制の複雑さと違反リスクを具体的に警告する"},
            {"name": "M&A専門家",       "desc": "有機的成長 vs 買収戦略の優劣・Exit設計・株主価値の最大化を財務的に論じる"},
        ],
        "moderator": {"name": "グローバルビジネス戦略顧問", "desc": "各国進出の成功・失敗事例を踏まえ、議論を実行可能な戦略に絞り込むファシリテーター"},
    },
]


def ask_gemma(system_prompt, user_prompt, model=None):
    payload = {
        "model": model or "gemma4:e2b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
        return r.json()['message']['content']
    except Exception as e:
        return f"（応答なし: {e}）"


def parse_list(text, key=None):
    """Extract a JSON array (optionally under a key) or fall back to line parsing."""
    if key:
        # Try {"key": [...]}
        match = re.search(rf'"{key}"\s*:\s*(\[.*?\])', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    match = re.search(r'\[.*?\]', text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except Exception:
            pass
    items = re.findall(r'(?:^|\n)\s*\d+[\.\)、]\s*(.+)', text)
    if items:
        return [i.strip().strip('"').strip('「').strip('」') for i in items]
    lines = [l.strip().lstrip('-・*#').strip('"').strip('「').strip('」').strip()
             for l in text.splitlines() if l.strip()]
    return [l for l in lines if 4 < len(l) < 80]


def parse_personas(text):
    items = parse_list(text, key='personas') or parse_list(text)
    result = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get('name', item.get('role', item.get('title', '')))).strip()
            desc = str(item.get('desc', item.get('description', item.get('perspective', '')))).strip()
            if name and desc:
                result.append({"name": name[:30], "desc": desc[:120]})
        elif isinstance(item, str) and '：' in item:
            parts = item.split('：', 1)
            result.append({"name": parts[0].strip()[:30], "desc": parts[1].strip()[:120]})
    return result[:4]


def sse(event_type, **kwargs):
    data = json.dumps({"type": event_type, **kwargs}, ensure_ascii=False)
    return f"data: {data}\n\n"


@app.route('/models')
def list_models():
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        r.raise_for_status()
        names = [m['name'] for m in r.json().get('models', [])]
        return jsonify({"models": names})
    except Exception as e:
        return jsonify({"models": [], "error": str(e)})


@app.route('/')
def index():
    return render_template('index.html', presets=PRESET_THEMES)


@app.route('/setup')
def setup():
    """Generate agenda + 4 personas + moderator for a custom theme."""
    theme = request.args.get('theme', '').strip()
    model = request.args.get('model', '').strip() or None
    if not theme:
        return jsonify({"error": "theme is required"}), 400

    agenda_raw = ask_gemma(
        "あなたは企業の議論ファシリテーターです。",
        f'テーマ「{theme}」について経営会議で議論すべき重要な議題を5つ生成してください。'
        f'各議題は15〜25文字の簡潔な名詞句で。必ずJSON配列で返してください: ["議題1","議題2","議題3","議題4","議題5"]',
        model=model,
    )
    agenda = [str(i).strip() for i in (parse_list(agenda_raw) or []) if str(i).strip()]
    if not agenda:
        agenda = [f"{theme}の現状分析", f"{theme}の課題整理", f"{theme}の実行計画",
                  f"{theme}のコストと効果", f"{theme}のリスクと対策"]

    personas_raw = ask_gemma(
        "あなたは議論設計の専門家です。",
        f'テーマ「{theme}」について、全く異なる4つの立場・角度から議論できる論客を設定してください。'
        f'職業・価値観・利害関係がそれぞれ正反対になるよう工夫してください。'
        f'必ずJSON配列で返してください（日本語で）:\n'
        f'[{{"name":"役職や肩書き","desc":"この人物の視点・価値観・議論スタンス（40〜60文字）"}},'
        f' {{"name":"...","desc":"..."}},'
        f' {{"name":"...","desc":"..."}},'
        f' {{"name":"...","desc":"..."}}]',
        model=model,
    )
    personas = parse_personas(personas_raw)
    if len(personas) < 4:
        fallbacks = [
            {"name": "推進派リーダー",   "desc": f"{theme}を積極推進する立場。メリットと可能性を強調する"},
            {"name": "懐疑的専門家",     "desc": f"{theme}のリスクと課題を客観的データで指摘する"},
            {"name": "現場の実務者",     "desc": f"{theme}の現場実態を語り、理想論と現実のギャップを訴える"},
            {"name": "社会的影響の代弁者", "desc": f"{theme}が社会・コミュニティに与える影響を当事者視点で語る"},
        ]
        for fb in fallbacks[len(personas):4]:
            personas.append(fb)

    moderator_raw = ask_gemma(
        "あなたは議論設計の専門家です。",
        f'テーマ「{theme}」の議論をまとめる中立的なモデレーターを1名設定してください。'
        f'このテーマに精通した専門家でありながら中立的な立場の人物で。'
        f'必ずJSON形式で返してください: {{"name":"役職や肩書き","desc":"この人物の特徴（30〜50文字）"}}',
        model=model,
    )
    mod_match = re.search(r'\{[^{}]+\}', moderator_raw, re.DOTALL)
    moderator = {"name": "モデレーター", "desc": "中立的な立場で議論を整理し合意形成を促すファシリテーター"}
    if mod_match:
        try:
            m = json.loads(mod_match.group())
            if isinstance(m, dict) and m.get('name'):
                moderator = {"name": str(m['name'])[:40], "desc": str(m.get('desc', ''))[:100]}
        except Exception:
            pass

    return jsonify({"agenda": agenda, "personas": personas, "moderator": moderator})


@app.route('/run_discussion')
def run_discussion():
    theme_name = request.args.get('theme_name', '議論')
    model = request.args.get('model', '').strip() or None
    rounds = max(1, min(int(request.args.get('rounds', 10)), 20))
    try:
        agenda = json.loads(request.args.get('agenda', '[]'))
        personas = json.loads(request.args.get('personas', '[]'))
        moderator = json.loads(request.args.get('moderator', '{}'))
    except Exception:
        agenda, personas, moderator = [], [], {}

    if not agenda:
        return Response(sse("error", message="議題が選択されていません"), mimetype='text/event-stream')
    if not personas:
        return Response(sse("error", message="ペルソナが設定されていません"), mimetype='text/event-stream')

    mod_name = moderator.get('name', 'モデレーター')
    mod_desc = moderator.get('desc', '中立的な立場で議論を整理するファシリテーター')

    def generate():
        final_report = []

        for agenda_idx, item in enumerate(agenda):
            yield sse("agenda_start", index=agenda_idx + 1, total=len(agenda), item=item)
            discussion_history = []

            for round_num in range(1, rounds + 1):
                yield sse("round_start", round=round_num, total_rounds=rounds)

                for persona in personas:
                    role = persona['name']
                    desc = persona['desc']
                    others = [p['name'] for p in personas if p['name'] != role]

                    yield sse("thinking", speaker=role, round=round_num)

                    if round_num == 1:
                        system_prompt = (
                            f"あなたは{role}です。{desc}\n"
                            f"テーマ「{theme_name}」の議題「{item}」について、"
                            f"あなた独自の立場・価値観からの主張を150文字程度で述べてください。"
                            f"他の参加者とは全く異なる角度から発言してください。"
                        )
                        user_prompt = f"議題「{item}」についてあなたの立場から発言してください。"
                    else:
                        history_text = "\n".join(
                            f"[R{e['round']} {e['speaker']}]: {e['response']}"
                            for e in discussion_history
                        )
                        system_prompt = (
                            f"あなたは{role}です。{desc}\n"
                            f"第{round_num}ラウンドです。特に{', '.join(others[:2])}の発言に対して、"
                            f"相手の名前を出しながら具体的に反論・同意・補足をしてください。"
                            f"抽象論ではなく具体的な数字・事例・経験を引いて150文字程度で述べてください。"
                        )
                        user_prompt = f"これまでの議論:\n{history_text}\n\nあなたの発言:"

                    response = ask_gemma(system_prompt, user_prompt, model=model)
                    discussion_history.append({"round": round_num, "speaker": role, "response": response})
                    yield sse("message", item=item, speaker=role, response=response, round=round_num)

            yield sse("summarizing", item=item)
            history_text = "\n".join(
                f"[R{e['round']} {e['speaker']}]: {e['response']}"
                for e in discussion_history
            )
            summary = ask_gemma(
                f"あなたは{mod_name}です。{mod_desc}\n"
                f"議論を整理し、合意点・対立点・次のアクションを簡潔にまとめてください。",
                f"議題「{item}」の議論:\n{history_text}\n\nまとめ:",
                model=model,
            )
            yield sse("summary", item=item, summary=summary)
            final_report.append(f"議題: {item}\n結果: {summary}")

        yield sse("concluding")
        full_prompt = (
            "以下の各議題の議論結果を統合し、プロジェクトの最終意思決定案と優先アクションを作成してください:\n\n"
            + "\n\n".join(final_report)
        )
        conclusion = ask_gemma(
            f"あなたは{mod_name}です。{mod_desc}\n全議論を統合し、明確な意思決定と次のステップを示してください。",
            full_prompt,
            model=model,
        )
        yield sse("conclusion", text=conclusion)
        yield sse("done")

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route('/save', methods=['POST'])
def save_report():
    data = request.get_json()
    theme_name   = data.get('theme_name', '議論')
    model        = data.get('model', '')
    personas     = data.get('personas', [])
    moderator    = data.get('moderator', {})
    agenda_results = data.get('agenda_results', [])
    conclusion   = data.get('conclusion', '')

    # AI でタイトル生成
    summary_for_title = "\n".join(
        f"- {r['item']}: {r['summary']}" for r in agenda_results if r.get('summary')
    )
    raw_title = ask_gemma(
        "あなたは優秀なライターです。議論の内容を端的に表す日本語タイトルを1行だけ出力してください。",
        f"テーマ「{theme_name}」の議論要約:\n{summary_for_title}\n\n結論:\n{conclusion}\n\nタイトル:",
        model=model or None,
    )
    title = raw_title.strip().strip('#').strip('"').strip('「').strip('」').split('\n')[0].strip()
    if not title:
        title = theme_name

    # Markdown 生成
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f"# {title}",
        f"",
        f"**テーマ:** {theme_name}　**日時:** {now}　**モデル:** {model}",
        f"",
        f"**論客:** {' / '.join(p['name'] for p in personas)}",
        f"**まとめ役:** {moderator.get('name', 'モデレーター')}",
        f"",
        f"---",
        f"",
    ]

    for result in agenda_results:
        lines.append(f"## 議題：{result['item']}")
        lines.append("")
        last_round = None
        for msg in result.get('messages', []):
            if msg['round'] != last_round:
                last_round = msg['round']
                lines.append(f"### Round {msg['round']}")
                lines.append("")
            lines.append(f"**{msg['speaker']}：** {msg['response']}")
            lines.append("")
        if result.get('summary'):
            lines.append(f"#### まとめ（{moderator.get('name', 'モデレーター')}）")
            lines.append("")
            lines.append(result['summary'])
            lines.append("")
        lines.append("---")
        lines.append("")

    if conclusion:
        lines.append(f"## 最終結論（{moderator.get('name', 'モデレーター')}）")
        lines.append("")
        lines.append(conclusion)
        lines.append("")

    content = "\n".join(lines)

    # ファイル保存
    reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M')}_{safe_title}.md"
    filepath = os.path.join(reports_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return jsonify({"filename": filename, "filepath": filepath, "title": title})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
