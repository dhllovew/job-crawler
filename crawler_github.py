import os
import time
import json
import logging
import smtplib
import base64
import random
import re
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from fake_useragent import UserAgent
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
    
    # 关键修复：明确指定Chromium路径
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    
    # 随机User-Agent
    ua = UserAgent()
    chrome_options.add_argument(f"user-agent={ua.random}")
    
    # 创建浏览器实例
    driver = webdriver.Chrome(options=chrome_options)
    
    # 隐藏自动化特征
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    })
    
    logger.info(f"浏览器初始化完成，使用路径: {chrome_options.binary_location}")
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
        # 更友好的首次运行提示
        if "404" in str(e):
            logger.info("首次运行：尚未找到历史数据文件，将创建新数据集")
        else:
            logger.warning(f"加载历史数据失败: {str(e)}，将创建新数据集")
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
            
            logger.info(f"已创建新的数据文件: {DATA_FILE}")
        return True
    except Exception as e:
        logger.error(f"保存数据到GitHub失败: {str(e)}")
        return False

def clean_expired_jobs(historical_data):
    """清理过期职位（假设历史数据中的每个职位都有deadline字段）"""
    logger.info("开始清理过期职位...")
    current_time = datetime.now()
    expired_count = 0
    # 遍历历史数据中的职位
    for job_id, job in list(historical_data['jobs'].items()):
        # 如果deadline存在且已过期
        if job.get('deadline'):
            # 尝试解析deadline字符串为日期对象
            try:
                # 假设deadline格式为"YYYY-MM-DD"
                deadline_date = datetime.strptime(job['deadline'], '%Y-%m-%d')
                if deadline_date < current_time:
                    del historical_data['jobs'][job_id]
                    expired_count += 1
            except ValueError:
                # 如果解析失败，尝试其他格式
                try:
                    # 尝试匹配"X天前"格式
                    match = re.search(r'(\d+)天前', job['deadline'])
                    if match:
                        days_ago = int(match.group(1))
                        deadline_date = current_time - timedelta(days=days_ago)
                        if deadline_date < current_time:
                            del historical_data['jobs'][job_id]
                            expired_count += 1
                    else:
                        # 无法解析的格式，保留职位
                        pass
                except Exception as e:
                    logger.warning(f"解析deadline失败: {job['deadline']} - {str(e)}")
    
    logger.info(f"清理完成，移除了 {expired_count} 个过期职位")
    return historical_data, expired_count

def compare_jobs(new_jobs, historical_data):
    """比较新旧职位数据，识别新增和更新的职位"""
    logger.info("比较新旧职位数据...")
    added_jobs = []
    updated_jobs = []
    total_jobs = 0
    
    # 创建职位唯一标识符的函数
    def create_job_id(job):
        """创建职位的唯一标识符"""
        return f"{job['company']}-{job['position']}-{job['update_time']}"
    
    # 处理新爬取的职位
    for job in new_jobs:
        job_id = create_job_id(job)
        
        if job_id not in historical_data['jobs']:
            # 新增职位
            historical_data['jobs'][job_id] = job
            added_jobs.append(job)
        else:
            # 检查职位是否有更新
            existing_job = historical_data['jobs'][job_id]
            if existing_job['update_time'] != job['update_time']:
                # 更新职位信息
                historical_data['jobs'][job_id] = job
                updated_jobs.append(job)
    
    # 更新最后爬取时间
    historical_data['last_update'] = datetime.now().isoformat()
    total_jobs = len(historical_data['jobs'])
    
    logger.info(f"发现新增职位: {len(added_jobs)}, 更新职位: {len(updated_jobs)}, 总职位数: {total_jobs}")
    return added_jobs, updated_jobs, historical_data, total_jobs

def generate_html_report(all_jobs, added_jobs, updated_jobs, total_jobs, expired_count):
    """生成HTML格式的报告"""
    logger.info("生成HTML报告...")
    
    # HTML头部
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>招聘信息更新报告</title>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; }
            .container { max-width: 800px; margin: 0 auto; }
            .stats { background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            .section { margin-bottom: 25px; }
            .section-title { font-size: 18px; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
            .job-list { list-style: none; padding: 0; }
            .job-item { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 4px; padding: 10px; margin-bottom: 10px; }
            .job-company { font-weight: bold; color: #2980b9; }
            .job-position { font-style: italic; }
            .job-links a { margin-right: 10px; }
            .new { background-color: #e8f4e4; border-left: 3px solid #2ecc71; }
            .updated { background-color: #fff8e1; border-left: 3px solid #f39c12; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>招聘信息更新报告</h1>
            <div class="stats">
                <p><strong>统计摘要</strong></p>
                <p>总职位数: {total_jobs}</p>
                <p>新增职位: {added_count} <span style="color:#2ecc71">(绿色标记)</span></p>
                <p>更新职位: {updated_count} <span style="color:#f39c12">(橙色标记)</span></p>
                <p>清理过期职位: {expired_count}</p>
                <p>报告时间: {report_time}</p>
            </div>
    """.format(
        total_jobs=total_jobs,
        added_count=len(added_jobs),
        updated_count=len(updated_jobs),
        expired_count=expired_count,
        report_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    
    # 新增职位部分
    if added_jobs:
        html += """
            <div class="section">
                <h2 class="section-title">新增职位 ({})</h2>
                <ul class="job-list">
        """.format(len(added_jobs))
        
        for job in added_jobs:
            html += """
                    <li class="job-item new">
                        <div class="job-company">{company}</div>
                        <div class="job-position">{position}</div>
                        <div>类型: {company_type} | 地点: {location}</div>
                        <div>招聘类型: {recruitment_type} | 目标: {target}</div>
                        <div>更新时间: {update_time} | 截止时间: {deadline}</div>
                        <div class="job-links">
                            <a href="{links}">职位链接</a>
                            <a href="{notice}">通知链接</a>
                        </div>
                        <div>备注: {notes}</div>
                    </li>
            """.format(**job)
        
        html += """
                </ul>
            </div>
        """
    
    # 更新职位部分
    if updated_jobs:
        html += """
            <div class="section">
                <h2 class="section-title">更新职位 ({})</h2>
                <ul class="job-list">
        """.format(len(updated_jobs))
        
        for job in updated_jobs:
            html += """
                    <li class="job-item updated">
                        <div class="job-company">{company}</div>
                        <div class="job-position">{position}</div>
                        <div>类型: {company_type} | 地点: {location}</div>
                        <div>招聘类型: {recruitment_type} | 目标: {target}</div>
                        <div>更新时间: {update_time} | 截止时间: {deadline}</div>
                        <div class="job-links">
                            <a href="{links}">职位链接</a>
                            <a href="{notice}">通知链接</a>
                        </div>
                        <div>备注: {notes}</div>
                    </li>
            """.format(**job)
        
        html += """
                </ul>
            </div>
        """
    
    # HTML尾部
    html += """
            <div class="footer">
                <p>此报告由招聘信息爬虫自动生成</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def send_email(subject, body):
    """发送邮件通知"""
    try:
        # 邮件服务器配置（这里使用QQ邮箱，其他邮箱修改smtp_server）
        smtp_server = "smtp.qq.com"
        smtp_port = 587

        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_USER  # 发送给自己
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        # 发送邮件
        server = smtplib.SMTP(smtp_server, smtp_port)
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
    
    try:
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
    except Exception as e:
        logger.error(f"主程序发生未处理异常: {str(e)}")
        # 尝试发送错误通知邮件
        try:
            error_html = f"<h1>招聘爬虫系统崩溃</h1><p>系统发生未处理异常:</p><pre>{str(e)}</pre>"
            send_email("招聘爬虫系统崩溃", error_html)
        except Exception as email_err:
            logger.error(f"发送错误通知邮件失败: {str(email_err)}")

if __name__ == "__main__":
    main()
