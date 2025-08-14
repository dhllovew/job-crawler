# 校招与实习信息爬虫工具

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

一个自动化爬取、筛选和推送2026届相关校招/实习信息的工具，支持数据本地存储与邮件通知功能。


## 项目简介

本工具通过Selenium自动化爬取指定招聘网站的校招和实习岗位信息，定向筛选2026届相关职位，将数据保存为JSON和Excel格式（新增职位自动高亮），并通过邮件推送最新职位动态，帮助2026届毕业生及时获取目标岗位信息。

## 项目特色
本项目可直接克隆后挂载到GitHub上每天自动运行，去本地化，无需额外的服务器。


## 功能特点

- **定向爬取**：支持校招和实习两个渠道的职位信息爬取，可配置爬取页码范围
- **智能筛选**：自动过滤非2026届相关职位，仅保留目标群体岗位
- **数据管理**：
  - 本地JSON存储历史数据，自动去重
  - 生成Excel报表，新增职位高亮标记
  - 定期清理过期职位和无效数据
- **通知机制**：通过邮件推送新增职位信息，支持多接收人
- **反爬策略**：
  - 随机User-Agent与页面等待时间
  - 每次会话爬取页数限制
  - 浏览器自动化特征隐藏
  - 模拟人类滚动与点击行为


## 环境依赖

- Python 3.8+
- 依赖库：
  ```bash
  pip install selenium pandas fake-useragent openpyxl
  ```
- 浏览器驱动：
  - Chrome/Chromium 浏览器
  - 对应版本的 [ChromeDriver](https://sites.google.com/chromium.org/driver/)（需配置到环境变量或同目录）


## 安装与配置

1. **克隆仓库**：
   ```bash
   git clone https://github.com/yourusername/recruitment-spider.git
   cd recruitment-spider
   ```

2. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

3. **环境变量配置**（必填，用于邮件功能）：
   - `EMAIL_USER`：发送邮箱账号（如QQ邮箱）
   - `EMAIL_PWD`：发送邮箱授权码（非登录密码，需在邮箱安全设置中获取）
   - `RECEIVER_EMAILS`：接收邮箱列表（英文分号分隔，如 `a@xxx.com;b@xxx.com`）

   ```bash
   # 临时配置示例（Linux/Mac）
   export EMAIL_USER="your-email@qq.com"
   export EMAIL_PWD="your-smtp-auth-code"
   export RECEIVER_EMAILS="target1@xxx.com;target2@xxx.com"
   
   # Windows 命令提示符
   set EMAIL_USER=your-email@qq.com
   set EMAIL_PWD=your-smtp-auth-code
   set RECEIVER_EMAILS=target1@xxx.com;target2@xxx.com
   ```

4. **参数自定义**（可选，修改代码中常量）：
   - `START_PAGE`/`END_PAGE`：爬取页码范围（默认1-6页）
   - `MAX_PAGES_PER_SESSION`：每次会话最大爬取页数（默认2页，作用反爬）
   - `SITE_URL`/`SITE_URL_INTERNSHIP`：目标网站URL（暂时不可替换其他网站）


## 使用方法

直接运行主程序：
```bash
python recruitment_spider.py
```

程序执行流程：
1. 初始化浏览器环境
2. 分页爬取校招/实习信息（每次会话2页）
3. 筛选2026届相关职位并去重
4. 保存数据到JSON和Excel
5. 发送包含新增职位的邮件通知


## 输出说明

- **数据文件**：
  - `campus_jobs.json`：校招历史数据（JSON格式）
  - `intern_jobs.json`：实习历史数据（JSON格式）
  - `campus_jobs.xlsx`：校招Excel报表（新增职位黄色高亮）
  - `intern_jobs.xlsx`：实习Excel报表（新增职位黄色高亮）

- **邮件内容**：
  - 新增职位数量统计
  - 公司/岗位/地点/截止时间等关键信息
  - 职位详情链接
  - 自动标记2026届相关标签
  - **邮件内容例子展示截图：**
  - ![QQ邮箱功能截图](https://raw.githubusercontent.com/dhllovew/job-crawler/master/QQ邮箱功能截图.png)

## 后期开发
- **就业建议**：
- 定向爬取自媒体关于就业的帖子和评论，进行文本分析量化。
- 自媒体信息迭代速度更快，但是个例也比较多，需要区分。
- 目前已经完成自媒体爬虫的实现，测试文本分析量化中。

## 注意事项

- **网站合规性**：
  - 请遵守目标网站的`robots.txt`协议和使用条款
  - 合理设置爬取频率，避免给服务器造成压力

- **反爬风险**：
  - 频繁爬取可能导致IP被临时封禁，建议控制每日运行次数
  - 若网站结构更新（如HTML标签变化），需同步修改代码中的CSS选择器

- **邮箱配置**：
  - QQ邮箱需在「设置→账户」中开启「SMTP服务」并获取授权码
  - 其他邮箱（如163）需修改代码中`smtp_server`和`smtp_port`（例如163邮箱为`smtp.163.com:465`）


## 致谢

- 基于Selenium实现自动化爬取
- 感谢开源社区提供的各类依赖库支持

如有问题或建议，欢迎提交Issue或PR！
