import requests
import time

BASE_URL = "http://localhost:8000"


def test_all():
    print("🚀 开始测试供应链知识图谱多智能体系统...\n")

    # 1. 根路径测试
    print("1️⃣ 测试根路径...")
    resp = requests.get(f"{BASE_URL}/")
    print(f"   状态: {resp.status_code}, 系统: {resp.json().get('name')}\n")

    # 2. 健康检查
    print("2️⃣ 健康检查...")
    resp = requests.get(f"{BASE_URL}/api/chat/health")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   状态: {data['status']}")
        print(f"   智能体: {data['agents']}\n")
    else:
        print(f"   失败: {resp.status_code}\n")

    # 3. 聊天测试
    print("3️⃣ 测试聊天接口...")
    test_questions = [
        "查询所有物料",
        "分析供应风险"
    ]

    for q in test_questions:
        print(f"   问题: {q}")
        try:
            resp = requests.post(
                f"{BASE_URL}/api/chat/sync",
                json={"question": q, "session_id": "test"},
                timeout=30
            )
            if resp.status_code == 200:
                answer = resp.json().get('answer', '')[:100]
                print(f"   回答: {answer}...")
            else:
                print(f"   错误: {resp.status_code}")
        except Exception as e:
            print(f"   异常: {str(e)}")
        print()

    print("✅ 测试完成！")


if __name__ == "__main__":
    test_all()