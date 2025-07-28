#用户管理模块
import os
import json
import logging
import secrets
import requests
from datetime import datetime

# 配置日志
logger = logging.getLogger('user_manager')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# 用户数据文件路径
USERS_FILE = "users.json"
ISSUES_FILE = "pending_registrations.json"

# 从环境变量获取配置
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_NAME = os.environ.get('REPO_NAME', 'your-username/your-repo')

def load_users():
    """加载用户数据"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        return {"verified_users": {}, "pending_verification": {}}
    except Exception as e:
        logger.error(f"加载用户数据失败: {str(e)}")
        return {"verified_users": {}, "pending_verification": {}}

def save_users(users):
    """保存用户数据"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存用户数据失败: {str(e)}")
        return False

def load_pending_issues():
    """加载待处理注册请求"""
    try:
        if os.path.exists(ISSUES_FILE):
            with open(ISSUES_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"加载待处理注册请求失败: {str(e)}")
        return {}

def save_pending_issues(issues):
    """保存待处理注册请求"""
    try:
        with open(ISSUES_FILE, 'w') as f:
            json.dump(issues, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存待处理注册请求失败: {str(e)}")
        return False

def fetch_new_registrations():
    """从GitHub Issues获取新注册请求"""
    try:
        url = f"https://api.github.com/repos/{REPO_NAME}/issues?state=open&labels=registration"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"获取GitHub Issues失败: {response.status_code}")
            return {}
        
        registrations = {}
        for issue in response.json():
            if "新用户注册" in issue['title']:
                email = issue['title'].split(":")[1].strip()
                issue_id = issue['id']
                created_at = issue['created_at']
                registrations[email] = {
                    "issue_id": issue_id,
                    "created_at": created_at,
                    "verified": False
                }
        
        return registrations
    except Exception as e:
        logger.error(f"获取新注册请求失败: {str(e)}")
        return {}

def create_verification_token(email):
    """创建验证token"""
    return secrets.token_urlsafe(32)

def create_user_directory(email):
    """创建用户数据目录"""
    user_dir = f"user_data/{email}"
    os.makedirs(user_dir, exist_ok=True)
    
    # 初始化用户数据文件
    user_data_file = f"{user_dir}/user_data.json"
    if not os.path.exists(user_data_file):
        with open(user_data_file, 'w') as f:
            json.dump({
                "email": email,
                "created_at": datetime.now().isoformat(),
                "last_login": None,
                "preferences": {
                    "keywords": [],
                    "locations": [],
                    "notification_freq": "daily"
                },
                "job_data": {}
            }, f)
    
    return user_dir

def mark_issue_as_verified(issue_id):
    """在GitHub上标记issue为已验证"""
    try:
        url = f"https://api.github.com/repos/{REPO_NAME}/issues/{issue_id}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "state": "closed",
            "labels": ["verified"],
            "body": f"已验证用户 - {datetime.now().isoformat()}"
        }
        
        response = requests.patch(url, headers=headers, json=data)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"标记issue为已验证失败: {str(e)}")
        return False
