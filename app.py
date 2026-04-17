import json
from flask import Flask, render_template, Response, stream_with_context, request
import requests

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gemma4:e2b"

THEMES = {
    "evergreen": {
        "name": "Project Evergreen（24時間稼働AIシステム）",
        "agenda": [
            "プロジェクトのビジョンと目的",
            "アーキテクチャと技術的実現性",
            "開発フェーズとタイムライン",
            "コスト構造とROI予測",
            "リスク管理とガバナンス",
        ]
    },
    "ai_ethics": {
        "name": "AI倫理と規制",
        "agenda": [
            "AIの意思決定の透明性",
            "プライバシーとデータ保護",
            "AI規制の国際標準化",
            "自律型AIのガバナンス",
            "AIと雇用の未来",
        ]
    },
    "remote_work": {
        "name": "リモートワーク戦略",
        "agenda": [
            "生産性と管理の課題",
            "チームコミュニケーション",
            "オフィス縮小とコスト削減",
            "採用・人材確保への影響",
            "セキュリティとコンプライアンス",
        ]
    },
    "carbon_neutral": {
        "name": "2030年カーボンニュートラル",
        "agenda": [
            "現状の炭素排出量と削減目標",
            "再生可能エネルギーへの移行",
            "サプライチェーンの脱炭素化",
            "コストと投資回収",
            "社会・規制上のリスク",
        ]
    },
    "global_expansion": {
        "name": "海外展開戦略",
        "agenda": [
            "ターゲット市場の選定",
            "現地化とプロダクト適応",
            "法規制・コンプライアンス",
            "組織体制と採用",
            "財務計画とリスク",
        ]
    },
}

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


def sse(event_type, **kwargs):
    data = json.dumps({"type": event_type, **kwargs}, ensure_ascii=False)
    return f"data: {data}\n\n"


@app.route('/')
def index():
    themes_info = {k: v['name'] for k, v in THEMES.items()}
    themes_agenda = {k: v['agenda'] for k, v in THEMES.items()}
    return render_template('index.html', themes=themes_info, themes_agenda=themes_agenda)


@app.route('/run_discussion')
def run_discussion():
    theme_key = request.args.get('theme', 'evergreen')
    rounds = max(1, min(int(request.args.get('rounds', 10)), 20))
    item_indices_raw = request.args.get('items', '')

    theme = THEMES.get(theme_key, THEMES['evergreen'])
    all_agenda = theme['agenda']

    if item_indices_raw:
        indices = [int(i) for i in item_indices_raw.split(',') if i.isdigit() and int(i) < len(all_agenda)]
        agenda = [all_agenda[i] for i in indices] if indices else all_agenda
    else:
        agenda = all_agenda

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
                            f"議題「{item}」について、あなたの立場から明確な主張を150文字程度で述べてください。"
                        )
                        user_prompt = f"議題「{item}」についてあなたの立場から発言してください。"
                    else:
                        history_text = "\n".join(
                            f"[R{e['round']} {e['speaker']}]: {e['response']}" for e in discussion_history
                        )
                        system_prompt = (
                            f"あなたは{role}です。{desc}\n"
                            f"これは第{round_num}ラウンドです。{', '.join(others)}の発言に具体的に反応し、"
                            f"賛成・反論・補足のいずれかをあなたの立場から鋭く150文字程度で述べてください。"
                            f"相手の名前を出して具体的に議論してください。"
                        )
                        user_prompt = f"これまでの議論:\n{history_text}\n\nあなたの発言:"

                    response = ask_gemma(system_prompt, user_prompt)
                    discussion_history.append({"round": round_num, "speaker": role, "response": response})
                    yield sse("message", item=item, speaker=role, response=response, round=round_num)

            yield sse("summarizing", item=item)
            history_text = "\n".join(
                f"[R{e['round']} {e['speaker']}]: {e['response']}" for e in discussion_history
            )
            summary = ask_gemma(
                "あなたは中立的なモデレーターです。議論を整理し合意点・対立点・結論を簡潔にまとめてください。",
                f"議題「{item}」の議論:\n{history_text}\n\nまとめ:"
            )
            yield sse("summary", item=item, summary=summary)
            final_report.append(f"議題: {item}\n結果: {summary}")

        yield sse("concluding")
        full_prompt = "以下の各議題の議論結果を統合し、プロジェクトの最終意思決定案を作成してください:\n\n" + "\n\n".join(final_report)
        conclusion = ask_gemma(
            "あなたはCEOです。全議論を踏まえ、プロジェクトの最終判断を下してください。",
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
