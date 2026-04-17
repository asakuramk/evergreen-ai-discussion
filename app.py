import json
import re
from flask import Flask, render_template, Response, stream_with_context, request, jsonify
import requests

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gemma4:e2b"

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
        ]
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
        ]
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
        ]
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
        ]
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
        ]
    },
]

ROLES = {
    "プロダクトオーナー": "全体最適とユーザー価値を重視。議論を前に進める立場。",
    "CTO": "技術的限界と実現性を重視。最新技術のポテンシャルを高く評価している。",
    "CFO": "コスト、ROI、リソース配分を重視。無駄な投資には極めて批判的。",
    "リスクマネジメント": "セキュリティ、プライバシー、法規制、レピュテーションリスクを重視。",
}


def ask_gemma(system_prompt, user_prompt):
    payload = {
        "model": MODEL_NAME,
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


def parse_agenda(text):
    match = re.search(r'\[.*?\]', text, re.DOTALL)
    if match:
        try:
            items = json.loads(match.group())
            if isinstance(items, list):
                return [str(i).strip() for i in items if str(i).strip()]
        except Exception:
            pass
    items = re.findall(r'(?:^|\n)\s*\d+[\.\)、]\s*(.+)', text)
    if items:
        return [i.strip().strip('"').strip('「').strip('」') for i in items[:7]]
    lines = [l.strip().lstrip('-・*#').strip('"').strip('「').strip('」').strip()
             for l in text.splitlines() if l.strip()]
    return [l for l in lines if 4 < len(l) < 60][:7]


def sse(event_type, **kwargs):
    data = json.dumps({"type": event_type, **kwargs}, ensure_ascii=False)
    return f"data: {data}\n\n"


@app.route('/')
def index():
    return render_template('index.html', presets=PRESET_THEMES)


@app.route('/generate_agenda')
def generate_agenda():
    theme = request.args.get('theme', '').strip()
    if not theme:
        return jsonify({"error": "theme is required"}), 400

    raw = ask_gemma(
        "あなたは企業の議論ファシリテーターです。指定されたテーマに対して、経営層が議論すべき重要な議題を5つ生成してください。",
        f'テーマ「{theme}」について、経営会議で議論すべき議題を5つ生成してください。'
        f'各議題は15〜25文字の簡潔な名詞句で。必ずJSON配列形式で返してください: ["議題1", "議題2", "議題3", "議題4", "議題5"]'
    )
    agenda = parse_agenda(raw)
    if not agenda:
        agenda = [f"{theme}の現状分析", f"{theme}の課題整理", f"{theme}の実行計画",
                  f"{theme}のコストと効果", f"{theme}のリスクと対策"]
    return jsonify({"agenda": agenda})


@app.route('/run_discussion')
def run_discussion():
    theme_name = request.args.get('theme_name', '議論')
    rounds = max(1, min(int(request.args.get('rounds', 10)), 20))
    try:
        agenda = json.loads(request.args.get('agenda', '[]'))
    except Exception:
        agenda = []

    if not agenda:
        return Response(sse("error", message="議題が選択されていません"), mimetype='text/event-stream')

    role_names = list(ROLES.keys())

    def generate():
        final_report = []

        for agenda_idx, item in enumerate(agenda):
            yield sse("agenda_start", index=agenda_idx + 1, total=len(agenda), item=item)

            discussion_history = []

            for round_num in range(1, rounds + 1):
                yield sse("round_start", round=round_num, total_rounds=rounds)

                for role, desc in ROLES.items():
                    yield sse("thinking", speaker=role, round=round_num)

                    others = [r for r in role_names if r != role]

                    if round_num == 1:
                        system_prompt = (
                            f"あなたは{role}です。{desc}\n"
                            f"テーマ「{theme_name}」の議題「{item}」について、"
                            f"あなたの立場からの主張を150文字程度で述べてください。"
                        )
                        user_prompt = f"議題「{item}」についてあなたの立場から発言してください。"
                    else:
                        history_text = "\n".join(
                            f"[R{e['round']} {e['speaker']}]: {e['response']}"
                            for e in discussion_history
                        )
                        system_prompt = (
                            f"あなたは{role}です。{desc}\n"
                            f"第{round_num}ラウンドです。{', '.join(others)}の具体的な発言内容に対して、"
                            f"相手の名前を出しながら反論・同意・補足をあなたの立場から150文字程度で述べてください。"
                            f"抽象論ではなく具体的な数字・事例・懸念点を挙げてください。"
                        )
                        user_prompt = f"これまでの議論:\n{history_text}\n\nあなたの発言:"

                    response = ask_gemma(system_prompt, user_prompt)
                    discussion_history.append({"round": round_num, "speaker": role, "response": response})
                    yield sse("message", item=item, speaker=role, response=response, round=round_num)

            yield sse("summarizing", item=item)
            history_text = "\n".join(
                f"[R{e['round']} {e['speaker']}]: {e['response']}"
                for e in discussion_history
            )
            summary = ask_gemma(
                "あなたは中立的なモデレーターです。議論を整理し、合意点・対立点・次のアクションを簡潔にまとめてください。",
                f"議題「{item}」の議論:\n{history_text}\n\nまとめ:"
            )
            yield sse("summary", item=item, summary=summary)
            final_report.append(f"議題: {item}\n結果: {summary}")

        yield sse("concluding")
        full_prompt = (
            "以下の各議題の議論結果を統合し、プロジェクトの最終意思決定案と優先アクションを作成してください:\n\n"
            + "\n\n".join(final_report)
        )
        conclusion = ask_gemma(
            "あなたはCEOです。全議論を踏まえ、明確な意思決定と次のステップを示してください。",
            full_prompt
        )
        yield sse("conclusion", text=conclusion)
        yield sse("done")

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000)
