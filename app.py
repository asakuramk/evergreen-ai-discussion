import json
from flask import Flask, render_template, Response, stream_with_context
import requests

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gemma4:e2b"

AGENDA = [
    "プロジェクトのビジョンと目的 (24時間稼働の定義)",
    "アーキテクチャと技術的実現性 (e2bモデルの活用)",
    "開発フェーズとタイムライン",
    "コスト構造とROI予測",
    "リスク管理とガバナンス"
]

ROLES = {
    "プロダクトオーナー": "全体最適とユーザー価値を重視。議論を前に進める立場。",
    "CTO": "技術的限界と実現性を重視。Gemma 4:e2bの推論能力を高く評価している。",
    "CFO": "コスト、ROI、リソース配分を重視。無駄な投資には極めて批判的。",
    "リスクマネジメント": "セキュリティ、プライバシー、AIの暴走、法規制を重視。"
}


def ask_gemma(role_name, role_desc, prompt):
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": f"あなたは{role_name}です。{role_desc} 議論履歴を踏まえ、100文字程度で鋭く発言してください。"},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
        return r.json()['message']['content']
    except Exception as e:
        return f"（沈黙: {e}）"


def sse(event_type, **kwargs):
    data = json.dumps({"type": event_type, **kwargs}, ensure_ascii=False)
    return f"data: {data}\n\n"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run_discussion', methods=['GET'])
def run_discussion():
    def generate():
        final_report = []

        for i, item in enumerate(AGENDA, 1):
            yield sse("agenda_start", index=i, item=item)
            discussion_history = ""

            for role, desc in ROLES.items():
                yield sse("thinking", speaker=role)
                response = ask_gemma(
                    role, desc,
                    f"議題「{item}」について発言してください。\nこれまでの議論: {discussion_history}"
                )
                yield sse("message", step=item, speaker=role, response=response)
                discussion_history += f"{role}: {response}\n"

            yield sse("summarizing")
            summary = ask_gemma("モデレーター", "中立的な立場の議事録作成者",
                                f"以下の議論を要約し、合意事項を抽出してください:\n\n{discussion_history}")
            yield sse("summary", item=item, summary=summary)
            final_report.append(f"議題: {item}\n結果: {summary}")

        yield sse("concluding")
        full_prompt = "以下の各議題の合意事項を統合し、プロジェクトの最終意思決定案を作成してください:\n\n" + "\n".join(final_report)
        conclusion = ask_gemma("総括責任者", "プロジェクトの最終判断を下すCEO", full_prompt)
        yield sse("conclusion", text=conclusion)
        yield sse("done")

    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
