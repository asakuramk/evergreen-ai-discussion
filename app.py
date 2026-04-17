import requests
import json

# --- 設定 ---
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gemma4:e2b"

# アジェンダ定義
AGENDA = [
    "プロジェクトのビジョンと目的 (24時間稼働の定義)",
    "アーキテクチャと技術的実現性 (e2bモデルの活用)",
    "開発フェーズとタイムライン",
    "コスト構造とROI予測",
    "リスク管理とガバナンス"
]

# 論客のペルソナ
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
        r = requests.post(OLLAMA_URL, json=payload)
        r.raise_for_status()
        return r.json()['message']['content']
    except:
        return "（沈黙: API接続を確認してください）"

def summarize(history):
    prompt = f"以下の議論を要約し、次のステップへの合意事項を抽出してください:\n\n{history}"
    return ask_gemma("モデレーター", "中立的な立場の議事録作成者", prompt)

# --- 実行プロセス ---
final_report = []

print(f"### Project 'Evergreen' 議論開始 (Model: {MODEL_NAME}) ###\n")

for i, item in enumerate(AGENDA, 1):
    print(f"【ステップ {i}: {item}】")
    discussion_history = ""
    
    # 各ロールが発言
    for role, desc in ROLES.items():
        response = ask_gemma(role, desc, f"議題「{item}」について発言してください。\nこれまでの議論: {discussion_history}")
        print(f"[{role}]: {response}")
        discussion_history += f"{role}: {response}\n"
    
    # 中間まとめ
    summary = summarize(discussion_history)
    print(f"\n> 中間まとめ: {summary}\n" + "-"*50 + "\n")
    final_report.append(f"議題: {item}\n結果: {summary}")

# 最終統合
full_summary_prompt = "以下の各議題の合意事項を統合し、プロジェクトの最終意思決定案を作成してください:\n\n" + "\n".join(final_report)
total_conclusion = ask_gemma("総括責任者", "プロジェクトの最終判断を下すCEO", full_summary_prompt)

print("### 総合まとめ ###")
print(total_conclusion)