import os
import time
import json
import logging
import smtplib
import base64
import random
import re
import pandas as pd
import html
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from fake_useragent import UserAgent

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
SITE_URL = "https://www.givemeoc.com"#校招岗位
SITE_URL_INTERNSHIP = "https://www.givemeoc.com/internship"  # 实习岗位
WAIT_TIME_MIN = 1
WAIT_TIME_MAX = 3

# 从环境变量获取配置
EMAIL_USER = os.environ.get('EMAIL_USER')#发送邮箱
EMAIL_PWD = os.environ.get('EMAIL_PWD')#发送邮箱密码
RECEIVER_EMAIL = "2946273956@qq.com"#接受邮箱
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

def crawl_job_data(driver, site_url, start_page, end_page, job_type):
    """爬取指定站点和页码范围的数据"""
    try:
        # 访问指定类型的网站
        driver.get(site_url)
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
                        "job_type": job_type,  # 添加职位类型字段
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

def generate_html_report(campus_data, intern_data, campus_expired, intern_expired):
    """生成HTML格式的报告（支持校招和实习双类别）"""
    logger.info("生成双类别HTML报告...")
    
    # 转义函数 - 处理HTML特殊字符和花括号
    def safe_format(text):
        if not text:
            return ""
        # 先转义HTML特殊字符
        escaped = html.escape(text)
        # 转义花括号{} -> {{}}
        return escaped.replace("{", "{{").replace("}", "}}")
    
    # 构建职位条目的HTML
    def build_job_html(jobs):
        html_content = ""
        for job in jobs:
            # 安全处理所有字段
            safe_job = {k: safe_format(v) for k, v in job.items()}
            
            html_content += f"""
                <li class="job-item">
                    <div class="job-type">{safe_job.get('job_type', '')}</div>
                    <div class="job-company">{safe_job['company']}</div>
                    <div class="job-position">{safe_job['position']}</div>
                    <div>类型: {safe_job['company_type']} | 地点: {safe_job['location']}</div>
                    <div>招聘类型: {safe_job['recruitment_type']} | 目标: {safe_job['target']}</div>
                    <div>更新时间: {safe_job['update_time']} | 截止时间: {safe_job['deadline']}</div>
                    <div class="job-links">
                        <a href="{safe_job['links']}">职位链接</a>
                        <a href="{safe_job['notice']}">通知链接</a>
                    </div>
                    <div>备注: {safe_job['notes']}</div>
                </li>
            """
        return html_content

    # 统计校招数据
    campus_stats = {
        "total": len(campus_data["jobs"]),
        "new": len([j for j in campus_data.get("added", [])]),
        "updated": len([j for j in campus_data.get("updated", [])])
    }
    
    # 统计实习数据
    intern_stats = {
        "total": len(intern_data["jobs"]),
        "new": len([j for j in intern_data.get("added", [])]),
        "updated": len([j for j in intern_data.get("updated", [])])
    }

    # HTML头部
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>招聘信息更新报告</title>
        <style>
            /* 样式保持不变... */
        </style>
    </head>
    <body>
        <div class="container">
            <h1>招聘信息更新报告</h1>
            <div class="stats">
                <p><strong>统计摘要</strong></p>
                <p>校招总岗位: {campus_stats['total']} | 实习总岗位: {intern_stats['total']}</p>
                <p>校招新增岗位: {campus_stats['new']} | 实习新增岗位: {intern_stats['new']}</p>
                <p>校招更新岗位: {campus_stats['updated']} | 实习更新岗位: {intern_stats['updated']}</p>
                <p>清理过期校招职位: {campus_expired} | 清理过期实习职位: {intern_expired}</p>
                <p>报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
    """
    
    # 校招职位部分
    if campus_stats['new'] > 0:
        html_content += f"""
            <div class="section">
                <h2 class="section-title">校招新增职位 ({campus_stats['new']})</h2>
                <ul class="job-list">
                    {build_job_html(campus_data.get("added", []))}
                </ul>
            </div>
        """
    
    # 实习职位部分
    if intern_stats['new'] > 0:
        html_content += f"""
            <div class="section">
                <h2 class="section-title">实习新增职位 ({intern_stats['new']})</h2>
                <ul class="job-list">
                    {build_job_html(intern_data.get("added", []))}
                </ul>
            </div>
        """
    
    # HTML尾部
    html_content += """
            <div class="footer">
                <p>此报告由招聘信息爬虫自动生成</p>
                <p>附件包含校招和实习的完整招聘信息Excel文件</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

    
def send_email(subject, body, attachment_paths=None):
    """发送邮件通知（支持多附件）"""
    try:
        # 邮件服务器配置（这里使用QQ邮箱示例）
        smtp_server = "smtp.qq.com"
        smtp_port = 587

        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = RECEIVER_EMAIL  # 主收件人
        msg['Cc'] = EMAIL_USER       # 抄送给自己
        msg['Subject'] = subject
        
        # 支持HTML正文
        msg.attach(MIMEText(body, 'html'))

        # 添加多个附件
        if attachment_paths:
            for path in attachment_paths:
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                    msg.attach(part)
                    logger.info(f"已添加附件: {path}")

        # 发送邮件（同时发给主收件人和抄送地址）
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PWD)
            server.sendmail(
                EMAIL_USER,
                [RECEIVER_EMAIL, EMAIL_USER],  # 同时发送给主收件人和自己
                msg.as_string()
            )
        
        logger.info(f"邮件已发送至: {RECEIVER_EMAIL} 和 {EMAIL_USER}")
        return True
    except Exception as e:
        logger.error(f"邮件发送失败: {str(e)}")
        return False



def main():
    """主程序（支持双站点爬取）"""
    logger.info(f"开始爬取招聘信息，时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 处理校招站点
        campus_data = process_site(
            "校招",
            SITE_URL_CAMPUS,
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
        
        # 生成HTML报告
        html_report = generate_html_report(
            campus_data, 
            intern_data,
            campus_data.get("expired", 0),
            intern_data.get("expired", 0)
        )
        
        # 发送邮件（带双附件）
        subject = f"双站点招聘信息更新 {datetime.now().strftime('%Y-%m-%d')}"
        send_email(
            subject, 
            html_report, 
            attachment_paths=[EXCEL_FILE_CAMPUS, EXCEL_FILE_INTERNSHIP]
        )
        
        logger.info("处理完成!")
    except Exception as e:
        logger.error(f"主程序发生未处理异常: {str(e)}")
        
        # 尝试发送错误通知邮件
        try:
            error_html = f"<h1>招聘爬虫系统崩溃</h1><p>系统发生未处理异常:</p><pre>{str(e)}</pre>"
            send_email("招聘爬虫系统崩溃", error_html)
        except Exception as email_err:
            logger.error(f"发送错误通知邮件失败: {str(email_err)}")


def process_site(site_name, site_url, data_file, excel_file):
    """处理单个站点（校招/实习）的完整流程"""
    logger.info(f"开始处理[{site_name}]站点: {site_url}")
    
    # 1. 加载历史数据
    historical_data = load_historical_data(data_file)
    
    # 2. 爬取新数据
    all_jobs = []
    current_start_page = START_PAGE
    driver = setup_browser()
    
    # 循环爬取直到达到目标页数
    while current_start_page <= END_PAGE:
        logger.info(f"[{site_name}]开始新的浏览器会话，从第 {current_start_page} 页开始爬取...")
        data, last_page = crawl_job_data(
            driver, 
            site_url, 
            current_start_page, 
            END_PAGE,
            site_name  # 传递职位类型
        )
        all_jobs.extend(data)
        logger.info(f"[{site_name}]本次会话爬取了 {len(data)} 条数据")
        current_start_page = last_page + 1
        
        if current_start_page <= END_PAGE:
            logger.info(f"[{site_name}]等待5秒后开始新的会话...")
            time.sleep(5)
    
    driver.quit()
    
    if not all_jobs:
        logger.error(f"[{site_name}]没有爬取到任何数据")
        return {
            "jobs": {},
            "added": [],
            "updated": [],
            "expired": 0
        }
    
    logger.info(f"[{site_name}]共爬取 {len(all_jobs)} 条职位信息")
    
    # 3. 清理过期职位
    historical_data, expired_count = clean_expired_jobs(historical_data)
    logger.info(f"[{site_name}]清理了 {expired_count} 个过期职位")
    
    # 4. 对比新旧数据
    added_jobs, updated_jobs, historical_data, total_jobs = compare_jobs(all_jobs, historical_data)
    
    # 5. 保存更新后的数据
    save_historical_data(historical_data, data_file)
    
    # 6. 生成Excel文件
    all_job_list = list(historical_data['jobs'].values())
    save_excel_file(all_job_list, excel_file, added_jobs=added_jobs)
    
    return {
        "jobs": historical_data['jobs'],
        "added": added_jobs,
        "updated": updated_jobs,
        "expired": expired_count
    }

# ... 其他辅助函数保持不变 ...

if __name__ == "__main__":
    main()
