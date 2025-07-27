# crawler_github.py - GitHub Actions专用版本
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from fake_useragent import UserAgent
import pandas as pd
import numpy as np
import random
import time
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

# 页码设置
START_PAGE = 1
END_PAGE = 6
MAX_PAGES_PER_SESSION = 2

# 文件路径设置
EXCEL_PATH = "招聘信息.xlsx"
HIGHLIGHT_COLOR = "FFFF00"  # 黄色高亮

# 邮箱配置（从环境变量获取）
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PWD = os.environ.get('EMAIL_PWD')
EMAIL_RECEIVER = os.environ.get('EMAIL_USER')  # 默认发送给自己


def send_email(subject, body, attachment_path=None):
    """发送邮件"""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject

    # 邮件正文
    msg.attach(MIMEText(body, 'plain'))

    # 添加附件
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            attach = MIMEApplication(f.read(), _subtype='xlsx')
            attach.add_header('Content-Disposition', 'attachment',
                              filename=os.path.basename(attachment_path))
            msg.attach(attach)

    # 发送邮件
    try:
        server = smtplib.SMTP('smtp.qq.com', 587)  # QQ邮箱服务器
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PWD)
        server.send_message(msg)
        server.quit()
        logger.info("邮件发送成功")
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")


def setup_browser():
    """配置浏览器（GitHub Actions专用）"""
    # 设置Chromedriver路径
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # 无头模式
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--incognito")  # 无痕模式
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


def crawl_job_data(start_page, end_page):
    """爬取指定页码范围的数据"""
    driver = setup_browser()
    ua = UserAgent()

    # 访问网站
    driver.get("https://www.givemeoc.com")
    time.sleep(random.uniform(2, 4))  # 初始等待

    # 如果起始页不是第一页，需要先跳转到指定页
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
            driver.quit()
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
                company = item.find_element("css selector", "td.crt-col-company").text
                company_type = item.find_element("css selector", "td.crt-col-type").text
                location = item.find_element("css selector", "td.crt-col-location").text
                recruitment_type = item.find_element("css selector", "td.crt-col-recruitment-type").text
                target = item.find_element("css selector", "td.crt-col-target").text
                position = item.find_element("css selector", "td.crt-col-position").text
                update_time = item.find_element("css selector", "td.crt-col-update-time").text
                deadline = item.find_element("css selector", "td.crt-col-deadline").text
                links = item.find_element("css selector", "td.crt-col-links a").get_attribute("href")
                notice = item.find_element("css selector", "td.crt-col-notice a").get_attribute("href")
                referral = item.find_element("css selector", "td.crt-col-referral").text
                notes = item.find_element("css selector", "td.crt-col-notes").text

                crawled_data.append(
                    [company, company_type, location, recruitment_type, target, position,
                     update_time, deadline, links, notice, referral, notes])
            except Exception as e:
                logger.warning(f"处理行数据时出错: {e}")
                continue

        # 翻页部分
        if page < min(end_page, start_page + MAX_PAGES_PER_SESSION - 1):
            try:
                page_input = driver.find_element("css selector", "input.crt-page-input")
                page_input.clear()
                page_input.send_keys(str(page + 1))

                go_button = driver.find_element("css selector", "button.crt-page-go-btn")
                driver.execute_script("arguments[0].click();", go_button)

                time.sleep(random.gauss(3, 1))
                new_ua = ua.random
                driver.execute_script(f"navigator.userAgent = '{new_ua}';")
            except:
                logger.warning("可能已到达最后一页")
                break

    # 关闭浏览器
    driver.quit()

    return crawled_data, current_page


def merge_data(new_df, existing_df=None):
    """合并新旧数据并标记新增项"""
    # 添加当前时间列
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_df["抓取时间"] = now_str

    # 如果没有现有数据，所有数据都是新的
    if existing_df is None:
        new_df["状态"] = "新增"
        return new_df, len(new_df), 0

    # 添加状态列（如果不存在）
    if "状态" not in existing_df.columns:
        existing_df["状态"] = ""

    # 合并数据框
    merged_df = pd.concat([existing_df, new_df], ignore_index=True)

    # 创建唯一标识符（公司+岗位）
    merged_df["标识符"] = merged_df["公司名称"] + "|" + merged_df["岗位"]

    # 标记重复项
    merged_df["重复"] = merged_df.duplicated(subset="标识符", keep=False)

    # 找出新增项
    new_entries = []
    updated_entries = []
    for idx, row in merged_df.iterrows():
        # 如果是新数据且没有重复（即全新记录）
        if row["抓取时间"] == now_str and not row["重复"]:
            row["状态"] = "新增"
            new_entries.append(row)
        # 如果是新数据但有重复（即更新记录）
        elif row["抓取时间"] == now_str and row["重复"]:
            row["状态"] = "更新"
            updated_entries.append(row)
        # 如果是旧数据
        else:
            # 保留旧数据的原始状态
            pass

    # 移除临时列
    merged_df = merged_df.drop(["标识符", "重复"], axis=1)

    # 去重（保留最后一次出现的记录）
    merged_df = merged_df.drop_duplicates(subset=["公司名称", "岗位"], keep="last")

    # 计算新增和更新的数量
    new_count = len([r for r in merged_df["状态"] if r == "新增"])
    updated_count = len([r for r in merged_df["状态"] if r == "更新"])

    return merged_df, new_count, updated_count


def main():
    """主程序"""
    logger.info(f"开始爬取招聘信息，时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 创建数据目录
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    excel_path = os.path.join(data_dir, EXCEL_PATH)

    # 爬取数据
    all_jobs = []
    current_start_page = START_PAGE

    # 循环爬取直到达到目标页数
    while current_start_page <= END_PAGE:
        logger.info(f"开始新的浏览器会话，从第 {current_start_page} 页开始爬取...")
        data, last_page = crawl_job_data(current_start_page, END_PAGE)
        all_jobs.extend(data)
        logger.info(f"本次会话爬取了 {len(data)} 条数据")
        current_start_page = last_page + 1

        if current_start_page <= END_PAGE:
            logger.info("等待5秒后开始新的会话...")
            time.sleep(5)

    # 处理数据
    if all_jobs:
        # 创建DataFrame
        columns = ["公司名称", "公司类型", "工作地点", "招聘类型", "招聘对象", "岗位", "更新时间",
                   "截止时间", "投递链接", "公告链接", "内推码", "备注学位要求"]

        new_df = pd.DataFrame(all_jobs, columns=columns)
        logger.info(f"爬取完成，共获取 {len(new_df)} 条数据")

        # 尝试读取现有数据
        existing_df = None
        if os.path.exists(excel_path):
            try:
                existing_df = pd.read_excel(excel_path)
                logger.info(f"找到现有数据文件，包含 {len(existing_df)} 条记录")
            except Exception as e:
                logger.error(f"读取现有数据文件失败: {e}")

        # 合并数据
        merged_df, new_count, updated_count = merge_data(new_df, existing_df)

        # 保存到Excel
        merged_df.to_excel(excel_path, index=False)
        logger.info(f"成功保存数据到Excel，总记录数: {len(merged_df)}")
        logger.info(f"新增数据: {new_count} 条, 更新数据: {updated_count} 条")

        # 发送邮件通知
        email_subject = f"招聘信息更新 {datetime.now().strftime('%Y-%m-%d')}"
        email_body = f"本次爬取结果：总记录数: {len(merged_df)}，新增数据: {new_count} 条, 更新数据: {updated_count} 条"
        send_email(email_subject, email_body, excel_path)
        logger.info("处理完成!")
    else:
        logger.error("没有爬取到任何数据")
        send_email("招聘信息爬取失败", "本次爬取未获取到任何数据")


if __name__ == "__main__":
    main()