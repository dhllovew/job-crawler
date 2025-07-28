import os
import time
import json
import logging
import smtplib
import base64
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from fake_useragent import UserAgent
import pandas as pd
from github import Github

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 配置常量
START_PAGE = 1
END_PAGE = 6
MAX_PAGES_PER_SESSION = 2
SITE_URL = "https://www.givemeoc.com"
WAIT_TIME_MIN = 1
WAIT_TIME_MAX = 3

# 从环境变量获取配置
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PWD = os.environ.get('EMAIL_PWD')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_NAME = os.environ.get('REPO_NAME')  # 格式: username/repository
DATA_FILE = "job_data.json"

def setup_browser():
    """配置浏览器（GitHub Actions专用）"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--incognito")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 随机User-Agent
    ua = UserAgent()
    chrome_options.add_argument(f"user-agent={ua.random}")
    
    # 创建浏览器实例
    driver = webdriver.Chrome(options=chrome_options)
    
    # 隐藏自动化特征
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    })
    
    return driver

def crawl_job_data(driver, start_page, end_page):
    """爬取指定页码范围的数据"""
    try:
        # 访问网站
        driver.get(SITE_URL)
        time.sleep(random.uniform(WAIT_TIME_MIN, WAIT_TIME_MAX))
        
        # 如果起始页不是第一页，跳转到指定页
        if start_page > 1:
            try:
                logger.info(f"跳转到第 {start_page} 页...")
                page_input = driver.find_element("css selector", "input.crt-page-input")
                page_input.clear()
                page_input.send_keys(str(start_page))

                go_button = driver.find_element("css selector", "button.crt-page-go-btn")
                driver.execute_script("arguments[0].click();", go_button)
                time.sleep(random.gauss(3, 1))
            except Exception as e:
                logger.error(f"跳转到第 {start_page} 页时出错: {e}")
                return [], start_page - 1

        crawled_data = []
        current_page = start_page

        # 爬取指定页数的数据
        for page in range(start_page, min(end_page + 1, start_page + MAX_PAGES_PER_SESSION)):
            logger.info(f"正在爬取第 {page} 页...")
            current_page = page

            # 模拟人类滚动
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))

            # 解析数据
            job_items = driver.find_elements("css selector", "table.crt-table tbody tr")

            for item in job_items:
                try:
                    company = safe_get_text(item, "td.crt-col-company")
                    company_type = safe_get_text(item, "td.crt-col-type")
                    location = safe_get_text(item, "td.crt-col-location")
                    recruitment_type = safe_get_text(item, "td.crt-col-recruitment-type")
                    target = safe_get_text(item, "td.crt-col-target")
                    position = safe_get_text(item, "td.crt-col-position")
                    update_time = safe_get_text(item, "td.crt-col-update-time")
                    deadline = safe_get_text(item, "td.crt-col-deadline")
                    links = safe_get_attr(item, "td.crt-col-links a", "href")
                    notice = safe_get_attr(item, "td.crt-col-notice a", "href")
                    referral = safe_get_text(item, "td.crt-col-referral")
                    notes = safe_get_text(item, "td.crt-col-notes")

                    crawled_data.append({
                        "company": company,
                        "company_type": company_type,
                        "location": location,
                        "recruitment_type": recruitment_type,
                        "target": target,
                        "position": position,
                        "update_time": update_time,
                        "deadline": deadline,
                        "links": links,
                        "notice": notice,
                        "referral": referral,
                        "notes": notes,
                        "crawl_time": datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.warning(f"处理行数据时出错: {e}")
                    continue

            # 翻页
            if page < min(end_page, start_page + MAX_PAGES_PER_SESSION - 1):
                try:
                    page_input = driver.find_element("css selector", "input.crt-page-input")
                    page_input.clear()
                    page_input.send_keys(str(page + 1))

                    go_button = driver.find_element("css selector", "button.crt-page-go-btn")
                    driver.execute_script("arguments[0].click();", go_button)
                    time.sleep(random.gauss(3, 1))
                    
                    # 更新User-Agent
                    new_ua = UserAgent().random
                    driver.execute_script(f"navigator.userAgent = '{new_ua}';")
                except Exception as e:
                    logger.warning(f"翻页时出错，可能已到达最后一页: {e}")
                    break

        return crawled_data, current_page
    except Exception as e:
        logger.error(f"爬取过程中发生错误: {e}")
        return [], start_page

def safe_get_text(element, selector):
    """安全获取元素文本"""
    try:
        return element.find_element("css selector", selector).text
    except:
        return ""

def safe_get_attr(element, selector, attribute):
    """安全获取元素属性"""
    try:
        return element.find_element("css selector", selector).get_attribute(attribute)
    except:
        return ""

def load_historical_data():
    """从GitHub仓库加载历史数据"""
    try:
        logger.info("从GitHub仓库加载历史数据...")
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(DATA_FILE)
        data = base64.b64decode(contents.content).decode('utf-8')
        return json.loads(data)
    except Exception as e:
        logger.warning(f"加载历史数据失败，创建新数据集: {str(e)}")
        return {
            "last_update": None,
            "jobs": {}
        }

def save_historical_data(data):
    """保存数据到GitHub仓库"""
    try:
        logger.info("保存数据到GitHub仓库...")
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # 尝试获取现有文件
        try:
            contents = repo.get_contents(DATA_FILE)
            repo.update_file(
                path=DATA_FILE,
                message=f"更新招聘数据 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                content=json.dumps(data, ensure_ascii=False, indent=2),
                sha=contents.sha
            )
        except:
            # 文件不存在则创建
            repo.create_file(
                path=DATA_FILE,
                message=f"创建招聘数据存储 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                content=json.dumps(data, ensure_ascii=False, indent=2)
            )
        return True
    except Exception as e:
        logger.error(f"保存数据到GitHub失败: {str(e)}")
        return False

def compare_jobs(new_jobs, historical_data):
    """对比新旧数据，识别新增和更新"""
    historical_jobs = historical_data.get("jobs", {})
    added = []
    updated = []
    
    # 创建唯一标识符：公司+岗位+截止日期
    for job in new_jobs:
        job_id = f"{job['company']}|{job['position']}|{job['deadline']}"
        
        if job_id not in historical_jobs:
            added.append(job)
            historical_jobs[job_id] = job
        else:
            # 检查是否有更新
            old_job = historical_jobs[job_id]
            changed = False
            
            # 检查关键字段是否有变化
            for key in ['position', 'deadline', 'links', 'notes', 'update_time']:
                if job.get(key) != old_job.get(key):
                    changed = True
                    break
            
            if changed:
                updated.append(job)
                historical_jobs[job_id] = job
    
    # 更新历史数据
    historical_data["jobs"] = historical_jobs
    historical_data["last_update"] = datetime.now().isoformat()
    
    return added, updated, historical_data, len(historical_jobs)

def clean_expired_jobs(historical_data):
    """清理过期职位"""
    logger.info("清理过期职位...")
    now = datetime.now()
    jobs = historical_data.get("jobs", {})
    cleaned_jobs = {}
    expired_count = 0
    
    for job_id, job in jobs.items():
        deadline_str = job.get("deadline", "")
        
        # 如果没有截止日期，保留
        if not deadline_str:
            cleaned_jobs[job_id] = job
            continue
            
        try:
            # 尝试解析日期 (格式如: 2023-12-31)
            deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d")
            if deadline_date > now:
                cleaned_jobs[job_id] = job
            else:
                expired_count += 1
        except:
            # 日期格式无法解析，保留
            cleaned_jobs[job_id] = job
    
    historical_data["jobs"] = cleaned_jobs
    logger.info(f"清理完成，移除了 {expired_count} 个过期职位")
    return historical_data, expired_count

def generate_html_report(all_jobs, added_jobs, updated_jobs, total_jobs, expired_count):
    """生成HTML格式的报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 创建HTML报告
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>招聘信息更新报告</title>
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                line-height: 1.6; 
                color: #333; 
                max-width: 1000px; 
                margin: 0 auto; 
                padding: 20px;
            }}
            .header {{ 
                background-color: #f0f8ff; 
                padding: 20px; 
                border-radius: 8px; 
                margin-bottom: 20px; 
                text-align: center;
            }}
            h1 {{ 
                color: #2c3e50; 
                margin-top: 0;
            }}
            .summary {{ 
                background-color: #e8f4f8; 
                padding: 15px; 
                border-radius: 8px; 
                margin-bottom: 25px;
            }}
            .summary-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
                margin-top: 10px;
            }}
            .summary-item {{
                background: white;
                padding: 10px;
                border-radius: 6px;
                text-align: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .summary-item .number {{
                font-size: 24px;
                font-weight: bold;
                display: block;
            }}
            .summary-item .label {{
                font-size: 14px;
                color: #666;
            }}
            .section-title {{
                background-color: #2c3e50;
                color: white;
                padding: 8px 15px;
                border-radius: 4px;
                margin-top: 25px;
                margin-bottom: 15px;
            }}
            .job-card {{
                background: white;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin-bottom: 15px;
                border-radius: 4px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            .job-card.new {{ border-left-color: #2ecc71; }}
            .job-card.updated {{ border-left-color: #f39c12; }}
            .company {{
                font-weight: bold;
                font-size: 18px;
                color: #2980b9;
                margin-bottom: 5px;
            }}
            .position {{
                font-style: italic;
                color: #7f8c8d;
                margin-bottom: 8px;
            }}
            .details {{
                display: grid;
                grid-template-columns: auto auto;
                gap: 10px;
                margin-bottom: 8px;
            }}
            .label {{
                font-weight: bold;
                color: #7f8c8d;
            }}
            .links a {{
                display: inline-block;
                background: #3498db;
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                text-decoration: none;
                margin-right: 10px;
                font-size: 14px;
            }}
            .links a:hover {{ background: #2980b9; }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                color: #7f8c8d;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>招聘信息更新报告</h1>
            <p>更新时间: {now}</p>
        </div>
        
        <div class="summary">
            <h2>数据概览</h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <span class="number">{len(all_jobs)}</span>
                    <span class="label">本次爬取职位</span>
                </div>
                <div class="summary-item">
                    <span class="number">{total_jobs}</span>
                    <span class="label">总职位数</span>
                </div>
                <div class="summary-item">
                    <span class="number">{len(added_jobs)}</span>
                    <span class="label">新增职位</span>
                </div>
                <div class="summary-item">
                    <span class="number">{len(updated_jobs)}</span>
                    <span class="label">更新职位</span>
                </div>
                <div class="summary-item">
                    <span class="number">{expired_count}</span>
                    <span class="label">过期职位</span>
                </div>
            </div>
        </div>
    """
    
    # 添加新增职位
    if added_jobs:
        html += """
        <div class="section-title">新增职位</div>
        """
        for job in added_jobs:
            html += f"""
            <div class="job-card new">
                <div class="company">{job['company']}</div>
                <div class="position">{job['position']}</div>
                <div class="details">
                    <div>
                        <span class="label">公司类型:</span> {job['company_type']}
                    </div>
                    <div>
                        <span class="label">工作地点:</span> {job['location']}
                    </div>
                    <div>
                        <span class="label">招聘类型:</span> {job['recruitment_type']}
                    </div>
                    <div>
                        <span class="label">招聘对象:</span> {job['target']}
                    </div>
                    <div>
                        <span class="label">更新时间:</span> {job['update_time']}
                    </div>
                    <div>
                        <span class="label">截止时间:</span> {job['deadline']}
                    </div>
                </div>
                <div class="links">
                    <a href="{job['links']}" target="_blank">投递链接</a>
                    <a href="{job['notice']}" target="_blank">公告详情</a>
                </div>
                <div class="notes">{job['notes']}</div>
            </div>
            """
    
    # 添加更新职位
    if updated_jobs:
        html += """
        <div class="section-title">更新职位</div>
        """
        for job in updated_jobs:
            html += f"""
            <div class="job-card updated">
                <div class="company">{job['company']}</div>
                <div class="position">{job['position']}</div>
                <div class="details">
                    <div>
                        <span class="label">公司类型:</span> {job['company_type']}
                    </div>
                    <div>
                        <span class="label">工作地点:</span> {job['location']}
                    </div>
                    <div>
                        <span class="label">招聘类型:</span> {job['recruitment_type']}
                    </div>
                    <div>
                        <span class="label">招聘对象:</span> {job['target']}
                    </div>
                    <div>
                        <span class="label">更新时间:</span> {job['update_time']}
                    </div>
                    <div>
                        <span class="label">截止时间:</span> {job['deadline']}
                    </div>
                </div>
                <div class="links">
                    <a href="{job['links']}" target="_blank">投递链接</a>
                    <a href="{job['notice']}" target="_blank">公告详情</a>
                </div>
                <div class="notes">{job['notes']}</div>
            </div>
            """
    
    html += """
        <div class="footer">
            <p>此邮件由自动爬虫系统生成，请勿直接回复</p>
            <p>© {} 招聘信息监控系统</p>
        </div>
    </body>
    </html>
    """.format(datetime.now().year)
    
    return html

def send_email(subject, html_content):
    """发送HTML格式的邮件"""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_USER  # 发送给自己
        msg['Subject'] = subject
        
        # 创建HTML邮件内容
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # 发送邮件
        server = smtplib.SMTP('smtp.qq.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PWD)
        server.send_message(msg)
        server.quit()
        logger.info("邮件发送成功")
        return True
    except Exception as e:
        logger.error(f"邮件发送失败: {str(e)}")
        return False

def main():
    """主程序"""
    logger.info(f"开始爬取招聘信息，时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 加载历史数据
    historical_data = load_historical_data()
    
    # 2. 爬取新数据
    all_jobs = []
    current_start_page = START_PAGE
    driver = setup_browser()
    
    # 循环爬取直到达到目标页数
    while current_start_page <= END_PAGE:
        logger.info(f"开始新的浏览器会话，从第 {current_start_page} 页开始爬取...")
        data, last_page = crawl_job_data(driver, current_start_page, END_PAGE)
        all_jobs.extend(data)
        logger.info(f"本次会话爬取了 {len(data)} 条数据")
        current_start_page = last_page + 1
        
        if current_start_page <= END_PAGE:
            logger.info("等待5秒后开始新的会话...")
            time.sleep(5)
    
    driver.quit()
    
    if not all_jobs:
        logger.error("没有爬取到任何数据")
        send_email("招聘信息爬取失败", "<h1>招聘信息爬取失败</h1><p>本次爬取未获取到任何数据</p>")
        return
    
    logger.info(f"共爬取 {len(all_jobs)} 条职位信息")
    
    # 3. 清理过期职位
    historical_data, expired_count = clean_expired_jobs(historical_data)
    
    # 4. 对比新旧数据
    added_jobs, updated_jobs, historical_data, total_jobs = compare_jobs(all_jobs, historical_data)
    
    logger.info(f"新增职位: {len(added_jobs)}, 更新职位: {len(updated_jobs)}, 总职位数: {total_jobs}")
    
    # 5. 保存更新后的数据
    save_success = save_historical_data(historical_data)
    
    # 6. 生成报告
    html_report = generate_html_report(all_jobs, added_jobs, updated_jobs, total_jobs, expired_count)
    
    # 7. 发送邮件
    subject = f"招聘信息更新报告 {datetime.now().strftime('%Y-%m-%d')}"
    if not send_email(subject, html_report):
        logger.error("邮件发送失败，但数据处理已完成")
    
    logger.info("处理完成!")

if __name__ == "__main__":
    main()
