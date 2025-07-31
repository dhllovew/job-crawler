import os
import time
import json
import logging
import smtplib
import random
import pandas as pd
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from fake_useragent import UserAgent
import openpyxl
import html

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
SITE_URL = "https://www.givemeoc.com"  # 校招岗位
SITE_URL_INTERNSHIP = "https://www.givemeoc.com/internship"  # 实习岗位
WAIT_TIME_MIN = 1
WAIT_TIME_MAX = 3

# 从环境变量获取配置
EMAIL_USER = os.environ.get('EMAIL_USER')  # 发送邮箱
EMAIL_PWD = os.environ.get('EMAIL_PWD')  # 发送邮箱密码
RECEIVER_EMAILS = os.environ.get('RECEIVER_EMAILS').split(';')  # 多个接收邮箱（分号分隔）

# 为两类岗位创建独立的存储文件
DATA_FILE_CAMPUS = "campus_jobs.json"  # 校招数据文件
DATA_FILE_INTERNSHIP = "intern_jobs.json"  # 实习数据文件
EXCEL_FILE_CAMPUS = "campus_jobs.xlsx"  # 校招Excel
EXCEL_FILE_INTERNSHIP = "intern_jobs.xlsx"  # 实习Excel

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

def crawl_campus_data(driver, site_url, start_page, end_page):
    """
    专门爬取校招站点数据
    注意：以下选择器需要根据实际页面结构调整
    """
    try:
        # 访问校招网站
        driver.get(site_url)
        time.sleep(random.uniform(WAIT_TIME_MIN, WAIT_TIME_MAX))
        
        # 如果起始页不是第一页，跳转到指定页
        if start_page > 1:
            try:
                logger.info(f"跳转到第 {start_page} 页...")
                # TODO: 根据实际页面结构调整选择器
                page_input = driver.find_element("css selector", "input.crt-page-input")
                page_input.clear()
                page_input.send_keys(str(start_page))

                # TODO: 根据实际页面结构调整选择器
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
            logger.info(f"正在爬取校招第 {page} 页...")
            current_page = page

            # 模拟人类滚动
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))

            # 解析数据 - TODO: 根据实际页面结构调整选择器
            job_items = driver.find_elements("css selector", "table.crt-table tbody tr")

            for item in job_items:
                try:
                    # 以下选择器需要根据实际校招页面结构调整
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
                        "job_type": "校招",  # 固定为校招类型
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
                    logger.warning(f"处理校招数据行时出错: {e}")
                    continue

            # 校招翻页逻辑
            if page < min(end_page, start_page + MAX_PAGES_PER_SESSION - 1):
                try:
                    # TODO: 根据实际校招页面结构调整选择器
                    page_input = driver.find_element("css selector", "input.crt-page-input")
                    page_input.clear()
                    page_input.send_keys(str(page + 1))

                    # TODO: 根据实际校招页面结构调整选择器
                    go_button = driver.find_element("css selector", "button.crt-page-go-btn")
                    driver.execute_script("arguments[0].click();", go_button)
                    time.sleep(random.gauss(3, 1))
                    
                    # 更新User-Agent
                    new_ua = UserAgent().random
                    driver.execute_script(f"navigator.userAgent = '{new_ua}';")
                except Exception as e:
                    logger.warning(f"校招翻页时出错，可能已到达最后一页: {e}")
                    break

        return crawled_data, current_page
    except Exception as e:
        logger.error(f"爬取校招数据过程中发生错误: {e}")
        return [], start_page

def crawl_internship_data(driver, site_url, start_page, end_page):
    """
    专门爬取实习站点数据
    注意：以下选择器需要根据实际页面结构调整
    """
    try:
        # 访问实习网站
        driver.get(site_url)
        time.sleep(random.uniform(WAIT_TIME_MIN, WAIT_TIME_MAX))
        
        # 如果起始页不是第一页，跳转到指定页
        if start_page > 1:
            try:
                logger.info(f"跳转到第 {start_page} 页...")
                # TODO: 根据实际实习页面结构调整选择器
                page_input = driver.find_element("css selector", "input.int-page-input")
                page_input.clear()
                page_input.send_keys(str(start_page))

                # TODO: 根据实际实习页面结构调整选择器
                go_button = driver.find_element("css selector", "button.int-page-go-btn")
                driver.execute_script("arguments[0].click();", go_button)
                time.sleep(random.gauss(3, 1))
            except Exception as e:
                logger.error(f"跳转到第 {start_page} 页时出错: {e}")
                return [], start_page - 1

        crawled_data = []
        current_page = start_page

        # 爬取指定页数的数据
        for page in range(start_page, min(end_page + 1, start_page + MAX_PAGES_PER_SESSION)):
            logger.info(f"正在爬取实习第 {page} 页...")
            current_page = page

            # 模拟人类滚动
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))

            # 解析数据 - TODO: 根据实际实习页面结构调整选择器
            job_items = driver.find_elements("css selector", "table.int-table tbody tr")

            for item in job_items:
                try:
                    # 以下选择器需要根据实际实习页面结构调整
                    company = safe_get_text(item, "td.int-col-company")
                    company_type = safe_get_text(item, "td.int-col-type")
                    location = safe_get_text(item, "td.int-col-location")
                    recruitment_type = safe_get_text(item, "td.int-col-recruitment-type")
                    target = safe_get_text(item, "td.int-col-target")
                    position = safe_get_text(item, "td.int-col-position")
                    update_time = safe_get_text(item, "td.int-col-update-time")
                    deadline = safe_get_text(item, "td.int-col-deadline")
                    links = safe_get_attr(item, "td.int-col-links a", "href")
                    notice = safe_get_attr(item, "td.int-col-notice a", "href")
                    referral = safe_get_text(item, "td.int-col-referral")
                    notes = safe_get_text(item, "td.int-col-notes")

                    crawled_data.append({
                        "job_type": "实习",  # 固定为实习类型
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
                    logger.warning(f"处理实习数据行时出错: {e}")
                    continue

            # 实习翻页逻辑
            if page < min(end_page, start_page + MAX_PAGES_PER_SESSION - 1):
                try:
                    # TODO: 根据实际实习页面结构调整选择器
                    page_input = driver.find_element("css selector", "input.int-page-input")
                    page_input.clear()
                    page_input.send_keys(str(page + 1))

                    # TODO: 根据实际实习页面结构调整选择器
                    go_button = driver.find_element("css selector", "button.int-page-go-btn")
                    driver.execute_script("arguments[0].click();", go_button)
                    time.sleep(random.gauss(3, 1))
                    
                    # 更新User-Agent
                    new_ua = UserAgent().random
                    driver.execute_script(f"navigator.userAgent = '{new_ua}';")
                except Exception as e:
                    logger.warning(f"实习翻页时出错，可能已到达最后一页: {e}")
                    break

        return crawled_data, current_page
    except Exception as e:
        logger.error(f"爬取实习数据过程中发生错误: {e}")
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

def load_historical_data(data_file):
    """从指定文件加载历史数据"""
    try:
        logger.info(f"加载历史数据: {data_file}")
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            logger.info(f"首次运行：尚未找到历史数据文件 {data_file}")
            return {
                "last_update": None,
                "jobs": {}
            }
    except Exception as e:
        logger.warning(f"加载历史数据失败: {str(e)}，将创建新数据集")
        return {
            "last_update": None,
            "jobs": {}
        }

def save_historical_data(data, data_file):
    """保存数据到指定文件"""
    try:
        logger.info(f"保存数据到本地: {data_file}")
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"成功保存数据到: {data_file}")
        return True
    except Exception as e:
        logger.error(f"保存数据失败: {str(e)}")
        return False

def save_excel_file(job_list, filename, added_jobs=None):
    """保存Excel文件（自动中文表头+高亮新增）"""
    try:
        # --- 1. 中文列名映射 ---
        CN_HEADERS = {
            "company": "公司名称",
            "company_type": "公司类型",
            "location": "工作地点",
            "recruitment_type": "招聘类型",
            "target": "招聘对象",
            "position": "职位名称",
            "update_time": "更新时间",
            "deadline": "截止时间",
            "links": "职位链接",
            "notice": "通知链接",
            "referral": "内推信息",
            "notes": "备注",
            "crawl_time": "爬取时间"
        }
        
        # --- 2. 处理数据 ---
        # 创建DataFrame并重命名列
        df = pd.DataFrame(job_list).rename(columns=CN_HEADERS)
        
        # 标记新增职位（临时列，完成后删除）
        if added_jobs:
            added_ids = {f"{j['company']}-{j['position']}" for j in added_jobs}
            df['_is_new'] = df.apply(
                lambda x: "是" if f"{x['公司名称']}-{x['职位名称']}" in added_ids else "否", 
                axis=1
            )
        
        # --- 3. 保存Excel ---
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='招聘信息')
            
            # 获取工作表对象
            worksheet = writer.sheets['招聘信息']
            
            # --- 4. 高亮新增职位 ---
            if added_jobs:
                from openpyxl.styles import PatternFill
                yellow_fill = PatternFill(start_color="FFFF00", fill_type="solid")
                
                for row in worksheet.iter_rows(min_row=2):
                    if row[-1].value == "是":  # 最后一列是临时标记列
                        for cell in row[:-1]:  # 不处理标记列本身
                            cell.fill = yellow_fill
                
                # 删除临时列
                worksheet.delete_cols(worksheet.max_column)
            
            # --- 5. 调整列宽 ---
            for col in worksheet.columns:
                max_len = max(len(str(cell.value)) for cell in col)
                worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 2, 30)
        
        logger.info(f"Excel文件已保存: {filename}")
        return True
        
    except Exception as e:
        logger.error(f"保存Excel失败: {str(e)}")
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
                deadline_date = datetime.strptime(job['deadline'], "%Y-%m-%d")
                if deadline_date < current_time:
                    del historical_data['jobs'][job_id]
                    expired_count += 1
                    logger.info(f"已删除到期职位: {job['company']} - {job['position']} (截止时间: {job['deadline']})")
            except Exception as e:
                logger.warning("招满即止")
                continue
    logger.info(f"清理完成，共删除 {expired_count} 个过期职位")
    return historical_data


# 添加生成精美HTML邮件的函数
def generate_email_html(new_jobs, job_type):
    """生成美观的HTML邮件内容"""
    # CSS样式
    styles = """
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            line-height: 1.6; 
            color: #333; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px; 
            background-color: #f5f7fa; 
        }
        .header { 
            background: linear-gradient(135deg, #4b6cb7 0%, #182848 100%);
            color: white; 
            padding: 20px; 
            border-radius: 8px 8px 0 0;
            text-align: center;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 { 
            margin: 0; 
            font-weight: 600;
            font-size: 24px;
        }
        .notification-card {
            background: white;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            border: 1px solid #eaeaea;
        }
        .stats {
            display: flex;
            justify-content: space-around;
            margin-bottom: 25px;
            text-align: center;
        }
        .stat-item {
            background: #f0f5ff;
            padding: 15px;
            border-radius: 8px;
            flex: 1;
            margin: 0 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .stat-item span {
            display: block;
            font-size: 28px;
            font-weight: bold;
            color: #4b6cb7;
            margin-bottom: 5px;
        }
        .job-list {
            border-collapse: collapse;
            width: 100%;
        }
        .job-item {
            background-color: #fff;
            border-left: 4px solid #4b6cb7;
            margin-bottom: 15px;
            padding: 15px;
            border-radius: 0 6px 6px 0;
            transition: all 0.3s ease;
        }
        .job-item:hover {
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(75, 108, 183, 0.15);
        }
        .company {
            font-weight: bold;
            color: #2c3e50;
            font-size: 18px;
            margin-bottom: 5px;
        }
        .position {
            font-weight: 600;
            color: #4b6cb7;
            font-size: 16px;
            margin: 10px 0;
        }
        .meta {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 10px 0;
            color: #555;
            font-size: 14px;
        }
        .meta span {
            display: flex;
            align-items: center;
        }
        .meta span:before {
            content: "•";
            margin-right: 5px;
            color: #4b6cb7;
        }
        .deadline {
            background-color: #fff9e6;
            color: #e67e22;
            padding: 5px 10px;
            border-radius: 4px;
            font-weight: 600;
            display: inline-block;
            margin-top: 5px;
        }
        .links a {
            display: inline-block;
            background: #4b6cb7;
            color: white !important;
            text-decoration: none;
            padding: 8px 15px;
            border-radius: 4px;
            margin-top: 10px;
            font-weight: 500;
            transition: background 0.3s;
        }
        .links a:hover {
            background: #3a559f;
            text-decoration: none;
        }
        .notes {
            margin-top: 10px;
            padding: 10px;
            background-color: #f8f9fa;
            border-left: 3px solid #4b6cb7;
            font-size: 14px;
            color: #555;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #777;
            font-size: 13px;
            padding: 15px;
            border-top: 1px solid #eee;
        }
        .highlight {
            background: linear-gradient(120deg, #e0f7fa 0%, #bbdefb 100%);
            padding: 2px 5px;
            border-radius: 3px;
        }
    </style>
    """
    
    # 构建HTML内容
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>新职位通知 - {job_type}</title>
        {styles}
    </head>
    <body>
        <div class="header">
            <h1>🎯 新职位通知 - {job_type}</h1>
        </div>
        
        <div class="notification-card">
            <div class="stats">
                <div class="stat-item">
                    <span>{len(new_jobs)}</span>
                    新职位
                </div>
                <div class="stat-item">
                    <span>{len(set(job['company'] for job in new_jobs))}</span>
                    家公司
                </div>
                <div class="stat-item">
                    <span>{datetime.now().strftime('%m/%d')}</span>
                    更新日期
                </div>
            </div>
            
            <div class="job-list">
    """
    
    # 添加每个职位的信息
    for job in new_jobs:
        deadline = job.get('deadline', '截止时间待定')
        links_html = ""
        if job.get('links'):
            links_html = f'<div class="links"><a href="{job["links"]}" target="_blank">查看职位详情</a></div>'
        
        # 处理职位亮点
        notes = job.get('notes', '')
        if notes:
            notes = f'<div class="notes">💡 职位亮点: {html.escape(notes)}</div>'
        
        html_content += f"""
        <div class="job-item">
            <div class="company">{html.escape(job.get('company', ''))}</div>
            <div class="position">🏢 {html.escape(job.get('position', ''))}</div>
            <div class="meta">
                <span>📍 {html.escape(job.get('location', ''))}</span>
                <span>🚀 {html.escape(job.get('recruitment_type', ''))}</span>
                <span>🎯 {html.escape(job.get('target', ''))}</span>
            </div>
            <div class="deadline">⏰ 截止时间: {html.escape(str(deadline))}</div>
            {notes}
            {links_html}
        </div>
        """
    
    # 页脚
    html_content += f"""
            </div>
        </div>
        
        <div class="footer">
            <p>此邮件由自动爬虫系统生成 | 抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>© {datetime.now().year} 职位监控系统 | 共发现 {len(new_jobs)} 个新职位</p>
        </div>
    </body>
    </html>
    """
    
    return html_content
        
def send_email(subject, body, attachment_paths=None):
    """
    发送邮件通知（支持多附件和多接收邮箱）
    :param subject: 邮件主题
    :param body: 邮件正文内容
    :param attachment_paths: 附件路径列表(可选)
    :return: 发送是否成功
    """
    try:
        smtp_server = "smtp.qq.com"
        smtp_port = 587

        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = ", ".join(RECEIVER_EMAILS)
        msg['Subject'] = subject
        
        # 添加HTML格式的邮件正文
        msg.attach(MIMEText(body, 'html'))

        # 添加附件
        if attachment_paths:
            for path in attachment_paths:
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                    msg.attach(part)

        # 发送邮件
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PWD)
            server.sendmail(EMAIL_USER, RECEIVER_EMAILS, msg.as_string())
        
        logger.info(f"邮件已发送至: {', '.join(RECEIVER_EMAILS)}")
        return True
    except Exception as e:
        logger.error(f"邮件发送失败: {str(e)}")
        return False

def process_site(site_name, site_url, data_file, excel_file):
    """处理单个站点的爬取和更新逻辑"""
    logger.info(f"处理站点: {site_name}")
    
    # 初始化浏览器
    driver = setup_browser()
    
    # 加载历史数据
    historical_data = load_historical_data(data_file)
    
    # 爬取新数据
    if "校招" in site_name:
        new_jobs, last_page = crawl_campus_data(driver, site_url, START_PAGE, END_PAGE)
    else:
        new_jobs, last_page = crawl_internship_data(driver, site_url, START_PAGE, END_PAGE)
    
    logger.info(f"共爬取到 {len(new_jobs)} 条新职位信息")
    
    # 关闭浏览器
    driver.quit()
    
    # 检测新职位
    added_jobs = []
    existing_jobs = historical_data.get("jobs", {})
    
    for job in new_jobs:
        # 使用公司+职位作为唯一ID
        job_id = f"{job['company']}-{job['position']}"
        
        # 如果是新职位
        if job_id not in existing_jobs:
            added_jobs.append(job)
            existing_jobs[job_id] = job
            logger.info(f"发现新职位: {job['company']} - {job['position']}")
    
    # 更新历史数据
    historical_data["jobs"] = existing_jobs
    historical_data["last_update"] = datetime.now().isoformat()
    
    # 清理过期职位
    historical_data = clean_expired_jobs(historical_data)
    
    # 保存更新后的数据
    save_historical_data(historical_data, data_file)
    
    # 准备邮件内容
    email_body = f"""
    <h2>{site_name}职位更新报告</h2>
    <p>更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>爬取页面范围: {START_PAGE}-{last_page}</p>
    <p>新增职位: {len(added_jobs)} 个</p>
    <p>总职位数: {len(existing_jobs)} 个</p>
    """
    
    if added_jobs:
        email_body += "<h3>新增职位列表:</h3><ul>"
        for job in added_jobs:
            email_body += f"<li>{job['company']} - {job['position']} (截止: {job['deadline']})</li>"
        email_body += "</ul>"
    
    # 保存Excel文件并发送邮件
    if save_excel_file(list(existing_jobs.values()), excel_file, added_jobs=added_jobs):
        # 发送带附件的邮件
        send_email(
            subject=f"{site_name}招聘信息更新 - {datetime.now().strftime('%Y%m%d')}",
            body=email_body,
            attachment_paths=[excel_file]
        )
    else:
        # 发送不带附件的邮件
        email_body += "<p>警告: 未能生成Excel附件</p>"
        send_email(
            subject=f"{site_name}招聘信息更新 - {datetime.now().strftime('%Y%m%d')}",
            body=email_body
        )
    
    logger.info(f"{site_name}站点处理完成")
    
    # 返回当前所有职位数据
    return list(existing_jobs.values())

def main():
    """主程序（支持双站点爬取）"""
    logger.info(f"开始爬取招聘信息，时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 处理校招站点
        campus_data = process_site(
            "校招",
            SITE_URL,
            DATA_FILE_CAMPUS,
            EXCEL_FILE_CAMPUS
        )
        
        # 处理实习站点
        intern_data = process_site(
            "实习",
            SITE_URL_INTERNSHIP,
            DATA_FILE_INTERNSHIP,
            EXCEL_FILE_INTERNSHIP
        )
        
        logger.info(f"校招职位总数: {len(campus_data)}")
        logger.info(f"实习职位总数: {len(intern_data)}")
        logger.info("所有任务已完成")
        
    except Exception as e:
        logger.error(f"主程序发生错误: {e}")
        # 发送错误通知
        send_email(
            subject="招聘信息爬取出错",
            body=f"<h2>爬取过程中发生错误</h2><p>{str(e)}</p><p>时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        )


if __name__ == "__main__":
    main()
